import ezdxf
from ezdxf import recover
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import math
import copy
import io
import numpy as np
from scipy.optimize import linear_sum_assignment
from collections import defaultdict
import logging
import json
import os
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Force matplotlib to use 'Agg' backend (no GUI)
import matplotlib
matplotlib.use('Agg')

# ----------------------------------------------------------------------
# Load configuration
# ----------------------------------------------------------------------
def load_cad_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    try:
        with open(config_path, 'r') as f:
            full = json.load(f)
            return full.get('cad_engine', {})
    except Exception as e:
        logger.warning(f"Could not load config.json, using defaults: {e}")
        return {}

CAD_CFG = load_cad_config()

def get_cfg(key, default):
    return CAD_CFG.get(key, default)

# ----------------------------------------------------------------------
# Tunable parameters
# ----------------------------------------------------------------------
TOL_POS = get_cfg('tolerance_position', 1e-3)
TOL_LEN = get_cfg('tolerance_length', 1e-2)
PROX_MULT = get_cfg('proximity_multiplier', 1.5)
DEFAULT_PROX = get_cfg('default_proximity', 5.0)
MATCH_COST_THRESH = get_cfg('matching_cost_threshold', 1.5)
CLASH_MARGIN = get_cfg('clash_margin', 5.0)
TEXT_SIM_THRESH = get_cfg('text_similarity_threshold', 0.8)
DIM_TOL = get_cfg('dimension_tolerance', 0.05)
POLY_CLOSE_TOL = get_cfg('polyline_closed_distance_tol', 0.01)
VOTING_ROUND = get_cfg('voting_rounding', 0.1)
SHAPE_KEY_DIGITS = get_cfg('shape_key_rounding_digits', 3)
LABEL_DIGITS = get_cfg('label_rounding_digits', 2)

def approx_eq(a, b, tol=TOL_POS):
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=tol)

def rnd(v, digits=LABEL_DIGITS):
    return round(float(v), digits)

def shape_key_round(v):
    return round(v, SHAPE_KEY_DIGITS)

# ----------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------
def bbox(pts):
    if not pts: return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))

def polyline_fingerprint(pts, closed):
    if len(pts) < 2:
        return None
    pts = [ezdxf.math.Vec2(p[0], p[1]) for p in pts]
    start_idx = min(range(len(pts)), key=lambda i: (pts[i].x, pts[i].y))
    pts = pts[start_idx:] + pts[:start_idx]
    edges = []
    angles = []
    for i in range(len(pts)):
        p1 = pts[i]
        p2 = pts[(i+1) % len(pts)] if closed or i+1 < len(pts) else None
        if p2 is None:
            break
        length = p1.distance(p2)
        edges.append(shape_key_round(length))
        angle = math.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x)) % 360
        if i > 0:
            turn = (angle - prev_angle) % 360
            if turn > 180:
                turn -= 360
            angles.append(round(turn, 1))
        prev_angle = angle
    return (closed, len(pts), tuple(edges), tuple(angles))

# ----------------------------------------------------------------------
# Entity extraction (with error handling and attribute support)
# ----------------------------------------------------------------------
def extract_entities(doc, warnings=None):
    if warnings is None:
        warnings = []
    ents = []
    for e in doc.modelspace():
        try:
            p = _parse_entity(e)
            if p:
                ents.append(p)
        except Exception as ex:
            warnings.append(f"Skipped entity {e.dxftype()}: {str(ex)}")
    return ents, warnings

