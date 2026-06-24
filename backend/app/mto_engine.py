import ezdxf
import math
import tempfile
import os
import re
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Block name classification helpers
# ----------------------------------------------------------------------
def classify_block(block_name):
    """
    Returns (type, subtype) based on the block name.
    """
    name_upper = block_name.upper()
    type_ = "Fitting"   # default
    subtype = ""

    # ---- Elbow ----
    if "EL90" in name_upper or "ELBOW" in name_upper or "ELB" in name_upper:
        type_ = "Elbow"
        if "90" in name_upper:
            subtype = "90°"
        elif "45" in name_upper:
            subtype = "45°"
        else:
            subtype = "Elbow"
        # Check for material
        if "PVC" in name_upper:
            subtype += " PVC"
        elif "CS" in name_upper:
            subtype += " CS"
        elif "SS" in name_upper:
            subtype += " SS"

    # ---- Tee ----
    elif " T " in name_upper or " T " in block_name:  # pattern: T TOP, T RIGHT, etc.
        type_ = "Tee"
        # extract orientation
        parts = block_name.upper().split()
        if len(parts) >= 2:
            orient = parts[1]
            if orient in ("TOP", "RIGHT", "LEFT", "DOWN", "VERTI"):
                subtype = f"Tee ({orient})"
            else:
                subtype = "Tee"
        else:
            subtype = "Tee"

    # ---- Reducer ----
    elif "RED" in name_upper:
        type_ = "Reducer"
        subtype = "Reducer"

    # ---- Valve ----
    elif "VALVE" in name_upper or "VLV" in name_upper:
        type_ = "Valve"
        subtype = "Valve"

    # ---- Flange ----
    elif "FLANGE" in name_upper or "FLG" in name_upper:
        type_ = "Flange"
        subtype = "Flange"

    # ---- If nothing matches, keep as Fitting ----
    else:
        type_ = "Fitting"
        subtype = block_name   # store raw name as subtype

    # If subtype is still empty, use a cleaned version of the block name
    if not subtype:
        subtype = block_name[:20]

    return type_, subtype

# ----------------------------------------------------------------------
# Helpers to extract info from text (kept for pipe classification)
# ----------------------------------------------------------------------
def extract_size_from_text(text):
    if not text:
        return None
    text = text.upper()
    m = re.search(r'DN(\d+)', text)
    if m:
        return f"DN{m.group(1)}"
    m = re.search(r'(\d+(?:/\d+)?)"', text)
    if m:
        return f"{m.group(1)}\""
    m = re.search(r'(\d+)MM', text)
    if m:
        return f"{m.group(1)}mm"
    return None

def extract_schedule_from_text(text):
    if not text:
        return None
    text = text.upper()
    m = re.search(r'SCH\s*(\w+)', text)
    if m:
        return m.group(1)
    if 'XS' in text:
        return 'XS'
    if 'XXS' in text:
        return 'XXS'
    return None

def extract_material_from_text(text):
    if not text:
        return None
    text = text.upper()
    if 'ASTM A106' in text:
        return 'ASTM A106 Gr B SMLS'
    if 'ASTM A312' in text:
        return 'ASTM A312 TP304'
    if 'ASTM A312 TP316' in text:
        return 'ASTM A312 TP316'
    if 'SS304' in text:
        return 'SS304'
    if 'SS316' in text:
        return 'SS316'
    if 'CARBON STEEL' in text:
        return 'Carbon Steel'
    return None

# ----------------------------------------------------------------------
# Layer‑based fallback (if block mapping fails)
# ----------------------------------------------------------------------
LAYER_TYPE_MAP = {
    "pipe": "Pipe",
    "piping": "Pipe",
    "line": "Pipe",
    "flange": "Flange",
    "elbow": "Elbow",
    "tee": "Tee",
    "reducer": "Reducer",
    "valve": "Valve",
    "support": "Support",
    "instrument": "Instrument",
}

def get_type_from_layer(layer):
    layer_lower = layer.lower()
    for key, comp_type in LAYER_TYPE_MAP.items():
        if key in layer_lower:
            return comp_type
    return None

