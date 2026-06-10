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

# Force matplotlib to use 'Agg' backend (no GUI)
import matplotlib
matplotlib.use('Agg')

# ---------- Tolerance settings ----------
TOL_POS = 1e-3
TOL_LEN = 1e-2

def approx_eq(a, b, tol=TOL_POS):
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=tol)

def rnd(v, digits=2):
    return round(float(v), digits)

# ---------- Entity extraction (simplified for web) ----------
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
        edges.append(rnd(length, 3))
        angle = math.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x)) % 360
        if i > 0:
            turn = (angle - prev_angle) % 360
            if turn > 180:
                turn -= 360
            angles.append(rnd(turn, 1))
        prev_angle = angle
    return (closed, len(pts), tuple(edges), tuple(angles))

def extract_entities(doc):
    ents = []
    for e in doc.modelspace():
        p = _parse_entity(e)
        if p:
            ents.append(p)
    return ents

def _parse_entity(e):
    t = e.dxftype()
    layer = str(getattr(e.dxf, 'layer', '0'))
    try:
        if t == 'CIRCLE':
            c = e.dxf.center
            r = e.dxf.radius
            sk = f"CIRCLE|r={rnd(r,3)}|layer={layer}"
            return {'type':'CIRCLE','shape_key':sk,'cx':c.x,'cy':c.y,'r':r,'layer':layer,
                    'bbox':(c.x-r,c.y-r,c.x+r,c.y+r),'label':f'Circle r={rnd(r,2)}'}
        elif t == 'ARC':
            c = e.dxf.center; r = e.dxf.radius; sa = e.dxf.start_angle; ea = e.dxf.end_angle
            span = (ea - sa) % 360
            sk = f"ARC|r={rnd(r,3)}|span={rnd(span,1)}|layer={layer}"
            return {'type':'ARC','shape_key':sk,'cx':c.x,'cy':c.y,'r':r,'sa':sa,'ea':ea,'layer':layer,
                    'bbox':(c.x-r,c.y-r,c.x+r,c.y+r),'label':f'Arc r={rnd(r,2)} span={rnd(span,1)}°'}
        elif t == 'LINE':
            s, e_pt = e.dxf.start, e.dxf.end
            length = s.distance(e_pt); angle = math.degrees(math.atan2(e_pt.y - s.y, e_pt.x - s.x)) % 180
            sk = f"LINE|len={rnd(length,3)}|ang={rnd(angle,1)}|layer={layer}"
            return {'type':'LINE','shape_key':sk,'cx':(s.x+e_pt.x)/2,'cy':(s.y+e_pt.y)/2,'layer':layer,
                    'bbox':bbox([(s.x,s.y),(e_pt.x,e_pt.y)]),'label':f'Line len={rnd(length,2)}'}
        elif t == 'LWPOLYLINE':
            pts = [(p[0],p[1]) for p in e.get_points()]
            if len(pts)<2: return None
            closed = bool(e.closed or (len(pts)>=3 and math.dist(pts[0],pts[-1])<TOL_LEN))
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
            meas_key = rnd(meas,3) if meas is not None else txt
            sk = f"DIM|meas={meas_key}|layer={layer}"
            return {'type':'DIMENSION','shape_key':sk,'cx':pt.x,'cy':pt.y,'layer':layer,
                    'meas':meas,'txt':txt,'bbox':(pt.x-5,pt.y-5,pt.x+5,pt.y+5),'label':f'Dim {meas if meas else txt}'}
        elif t in ('MTEXT','TEXT'):
            pos = e.dxf.insert
            raw = e.text if t=='MTEXT' else e.dxf.text
            import re
            clean = re.sub(r'\\[A-Za-z][^;]*;','',raw).strip()
            sk = f"TEXT|txt={clean}|layer={layer}"
            return {'type':'TEXT','shape_key':sk,'cx':pos.x,'cy':pos.y,'layer':layer,
                    'txt':clean,'bbox':(pos.x,pos.y,pos.x+len(clean)*2.5,pos.y+2.5),'label':f'Text "{clean[:20]}"'}
        elif t == 'INSERT':
            pt = e.dxf.insert; name = e.dxf.name; rot = getattr(e.dxf,'rotation',0)
            sk = f"INSERT|name={name}|rot={rnd(rot,1)}|layer={layer}"
            return {'type':'INSERT','shape_key':sk,'cx':pt.x,'cy':pt.y,'layer':layer,
                    'name':name,'rot':rot,'bbox':(pt.x-6,pt.y-6,pt.x+6,pt.y+6),'label':f'Symbol "{name}"'}
        elif t == 'ELLIPSE':
            c = e.dxf.center; maj = e.dxf.major_axis; ratio = e.dxf.ratio; mag = maj.magnitude
            sk = f"ELLIPSE|mag={rnd(mag,3)}|ratio={rnd(ratio,4)}|layer={layer}"
            return {'type':'ELLIPSE','shape_key':sk,'cx':c.x,'cy':c.y,'layer':layer,
                    'bbox':(c.x-mag,c.y-mag,c.x+mag,c.y+mag),'label':f'Ellipse mag={rnd(mag,2)}'}
        elif t == 'SPLINE':
            pts = [(p[0],p[1]) for p in e.control_points]
            if len(pts)<2: return None
            total_len = sum(math.dist(pts[i],pts[i+1]) for i in range(len(pts)-1))
            sk = f"SPLINE|n={len(pts)}|len={rnd(total_len,3)}|layer={layer}"
            cx = sum(p[0] for p in pts)/len(pts); cy = sum(p[1] for p in pts)/len(pts)
            return {'type':'SPLINE','shape_key':sk,'cx':cx,'cy':cy,'layer':layer,
                    'bbox':bbox(pts),'label':'Spline'}
    except Exception:
        pass
    return None