def _parse_entity(e):
    t = e.dxftype()
    layer = str(getattr(e.dxf, 'layer', '0'))
    try:
        if t == 'CIRCLE':
            c = e.dxf.center
            r = e.dxf.radius
            sk = f"CIRCLE|r={shape_key_round(r)}|layer={layer}"
            return {'type':'CIRCLE','shape_key':sk,'cx':c.x,'cy':c.y,'r':r,'layer':layer,
                    'bbox':(c.x-r,c.y-r,c.x+r,c.y+r),'label':f'Circle r={rnd(r)}'}
        elif t == 'ARC':
            c = e.dxf.center; r = e.dxf.radius; sa = e.dxf.start_angle; ea = e.dxf.end_angle
            span = (ea - sa) % 360
            sk = f"ARC|r={shape_key_round(r)}|span={round(span,1)}|layer={layer}"
            return {'type':'ARC','shape_key':sk,'cx':c.x,'cy':c.y,'r':r,'sa':sa,'ea':ea,'layer':layer,
                    'bbox':(c.x-r,c.y-r,c.x+r,c.y+r),'label':f'Arc r={rnd(r)} span={round(span,1)}°'}
        elif t == 'LINE':
            s, e_pt = e.dxf.start, e.dxf.end
            length = s.distance(e_pt); angle = math.degrees(math.atan2(e_pt.y - s.y, e_pt.x - s.x)) % 180
            sk = f"LINE|len={shape_key_round(length)}|ang={round(angle,1)}|layer={layer}"
            return {'type':'LINE','shape_key':sk,'cx':(s.x+e_pt.x)/2,'cy':(s.y+e_pt.y)/2,'layer':layer,
                    'bbox':bbox([(s.x,s.y),(e_pt.x,e_pt.y)]),'label':f'Line len={rnd(length)}'}
        elif t == 'LWPOLYLINE':
            pts = [(p[0],p[1]) for p in e.get_points()]
            if len(pts)<2: return None
            closed = bool(e.closed or (len(pts)>=3 and math.dist(pts[0],pts[-1])<POLY_CLOSE_TOL))
            fp = polyline_fingerprint(pts, closed)
            if not fp: return None
            sk = f"LWPOLY|fp={fp}|layer={layer}"
            cx = sum(p[0] for p in pts)/len(pts); cy = sum(p[1] for p in pts)/len(pts)
            label = 'Rectangle' if (len(pts)==4 and closed) else f'Polyline({len(pts)}pts)'
            return {'type':'LWPOLYLINE','shape_key':sk,'cx':cx,'cy':cy,'layer':layer,'pts':pts,
                    'closed':closed,'n':len(pts),'bbox':bbox(pts),'label':label}
        elif t == 'DIMENSION':
            pt = e.dxf.defpoint
            meas = e.dxf.actual_measurement if hasattr(e.dxf,'actual_measurement') else None
            txt = (getattr(e.dxf,'text','') or '').strip()
            if meas is not None:
                meas_rounded = round(meas, 2)
                meas_key = str(meas_rounded)
            else:
                meas_rounded = None
                meas_key = txt
            sk = f"DIM|meas={meas_key}|layer={layer}"
            return {'type':'DIMENSION','shape_key':sk,'cx':pt.x,'cy':pt.y,'layer':layer,
                    'meas':meas, 'meas_rounded':meas_rounded, 'txt':txt,
                    'bbox':(pt.x-5,pt.y-5,pt.x+5,pt.y+5),'label':f'Dim {meas if meas else txt}'}
        elif t in ('MTEXT','TEXT'):
            pos = e.dxf.insert
            raw = e.text if t=='MTEXT' else e.dxf.text
            import re
            clean = re.sub(r'\\[A-Za-z][^;]*;', '', raw).strip()
            normalised = re.sub(r'[\s\(\)\{\}\[\]\.\,\-\_\*\&]', '', clean).upper()
            sk = f"TEXT|txt={normalised}|layer={layer}"
            return {'type':'TEXT','shape_key':sk,'cx':pos.x,'cy':pos.y,'layer':layer,
                    'txt':clean, 'norm_txt':normalised,
                    'bbox':(pos.x,pos.y,pos.x+len(clean)*2.5,pos.y+2.5),'label':f'Text "{clean[:20]}"'}
        elif t == 'INSERT':
            pt = e.dxf.insert
            name = e.dxf.name
            rot = getattr(e.dxf, 'rotation', 0)
            # Extract attributes
            attrs = {}
            try:
                for attrib in e.attribs:
                    tag = attrib.dxf.tag
                    value = attrib.dxf.text
                    attrs[tag] = value
            except Exception:
                pass
            sk = f"INSERT|name={name}|rot={round(rot,1)}|layer={layer}"
            return {
                'type': 'INSERT',
                'shape_key': sk,
                'cx': pt.x,
                'cy': pt.y,
                'layer': layer,
                'name': name,
                'rot': rot,
                'attributes': attrs,
                'bbox': (pt.x-6, pt.y-6, pt.x+6, pt.y+6),
                'label': f'Block: {name}' + (f' {attrs}' if attrs else '')
            }
        elif t == 'ELLIPSE':
            c = e.dxf.center
            maj = e.dxf.major_axis
            ratio = e.dxf.ratio
            mag = maj.magnitude
            sk = f"ELLIPSE|mag={shape_key_round(mag)}|ratio={round(ratio,4)}|layer={layer}"
            return {'type':'ELLIPSE','shape_key':sk,'cx':c.x,'cy':c.y,'layer':layer,
                    'bbox':(c.x-mag,c.y-mag,c.x+mag,c.y+mag),'label':f'Ellipse mag={rnd(mag)}'}
        elif t == 'SPLINE':
            pts = [(p[0],p[1]) for p in e.control_points]
            if len(pts)<2: return None
            total_len = sum(math.dist(pts[i],pts[i+1]) for i in range(len(pts)-1))
            sk = f"SPLINE|n={len(pts)}|len={shape_key_round(total_len)}|layer={layer}"
            cx = sum(p[0] for p in pts)/len(pts); cy = sum(p[1] for p in pts)/len(pts)
            return {'type':'SPLINE','shape_key':sk,'cx':cx,'cy':cy,'layer':layer,
                    'bbox':bbox(pts),'label':'Spline'}
        elif t == 'HATCH':
            # No geometric meaning for QA – ignore silently
            return None
    except Exception:
        # Let the exception bubble up to extract_entities
        raise
    return None