# ----------------------------------------------------------------------
# DXF MTO extraction (no annotations, classified blocks)
# ----------------------------------------------------------------------
def extract_mto_from_dxf(file_bytes):
    with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()

        # Storage
        pipe_groups = defaultdict(lambda: {
            "count": 0,
            "total_len": 0.0,
            "layer": "",
            "size": "",
            "schedule": "",
            "material": ""
        })
        comp_groups = defaultdict(lambda: {
            "count": 0,
            "layer": "",
            "type": "",
            "subtype": "",
            "description": ""
        })

        # Collect text entities (only for pipe size/material inference)
        text_entities = []
        for e in msp:
            if e.dxftype() in ('TEXT', 'MTEXT'):
                pos = e.dxf.insert
                raw = e.text if e.dxftype() == 'MTEXT' else e.dxf.text
                clean = re.sub(r'\\[A-Za-z][^;]*;', '', raw).strip()
                if clean:
                    text_entities.append((pos.x, pos.y, clean))

        def find_nearby_text(cx, cy, radius=50):
            for tx, ty, txt in text_entities:
                if abs(tx - cx) < radius and abs(ty - cy) < radius:
                    return txt
            return None

        # Process each entity
        for e in msp:
            t = e.dxftype()
            layer = e.dxf.layer
            try:
                if t == 'LINE':
                    length = e.dxf.start.distance(e.dxf.end)
                    cx = (e.dxf.start.x + e.dxf.end.x) / 2
                    cy = (e.dxf.start.y + e.dxf.end.y) / 2
                    nearby = find_nearby_text(cx, cy, 50)
                    size = extract_size_from_text(nearby) or ""
                    schedule = extract_schedule_from_text(nearby) or ""
                    material = extract_material_from_text(nearby) or ""
                    key = (layer, size, schedule, material)
                    pipe_groups[key]["count"] += 1
                    pipe_groups[key]["total_len"] += length
                    pipe_groups[key]["layer"] = layer
                    pipe_groups[key]["size"] = size
                    pipe_groups[key]["schedule"] = schedule
                    pipe_groups[key]["material"] = material

                elif t == 'LWPOLYLINE':
                    pts = list(e.vertices())
                    if len(pts) < 2:
                        continue
                    total_len = 0.0
                    for i in range(len(pts)-1):
                        total_len += math.dist((pts[i][0], pts[i][1]), (pts[i+1][0], pts[i+1][1]))
                    if e.closed and len(pts) > 2:
                        total_len += math.dist((pts[-1][0], pts[-1][1]), (pts[0][0], pts[0][1]))
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    nearby = find_nearby_text(cx, cy, 50)
                    size = extract_size_from_text(nearby) or ""
                    schedule = extract_schedule_from_text(nearby) or ""
                    material = extract_material_from_text(nearby) or ""
                    key = (layer, size, schedule, material)
                    pipe_groups[key]["count"] += 1
                    pipe_groups[key]["total_len"] += total_len
                    pipe_groups[key]["layer"] = layer
                    pipe_groups[key]["size"] = size
                    pipe_groups[key]["schedule"] = schedule
                    pipe_groups[key]["material"] = material

                elif t == 'CIRCLE':
                    r = e.dxf.radius
                    size = f"R{round(r,1)}"
                    comp_type = get_type_from_layer(layer) or "Flange"
                    key = (layer, comp_type, size)
                    comp_groups[key]["count"] += 1
                    comp_groups[key]["layer"] = layer
                    comp_groups[key]["type"] = comp_type
                    comp_groups[key]["subtype"] = size
                    comp_groups[key]["description"] = f"Flange {size}"

                elif t == 'ARC':
                    r = e.dxf.radius
                    size = f"R{round(r,1)}"
                    comp_type = get_type_from_layer(layer) or "Elbow"
                    key = (layer, comp_type, size)
                    comp_groups[key]["count"] += 1
                    comp_groups[key]["layer"] = layer
                    comp_groups[key]["type"] = comp_type
                    comp_groups[key]["subtype"] = size
                    comp_groups[key]["description"] = f"Elbow {size}"

                elif t == 'INSERT':
                    name = e.dxf.name
                    comp_type, subtype = classify_block(name)
                    # If block name is unknown and layer gives a type, use layer type
                    if comp_type == "Fitting" and get_type_from_layer(layer):
                        comp_type = get_type_from_layer(layer)
                    key = (layer, comp_type, subtype)
                    comp_groups[key]["count"] += 1
                    comp_groups[key]["layer"] = layer
                    comp_groups[key]["type"] = comp_type
                    comp_groups[key]["subtype"] = subtype
                    comp_groups[key]["description"] = name

                # Skip TEXT/MTEXT entirely (no annotations in MTO)

            except Exception as inner_e:
                logger.warning(f"Skipping entity {t}: {inner_e}")
                continue

        # Build result list
        result = []

        # Pipes
        for (layer, size, schedule, material), data in pipe_groups.items():
            avg_len = round(data["total_len"] / data["count"], 1) if data["count"] > 0 else 0
            result.append({
                "type": "Pipe",
                "layer": layer,
                "size": size,
                "schedule": schedule,
                "material": material,
                "quantity": data["count"],
                "total_length": round(data["total_len"], 2),
                "description": f"Pipe, length ~{avg_len}"
            })

        # Components (blocks, flanges, elbows)
        for (layer, comp_type, subtype), data in comp_groups.items():
            result.append({
                "type": data["type"],
                "layer": layer,
                "size": data["subtype"],   # subtype goes into size column
                "schedule": "",
                "material": "",
                "quantity": data["count"],
                "total_length": 0,
                "description": data["description"]
            })

        return result

    except Exception as e:
        logger.error(f"DXF MTO error: {str(e)}", exc_info=True)
        raise Exception(f"DXF MTO error: {str(e)}")
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


# ----------------------------------------------------------------------
# Image / PDF MTO (placeholder – simple OCR, but we keep it minimal)
# ----------------------------------------------------------------------
def extract_mto_from_image(file_bytes):
    # This function is not used in typical MTO; we keep it for compatibility.
    return [{"type": "Info", "layer": "image", "size": "", "schedule": "", "material": "",
             "quantity": 0, "total_length": 0, "description": "Image MTO not supported"}]