# ---------- Offset detection & matching (same as Colab) ----------
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
        qdx = round(dx*10)/10.0; qdy = round(dy*10)/10.0
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
    return np.median(distances) * 1.5 if distances else 5.0

REAL_GEO = {'LINE','CIRCLE','ARC','LWPOLYLINE','ELLIPSE','SPLINE'}

def compare_dxf(ea_orig, eb_orig):
    dx, dy = detect_offset_voting(ea_orig, eb_orig)
    ea = shift_entities(ea_orig, dx, dy)
    prox = estimate_proximity(ea, eb_orig)

    types = set(e['type'] for e in ea) | set(e['type'] for e in eb_orig)
    matched_pairs = []
    a_unmatched = []
    b_unmatched = []

    for typ in types:
        a_list = [e for e in ea if e['type']==typ]
        b_list = [e for e in eb_orig if e['type']==typ]
        if not a_list or not b_list:
            a_unmatched.extend(a_list)
            b_unmatched.extend(b_list)
            continue
        cost = np.zeros((len(a_list), len(b_list)))
        for i,a in enumerate(a_list):
            for j,b in enumerate(b_list):
                shape_cost = 0.0 if a['shape_key']==b['shape_key'] else 1.0
                pos_dist = math.hypot(a['cx']-b['cx'], a['cy']-b['cy'])
                pos_cost = min(pos_dist/prox, 1.0) if prox>0 else 0.0
                cost[i,j] = shape_cost + pos_cost
        row_ind, col_ind = linear_sum_assignment(cost)
        used_a = set(); used_b = set()
        for r,c in zip(row_ind, col_ind):
            if cost[r,c] < 1.5:
                matched_pairs.append((a_list[r], b_list[c]))
                used_a.add(r); used_b.add(c)
        for i,a in enumerate(a_list):
            if i not in used_a:
                a_unmatched.append(a)
        for j,b in enumerate(b_list):
            if j not in used_b:
                b_unmatched.append(b)

    moved = []
    modified = []
    for a,b in matched_pairs:
        if a['shape_key'] == b['shape_key']:
            if not (approx_eq(a['cx'],b['cx']) and approx_eq(a['cy'],b['cy'])):
                delta_x = b['cx'] - a['cx']; delta_y = b['cy'] - a['cy']
                moved.append({'from':a,'to':b,'label':f"Moved by ({delta_x:+.1f},{delta_y:+.1f})",'bbox':b.get('bbox')})
        else:
            if a['type'] == 'CIRCLE':
                dr = b['r'] - a['r']
                modified.append({'from':a,'to':b,'label':f"Radius {rnd(a['r'])} → {rnd(b['r'])} (Δ{dr:+.2f})",'bbox':b.get('bbox')})
            elif a['type'] == 'TEXT' and a['txt'] != b['txt']:
                modified.append({'from':a,'to':b,'label':f"Text '{a['txt']}' → '{b['txt']}'",'bbox':b.get('bbox')})
            elif a['type'] == 'DIMENSION' and not approx_eq(a['meas'], b['meas'], tol=TOL_LEN):
                modified.append({'from':a,'to':b,'label':f"Dim {rnd(a['meas'])} → {rnd(b['meas'])}",'bbox':b.get('bbox')})
            else:
                modified.append({'from':a,'to':b,'label':f"{a['type']} modified",'bbox':b.get('bbox')})

    missing = a_unmatched
    added = b_unmatched

    # Clash detection
    clashes = []
    real_in_output = [e for e in eb_orig if e['type'] in REAL_GEO]
    for a in added:
        if a['type'] not in REAL_GEO or not a.get('bbox'):
            continue
        x1,y1,x2,y2 = a['bbox']
        w,h = x2-x1, y2-y1
        if w<0.5 or h<0.5 or (min(w,h)>0 and max(w,h)/min(w,h)>12):
            continue
        for be in real_in_output:
            if be.get('shape_key') == a.get('shape_key'):
                continue
            if not be.get('bbox'):
                continue
            bx1,by1,bx2,by2 = be['bbox']
            if (x1 - 5 < bx2 and x2 + 5 > bx1 and y1 - 5 < by2 and y2 + 5 > by1):
                clashes.append({'a':a, 'b':be, 'bbox':a['bbox']})
                break

    return {'moved':moved, 'modified':modified, 'missing':missing, 'added':added, 'clashes':clashes,
            'offset':(dx,dy), 'prox':prox}