# ----------------------------------------------------------------------
# Offset detection and matching
# ----------------------------------------------------------------------
def detect_offset_voting(ea, eb):
    votes = defaultdict(int)
    b_by_shape = defaultdict(list)
    for e in eb:
        b_by_shape[e['shape_key']].append(e)
    for a in ea:
        matches = b_by_shape.get(a['shape_key'], [])
        if not matches:
            continue
        best = min(matches, key=lambda b: math.hypot(b['cx']-a['cx'], b['cy']-a['cy']))
        dx = best['cx'] - a['cx']; dy = best['cy'] - a['cy']
        qdx = round(dx / VOTING_ROUND) * VOTING_ROUND
        qdy = round(dy / VOTING_ROUND) * VOTING_ROUND
        votes[(qdx,qdy)] += 1
    if not votes:
        return 0.0,0.0
    return max(votes.items(), key=lambda kv: kv[1])[0]

def shift_entities(ents, dx, dy):
    if dx==0 and dy==0:
        return ents
    shifted = []
    for e in ents:
        ne = copy.deepcopy(e)
        ne['cx'] += dx; ne['cy'] += dy
        if e.get('bbox'):
            x1,y1,x2,y2 = e['bbox']
            ne['bbox'] = (x1+dx, y1+dy, x2+dx, y2+dy)
        if 'pts' in ne:
            ne['pts'] = [(x+dx, y+dy) for x,y in ne['pts']]
        shifted.append(ne)
    return shifted

def estimate_proximity(ea, eb):
    dx, dy = detect_offset_voting(ea, eb)
    distances = []
    for a in ea:
        candidates = [b for b in eb if b['shape_key'] == a['shape_key']]
        if not candidates:
            continue
        best = min(candidates, key=lambda b: math.hypot(b['cx']-(a['cx']+dx), b['cy']-(a['cy']+dy)))
        dist = math.hypot(best['cx']-(a['cx']+dx), best['cy']-(a['cy']+dy))
        distances.append(dist)
    if distances:
        return np.median(distances) * PROX_MULT
    return DEFAULT_PROX

REAL_GEO = {'LINE','CIRCLE','ARC','LWPOLYLINE','ELLIPSE','SPLINE'}