def generate_qa_image(doc_b, diff, name_input, name_output, opts):
    """Return PNG bytes of the output DXF with overlays respecting fine-grained options."""
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
                    # avoid label overlap
                    for px, py in placed_labels:
                        if abs(px - cx) < rw * 0.7 and abs(py - ly) < 10:
                            ly += 12
                    ax.text(cx, ly, label, ha='center', va='bottom', fontsize=7,
                            color=color, fontweight='bold', zorder=12,
                            bbox=dict(boxstyle='round,pad=0.2', fc='#111111', ec=color, lw=0.5, alpha=0.9))
                    placed_labels.append((cx, ly))

    # Use new fine-grained options; fallback to old 'changes' for backward compatibility
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

    # Legend (only show categories that are enabled)
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

def process_cad_files(file1_bytes, file2_bytes, opts):
    import io
    try:
        stream1 = io.BytesIO(file1_bytes)
        stream2 = io.BytesIO(file2_bytes)
        doc_a, _ = recover.read(stream1)
        doc_b, _ = recover.read(stream2)
        ea = extract_entities(doc_a)
        eb = extract_entities(doc_b)

        # Check for identical
        if len(ea) == len(eb) and all(
            a['shape_key'] == b['shape_key'] and
            approx_eq(a['cx'], b['cx']) and approx_eq(a['cy'], b['cy'])
            for a, b in zip(ea, eb)
        ):
            fig, ax = plt.subplots(figsize=(16, 16))
            ctx = RenderContext(doc_b)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc_b.modelspace(), finalize=True)
            ax.set_title("NO DIFFERENCE DETECTED", fontsize=20, fontweight='bold',
                         color='green', pad=20, loc='center')
            ax.set_axis_off()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#111111')
            plt.close(fig)
            report = {
                "identical": True,
                "moved": 0, "modified": 0, "missing": 0, "added": 0, "clashes": 0,
                "details": {
                    "moved": [], "modified": [], "missing": [], "added": [], "clashes": []
                }
            }
            return buf.getvalue(), report

        diff = compare_dxf(ea, eb)
        img_bytes = generate_qa_image(doc_b, diff, "input.dxf", "output.dxf", opts)

        # Build detailed lists with extra fields
        moved_details = []
        for item in diff['moved']:
            a = item['from']
            b = item['to']
            moved_details.append({
                "type": a['type'],
                "label": item['label'],
                "layer": a.get('layer', '0'),
                "change_description": f"Moved from ({a['cx']:.1f},{a['cy']:.1f}) to ({b['cx']:.1f},{b['cy']:.1f})",
                "position": f"({b['cx']:.1f}, {b['cy']:.1f})"
            })

        modified_details = []
        for item in diff['modified']:
            a = item['from']
            b = item['to']
            modified_details.append({
                "type": a['type'],
                "label": item['label'],
                "layer": a.get('layer', '0'),
                "change_description": item['label'],
                "position": f"({b.get('cx', 0):.1f}, {b.get('cy', 0):.1f})"
            })

        missing_details = []
        for item in diff['missing']:
            missing_details.append({
                "type": item['type'],
                "label": item.get('label', 'Unknown'),
                "layer": item.get('layer', '0'),
                "change_description": "Missing in output",
                "position": f"({item.get('cx', 0):.1f}, {item.get('cy', 0):.1f})"
            })

        added_details = []
        for item in diff['added']:
            added_details.append({
                "type": item['type'],
                "label": item.get('label', 'Unknown'),
                "layer": item.get('layer', '0'),
                "change_description": "Added (not in input)",
                "position": f"({item.get('cx', 0):.1f}, {item.get('cy', 0):.1f})"
            })

        clash_details = []
        for item in diff['clashes']:
            a = item['a']
            b = item['b']
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
            }
        }
        return img_bytes, report
    except Exception as e:
        fig, ax = plt.subplots(figsize=(8,6))
        ax.text(0.5, 0.5, f"CAD Error: {str(e)}", ha='center', va='center', transform=ax.transAxes, color='red')
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig)
        report = {"error": str(e)}
        return buf.getvalue(), report