def text_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def detect_offset_per_layer(ea_global, eb, global_dx, global_dy):
    """
    After global offset, compute per‑layer offsets using voting.
    Returns dict {layer: (dx, dy)}.
    """
    from collections import defaultdict
    layer_offsets = {}
    # Group ea by layer
    ea_by_layer = defaultdict(list)
    for e in ea_global:
        layer = e.get('layer', '0')
        ea_by_layer[layer].append(e)
    # For each layer, vote on offset
    for layer, e_list in ea_by_layer.items():
        if len(e_list) < 2:   # need at least 2 entities for a reliable vote
            continue
        votes = defaultdict(int)
        # Build shape_key map for eb (output)
        b_by_shape = defaultdict(list)
        for e in eb:
            b_by_shape[e['shape_key']].append(e)
        for a in e_list:
            matches = b_by_shape.get(a['shape_key'], [])
            if not matches:
                continue
            best = min(matches, key=lambda b: math.hypot(b['cx'] - a['cx'], b['cy'] - a['cy']))
            dx = best['cx'] - a['cx']
            dy = best['cy'] - a['cy']
            qdx = round(dx / VOTING_ROUND) * VOTING_ROUND
            qdy = round(dy / VOTING_ROUND) * VOTING_ROUND
            votes[(qdx, qdy)] += 1
        if votes:
            # Most frequent offset for this layer
            offset = max(votes.items(), key=lambda kv: kv[1])[0]
            layer_offsets[layer] = offset
    return layer_offsets

def compare_dxf(ea_orig, eb_orig, warnings=None):
    if warnings is None:
        warnings = []
    try:
        dx, dy = detect_offset_voting(ea_orig, eb_orig)
        ea = shift_entities(ea_orig, dx, dy)
        prox = estimate_proximity(ea, eb_orig)
    except Exception as e:
        warnings.append(f"Offset/proximity estimation failed: {str(e)}")
        dx, dy = 0, 0
        ea = ea_orig
        prox = DEFAULT_PROX

    # Per‑layer offset detection
    try:
        layer_offsets = detect_offset_per_layer(ea, eb_orig, dx, dy)
        for e in ea:
            layer = e.get('layer', '0')
            if layer in layer_offsets:
                off_x, off_y = layer_offsets[layer]
                e['cx'] += off_x
                e['cy'] += off_y
                if 'bbox' in e:
                    x1, y1, x2, y2 = e['bbox']
                    e['bbox'] = (x1 + off_x, y1 + off_y, x2 + off_x, y2 + off_y)
                if 'pts' in e:
                    e['pts'] = [(x + off_x, y + off_y) for x, y in e['pts']]
    except Exception as e:
        warnings.append(f"Per‑layer offset detection failed: {str(e)}")

    # ---- Stage 1: Exact shape_key matching ----
    # Copy entities to avoid modifying originals
    ea_remaining = list(ea)
    eb_remaining = list(eb_orig)
    matched_pairs = []
    # Group input by shape_key for fast lookup
    from collections import defaultdict
    groups_a = defaultdict(list)
    for e in ea_remaining:
        groups_a[(e['type'], e['shape_key'])].append(e)
    groups_b = defaultdict(list)
    for e in eb_remaining:
        groups_b[(e['type'], e['shape_key'])].append(e)

    # For each exact shape_key group, run Hungarian to pair by position
    for key, a_list in groups_a.items():
        b_list = groups_b.get(key, [])
        if not a_list or not b_list:
            continue
        n = len(a_list)
        m = len(b_list)
        cost = np.zeros((n, m))
        for i, a in enumerate(a_list):
            for j, b in enumerate(b_list):
                pos_dist = math.hypot(a['cx'] - b['cx'], a['cy'] - b['cy'])
                pos_cost = min(pos_dist / prox, 1.0) if prox > 0 else 0.0
                cost[i, j] = pos_cost  # shape_cost = 0 (identical)
        row_ind, col_ind = linear_sum_assignment(cost)
        used_a = set()
        used_b = set()
        for r, c in zip(row_ind, col_ind):
            if cost[r, c] < MATCH_COST_THRESH:
                matched_pairs.append((a_list[r], b_list[c]))
                used_a.add(r)
                used_b.add(c)
        # Remove matched entities from remaining lists (by reference)
        # We'll rebuild unmatched later
    # Build remaining lists after exact matching
    a_unmatched_stage1 = []
    for a in ea_remaining:
        # Check if a was matched (by comparing with matched_pairs)
        matched = any(a is pair[0] for pair in matched_pairs)
        if not matched:
            a_unmatched_stage1.append(a)
    b_unmatched_stage1 = []
    for b in eb_remaining:
        matched = any(b is pair[1] for pair in matched_pairs)
        if not matched:
            b_unmatched_stage1.append(b)

    # ---- Stage 2: Type‑level matching for modifications ----
    # Group remaining by type only (ignoring shape_key)
    groups_a2 = defaultdict(list)
    for a in a_unmatched_stage1:
        groups_a2[a['type']].append(a)
    groups_b2 = defaultdict(list)
    for b in b_unmatched_stage1:
        groups_b2[b['type']].append(b)

    modified = []
    # For each type, run Hungarian with shape_cost
    for typ, a_list in groups_a2.items():
        b_list = groups_b2.get(typ, [])
        if not a_list or not b_list:
            # All will become missing/added later
            continue
        n = len(a_list)
        m = len(b_list)
        cost = np.zeros((n, m))
        for i, a in enumerate(a_list):
            for j, b in enumerate(b_list):
                shape_cost = 0.0 if a['shape_key'] == b['shape_key'] else 1.0
                pos_dist = math.hypot(a['cx'] - b['cx'], a['cy'] - b['cy'])
                pos_cost = min(pos_dist / prox, 1.0) if prox > 0 else 0.0
                cost[i, j] = shape_cost + pos_cost
        row_ind, col_ind = linear_sum_assignment(cost)
        used_a = set()
        used_b = set()
        for r, c in zip(row_ind, col_ind):
            if cost[r, c] < MATCH_COST_THRESH:
                # These are likely modifications
                a = a_list[r]
                b = b_list[c]
                # Classify modification
                if a['type'] == 'CIRCLE':
                    dr = b['r'] - a['r']
                    label = f"Radius {rnd(a['r'])} → {rnd(b['r'])} (Δ{dr:+.2f})"
                elif a['type'] == 'TEXT':
                    sim = text_similarity(a.get('norm_txt',''), b.get('norm_txt',''))
                    if sim < TEXT_SIM_THRESH:
                        label = f"Text '{a['txt']}' → '{b['txt']}'"
                    else:
                        label = f"Text formatting changed (ignored)"
                        # Optionally treat as identical
                elif a['type'] == 'DIMENSION':
                    if not approx_eq(a.get('meas_rounded'), b.get('meas_rounded'), tol=DIM_TOL):
                        label = f"Dim {a['meas_rounded']} → {b['meas_rounded']}"
                    else:
                        continue
                elif a['type'] == 'INSERT':
                    if a['name'] != b['name']:
                        label = f"Block changed: {a['name']} → {b['name']}"
                    elif a.get('attributes') != b.get('attributes'):
                        label = f"Block attributes changed: {a.get('attributes')} → {b.get('attributes')}"
                    else:
                        continue
                else:
                    label = f"{a['type']} modified"
                modified.append({
                    'from': a,
                    'to': b,
                    'label': label,
                    'bbox': b.get('bbox')
                })
                used_a.add(r)
                used_b.add(c)
        # Remaining after type matching become missing/added
        # We'll collect them in the final unmatched lists
    # Build final missing and added from unmatched after both stages
    # (Simplification: treat all unmatched from stage1 that were not matched in stage2 as missing/added)
    # For simplicity, we'll take all remaining from stage1 after removing stage2 matches
    # Instead of complex bookkeeping, we'll just recalc:
    # Collect all matched from stage1 (moved) and stage2 (modified)
    all_matched_input = [pair[0] for pair in matched_pairs] + [m['from'] for m in modified]
    all_matched_output = [pair[1] for pair in matched_pairs] + [m['to'] for m in modified]
    missing = [e for e in ea_remaining if e not in all_matched_input]
    added = [e for e in eb_remaining if e not in all_matched_output]

    moved = []
    for a, b in matched_pairs:
        if not (approx_eq(a['cx'], b['cx']) and approx_eq(a['cy'], b['cy'])):
            delta_x = b['cx'] - a['cx']
            delta_y = b['cy'] - a['cy']
            moved.append({
                'from': a,
                'to': b,
                'label': f"Moved by ({delta_x:+.1f},{delta_y:+.1f})",
                'bbox': b.get('bbox')
            })
        # If position unchanged, no difference

    # Clash detection (unchanged, uses eb_orig and added)
    clashes = []
    try:
        real_in_output = [e for e in eb_orig if e['type'] in REAL_GEO]
        for a in added:
            if a['type'] not in REAL_GEO or not a.get('bbox'):
                continue
            x1, y1, x2, y2 = a['bbox']
            w, h = x2 - x1, y2 - y1
            if w < 0.5 or h < 0.5 or (min(w, h) > 0 and max(w, h) / min(w, h) > 12):
                continue
            for be in real_in_output:
                if be.get('shape_key') == a.get('shape_key'):
                    continue
                if not be.get('bbox'):
                    continue
                bx1, by1, bx2, by2 = be['bbox']
                if (x1 - CLASH_MARGIN < bx2 and x2 + CLASH_MARGIN > bx1 and
                    y1 - CLASH_MARGIN < by2 and y2 + CLASH_MARGIN > by1):
                    clashes.append({'a': a, 'b': be, 'bbox': a['bbox']})
                    break
    except Exception as e:
        warnings.append(f"Clash detection error: {str(e)}")

    return {
        'moved': moved,
        'modified': modified,
        'missing': missing,
        'added': added,
        'clashes': clashes,
        'offset': (dx, dy),
        'prox': prox
    }, warnings

# ----------------------------------------------------------------------
# Image generation (unchanged)
# ----------------------------------------------------------------------
def generate_qa_image(doc_b, diff, name_input, name_output, opts):
    fig, ax = plt.subplots(figsize=(16, 16))
    ctx = RenderContext(doc_b)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(doc_b.modelspace(), finalize=True)

    colors = {
        'moved': '#FFA500',
        'modified': '#FF4444',
        'missing': '#FF3333',
        'added': '#33CC55',
        'clashes': '#CC33FF'
    }

    placed_labels = []

    def draw_category(cat, entities, color, show_label, outline_only):
        for ent in entities:
            bbox = ent.get('bbox') if cat != 'clashes' else ent.get('bbox')
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            w = max(x2 - x1, 3.0)
            h = max(y2 - y1, 3.0)
            pad = max(w * 0.3, h * 0.3, 5.0)
            rx, ry, rw, rh = x1 - pad, y1 - pad, w + 2 * pad, h + 2 * pad
            if not outline_only:
                ax.add_patch(mpatches.Rectangle((rx, ry), rw, rh,
                                                fc=color, ec='none', alpha=0.15, zorder=10))
            ax.add_patch(mpatches.Rectangle((rx, ry), rw, rh,
                                            fc='none', ec=color, lw=1.5, alpha=0.8, zorder=11))
            if show_label and cat != 'clashes':
                label = ent.get('label', '')
                if cat == 'moved' and 'label' in ent:
                    label = ent['label']
                elif cat == 'modified' and 'label' in ent:
                    label = ent['label']
                elif cat == 'missing':
                    label = f"Missing: {ent['label']}"
                elif cat == 'added':
                    label = f"Added: {ent['label']}"
                if label:
                    cx = rx + rw / 2
                    ly = ry + rh + 3
                    for px, py in placed_labels:
                        if abs(px - cx) < rw * 0.7 and abs(py - ly) < 10:
                            ly += 12
                    ax.text(cx, ly, label, ha='center', va='bottom', fontsize=7,
                            color=color, fontweight='bold', zorder=12,
                            bbox=dict(boxstyle='round,pad=0.2', fc='#111111', ec=color, lw=0.5, alpha=0.9))
                    placed_labels.append((cx, ly))

    show_moved = opts.get('moved', opts.get('changes', True))
    show_modified = opts.get('modified', opts.get('changes', True))
    show_missing = opts.get('missing', opts.get('changes', True))
    show_added = opts.get('added', opts.get('changes', True))
    show_clashes = opts.get('clash', True)
    show_labels = opts.get('labels', True)
    outlines_only = opts.get('outlinesOnly', False)

    if show_moved:
        draw_category('moved', diff['moved'], colors['moved'], show_labels, outlines_only)
    if show_modified:
        draw_category('modified', diff['modified'], colors['modified'], show_labels, outlines_only)
    if show_missing:
        draw_category('missing', diff['missing'], colors['missing'], show_labels, outlines_only)
    if show_added:
        draw_category('added', diff['added'], colors['added'], show_labels, outlines_only)
    if show_clashes:
        draw_category('clashes', diff['clashes'], colors['clashes'], False, outlines_only)

    handles = []
    if show_moved and diff['moved']:
        handles.append(mpatches.Patch(fc=colors['moved'], ec=colors['moved'], label=f"Moved ({len(diff['moved'])})"))
    if show_modified and diff['modified']:
        handles.append(mpatches.Patch(fc=colors['modified'], ec=colors['modified'], label=f"Modified ({len(diff['modified'])})"))
    if show_missing and diff['missing']:
        handles.append(mpatches.Patch(fc=colors['missing'], ec=colors['missing'], label=f"Missing ({len(diff['missing'])})"))
    if show_added and diff['added']:
        handles.append(mpatches.Patch(fc=colors['added'], ec=colors['added'], label=f"Added ({len(diff['added'])})"))
    if show_clashes and diff['clashes']:
        handles.append(mpatches.Patch(fc=colors['clashes'], ec=colors['clashes'], label=f"Clashes ({len(diff['clashes'])})"))
    if handles:
        ax.legend(handles=handles, loc='upper right', fontsize=9,
                  framealpha=0.9, facecolor='#111111', edgecolor='#666',
                  labelcolor='white', title='Legend', title_fontsize=10)

    total = len(diff['moved']) + len(diff['modified']) + len(diff['missing']) + len(diff['added']) + len(diff['clashes'])
    status = 'PASS' if total == 0 else f'FAIL ({total} deviation(s))'
    ax.set_title(f"QA Result – Output: {name_output}  vs  Input: {name_input}  |  {status}",
                 fontsize=10, fontweight='bold', color='white', pad=6, loc='left',
                 bbox=dict(fc='#111111', ec='none', alpha=0.75, pad=5))

    fig.tight_layout(pad=0)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#111111')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

# ----------------------------------------------------------------------
# Main processing function (partial reports, warnings)
# ----------------------------------------------------------------------
def process_cad_files(file1_bytes, file2_bytes, opts):
    warnings = []
    img_bytes = None
    report = {}

    try:
        stream1 = io.BytesIO(file1_bytes)
        stream2 = io.BytesIO(file2_bytes)
        doc_a, _ = recover.read(stream1)
        doc_b, _ = recover.read(stream2)
        ea, warnings_a = extract_entities(doc_a, warnings)
        eb, warnings_b = extract_entities(doc_b, warnings)
        warnings.extend(warnings_a)
        warnings.extend(warnings_b)

        # Check identical
        if len(ea) == len(eb) and all(
            a['shape_key'] == b['shape_key'] and
            approx_eq(a['cx'], b['cx']) and approx_eq(a['cy'], b['cy'])
            for a, b in zip(ea, eb)
        ):
            fig, ax = plt.subplots(figsize=(16, 16))
            ctx = RenderContext(doc_b)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc_b.modelspace(), finalize=True)
            ax.set_title("✓", fontsize=40, fontweight='bold', color='green', pad=20, loc='center')
            ax.set_axis_off()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#111111')
            plt.close(fig)
            img_bytes = buf.getvalue()
            report = {
                "identical": True,
                "moved": 0, "modified": 0, "missing": 0, "added": 0, "clashes": 0,
                "details": {"moved": [], "modified": [], "missing": [], "added": [], "clashes": []},
                "warnings": warnings
            }
            return img_bytes, report

        diff, match_warnings = compare_dxf(ea, eb, warnings)
        warnings.extend(match_warnings)
        img_bytes = generate_qa_image(doc_b, diff, "input.dxf", "output.dxf", opts)

        moved_details = []
        for item in diff.get('moved', []):
            a = item['from']; b = item['to']
            moved_details.append({
                "type": a['type'],
                "label": item['label'],
                "layer": a.get('layer', '0'),
                "change_description": f"Moved from ({a['cx']:.1f},{a['cy']:.1f}) to ({b['cx']:.1f},{b['cy']:.1f})",
                "position": f"({b['cx']:.1f}, {b['cy']:.1f})"
            })
        modified_details = []
        for item in diff.get('modified', []):
            a = item['from']; b = item['to']
            modified_details.append({
                "type": a['type'],
                "label": item['label'],
                "layer": a.get('layer', '0'),
                "change_description": item['label'],
                "position": f"({b.get('cx', 0):.1f}, {b.get('cy', 0):.1f})"
            })
        missing_details = []
        for item in diff.get('missing', []):
            attrs_str = ""
            if item.get('attributes'):
                attrs_str = " " + str(item['attributes'])
            missing_details.append({
                "type": item['type'],
                "label": item.get('label', 'Unknown') + attrs_str,
                "layer": item.get('layer', '0'),
                "change_description": "Missing in output",
                "position": f"({item.get('cx', 0):.1f}, {item.get('cy', 0):.1f})"
            })
        added_details = []
        for item in diff.get('added', []):
            attrs_str = ""
            if item.get('attributes'):
                attrs_str = " " + str(item['attributes'])
            added_details.append({
                "type": item['type'],
                "label": item.get('label', 'Unknown') + attrs_str,
                "layer": item.get('layer', '0'),
                "change_description": "Added (not in input)",
                "position": f"({item.get('cx', 0):.1f}, {item.get('cy', 0):.1f})"
            })
        clash_details = []
        for item in diff.get('clashes', []):
            a = item['a']; b = item['b']
            clash_details.append({
                "type": a['type'],
                "label": f"{a.get('label', '?')} ↔ {b.get('label', '?')}",
                "layer": a.get('layer', '0'),
                "change_description": f"Clash between {a['type']} and {b['type']}",
                "position": f"({a.get('cx', 0):.1f}, {a.get('cy', 0):.1f})"
            })
        report = {
            "identical": False,
            "moved": len(moved_details),
            "modified": len(modified_details),
            "missing": len(missing_details),
            "added": len(added_details),
            "clashes": len(clash_details),
            "details": {
                "moved": moved_details,
                "modified": modified_details,
                "missing": missing_details,
                "added": added_details,
                "clashes": clash_details
            },
            "warnings": warnings
        }
        return img_bytes, report

    except Exception as e:
        logger.error(f"Critical CAD processing error: {str(e)}", exc_info=True)
        fig, ax = plt.subplots(figsize=(8,6))
        ax.text(0.5, 0.5, f"CAD Analysis Failed:\n{str(e)}", ha='center', va='center',
                transform=ax.transAxes, color='red')
        ax.set_axis_off()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig)
        img_bytes = buf.getvalue()
        report = {"error": str(e), "warnings": warnings}
        return img_bytes, report

# ----------------------------------------------------------------------
# DXF preview (reuse identical-file branch with no overlays)
# ----------------------------------------------------------------------
def render_dxf_preview(file_bytes):
    opts = {
        "moved": False,
        "modified": False,
        "missing": False,
        "added": False,
        "clash": False,
        "labels": False,
        "outlinesOnly": False
    }
    img_bytes, _ = process_cad_files(file_bytes, file_bytes, opts)
    return img_bytes