import math
import io
import ezdxf
from ezdxf import recover
import tempfile
import os
import matplotlib.pyplot as plt
import numpy as np
import logging
from matplotlib.patches import Polygon as MplPolygon
import json

logger = logging.getLogger(__name__)

# Force matplotlib to use 'Agg' backend (no GUI)
import matplotlib
matplotlib.use('Agg')

# =====================================================================
# Shared projection (same as manual generator)
# =====================================================================
ANGLE_X =90
ANGLE_Z =90

def project_to_2d(x, y, z):
    rad_x = math.radians(ANGLE_X)
    rad_z = math.radians(ANGLE_Z)
    u = x * math.cos(rad_x) + y * math.cos(rad_z)
    v = x * math.sin(rad_x) + y * math.sin(rad_z) + z
    return u, v

def rotate_z(x, y, z, angle_deg):
    rad = math.radians(angle_deg)
    x_rot = x * math.cos(rad) - y * math.sin(rad)
    y_rot = x * math.sin(rad) + y * math.cos(rad)
    return x_rot, y_rot, z

# =====================================================================
# Manual segments generator (for manual input mode)
# =====================================================================
def generate_from_segments(segments, rotation_deg=0):
    if not segments:
        raise ValueError("No segments provided")
    points_3d = [(0.0, 0.0, 0.0)]
    current = [0.0, 0.0, 0.0]
    fittings = []
    for seg in segments:
        direction = seg['dir'].lower()
        length = seg['length']
        if direction == 'x':
            current[0] += length
        elif direction == 'y':
            current[1] += length
        elif direction == 'z':
            current[2] += length
        pos = tuple(current)
        points_3d.append(pos)
        if 'fitting' in seg and seg['fitting']:
            fittings.append((pos, seg['fitting']))
    # Apply rotation
    points_3d_rot = [rotate_z(p[0], p[1], p[2], rotation_deg) for p in points_3d]
    fittings_rot = [(rotate_z(f[0][0], f[0][1], f[0][2], rotation_deg), f[1]) for f in fittings]
    points_2d = [project_to_2d(*p) for p in points_3d_rot]
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(f"Isometric (Rotation: {rotation_deg}°)")
    xs, ys = zip(*points_2d)
    ax.plot(xs, ys, 'b-', linewidth=2)
    for (x, y, z), fitting in fittings_rot:
        u, v = project_to_2d(x, y, z)
        if fitting == 'flange':
            circle = plt.Circle((u, v), 5, color='red', fill=False, linewidth=1.5)
            ax.add_patch(circle)
            ax.text(u+3, v+3, 'FLG', fontsize=6, color='red')
        elif fitting == 'elbow':
            ax.plot(u, v, 'ro', markersize=4)
            ax.text(u+3, v+3, 'ELBOW', fontsize=6, color='orange')
        else:
            ax.plot(u, v, 'ko', markersize=3)
            ax.text(u+3, v+3, fitting.upper(), fontsize=6)
    for i in range(len(points_2d)-1):
        x1, y1 = points_2d[i]
        x2, y2 = points_2d[i+1]
        mx, my = (x1+x2)/2, (y1+y2)/2
        length = segments[i]['length']
        ax.text(mx, my+2, f"{length}m", ha='center', fontsize=8, color='gray')
    xs_all, ys_all = zip(*points_2d)
    margin = 5
    ax.set_xlim(min(xs_all) - margin, max(xs_all) + margin)
    ax.set_ylim(min(ys_all) - margin, max(ys_all) + margin)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    return buf.getvalue()

# =====================================================================
# DXF Isometric generator with block explosion and MESH support
# =====================================================================
class GeometryExtractor:
    @staticmethod
    def to_vec3(p):
        if isinstance(p, (tuple, list)):
            if len(p) >= 3:
                return (p[0], p[1], p[2])
            elif len(p) == 2:
                return (p[0], p[1], 0)
            else:
                return (p[0], 0, 0)
        if hasattr(p, 'x') and hasattr(p, 'y'):
            z = getattr(p, 'z', 0)
            return (p.x, p.y, z)
        return (0, 0, 0)
    
    @staticmethod
    def extract_line(entity):
        start = GeometryExtractor.to_vec3(entity.dxf.start)
        end = GeometryExtractor.to_vec3(entity.dxf.end)
        return {'type': 'line', 'points': [start, end], 'color': 'blue'}
    
    @staticmethod
    def extract_polyline(entity):
        points = []
        if hasattr(entity, 'vertices'):
            points = [GeometryExtractor.to_vec3(v) for v in entity.vertices()]
        elif hasattr(entity, 'get_points'):
            points = [GeometryExtractor.to_vec3(p) for p in entity.get_points()]
        is_closed = getattr(entity, 'closed', False)
        return {'type': 'polyline', 'points': points, 'closed': is_closed, 'color': 'blue'}
    
    @staticmethod
    def extract_circle(entity, segments=32):
        center = GeometryExtractor.to_vec3(entity.dxf.center)
        radius = entity.dxf.radius
        points = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            z = center[2]
            points.append((x, y, z))
        return {'type': 'circle', 'points': points, 'closed': True, 'color': 'blue'}
    
    @staticmethod
    def extract_arc(entity, segments=24):
        center = GeometryExtractor.to_vec3(entity.dxf.center)
        radius = entity.dxf.radius
        start_angle = math.radians(entity.dxf.start_angle)
        end_angle = math.radians(entity.dxf.end_angle)
        points = []
        for i in range(segments + 1):
            angle = start_angle + (end_angle - start_angle) * i / segments
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            z = center[2]
            points.append((x, y, z))
        return {'type': 'arc', 'points': points, 'closed': False, 'color': 'blue'}
    
    @staticmethod
    def extract_ellipse(entity, segments=32):
        center = GeometryExtractor.to_vec3(entity.dxf.center)
        major_axis = entity.dxf.major_axis
        ratio = entity.dxf.ratio
        a = math.sqrt(major_axis.x**2 + major_axis.y**2)
        b = a * ratio
        angle = math.atan2(major_axis.y, major_axis.x)
        points = []
        for i in range(segments):
            t = 2 * math.pi * i / segments
            x_ellipse = a * math.cos(t)
            y_ellipse = b * math.sin(t)
            x_rot = x_ellipse * math.cos(angle) - y_ellipse * math.sin(angle)
            y_rot = x_ellipse * math.sin(angle) + y_ellipse * math.cos(angle)
            x = center[0] + x_rot
            y = center[1] + y_rot
            z = center[2]
            points.append((x, y, z))
        return {'type': 'ellipse', 'points': points, 'closed': True, 'color': 'blue'}
    
    @staticmethod
    def extract_3dface(entity):
        points = [
            GeometryExtractor.to_vec3(entity.dxf.vtx0),
            GeometryExtractor.to_vec3(entity.dxf.vtx1),
            GeometryExtractor.to_vec3(entity.dxf.vtx2),
            GeometryExtractor.to_vec3(entity.dxf.vtx3),
        ]
        if points[-1] == points[-2]:
            points = points[:-1]
        return {'type': 'face', 'points': points, 'color': 'cyan', 'alpha': 0.3}
    
    @staticmethod
    def extract_spline(entity):
        points = [GeometryExtractor.to_vec3(p) for p in entity.control_points()]
        return {'type': 'spline', 'points': points, 'color': 'blue'}
    
    @staticmethod
    def extract_mesh(entity):
        vertices = entity.vertices
        faces = entity.faces
        geometries = []
        for face in faces:
            face_pts = []
            for idx in face:
                v = vertices[idx]
                face_pts.append(GeometryExtractor.to_vec3(v))
            if len(face_pts) < 3:
                continue
            for i in range(len(face_pts)):
                p1 = face_pts[i]
                p2 = face_pts[(i+1) % len(face_pts)]
                geometries.append({'type': 'line', 'points': [p1, p2], 'color': 'blue'})
        return geometries
    
    @staticmethod
    def extract_insert(entity):
        block_def = entity.doc.blocks.get(entity.dxf.name)
        if not block_def:
            return []
        
        insert = entity.dxf.insert
        rot = math.radians(entity.dxf.rotation if hasattr(entity.dxf, 'rotation') else 0)
        def apply_transform(p):
            v = GeometryExtractor.to_vec3(p)
            xr = v[0] * math.cos(rot) - v[1] * math.sin(rot)
            yr = v[0] * math.sin(rot) + v[1] * math.cos(rot)
            return (xr + insert.x, yr + insert.y, v[2] + (insert.z if hasattr(insert, 'z') else 0))
        
        geometries = []
        for sub_entity in block_def:
            geoms = GeometryExtractor._extract_entity_with_transform(sub_entity, apply_transform)
            if geoms:
                if isinstance(geoms, list):
                    geometries.extend(geoms)
                else:
                    geometries.append(geoms)
        return geometries
    
    @staticmethod
    def _extract_entity_with_transform(entity, transform_func):
        ent_type = entity.dxftype()
        try:
            if ent_type == 'LINE':
                geom = GeometryExtractor.extract_line(entity)
                geom['points'] = [transform_func(p) for p in geom['points']]
                return [geom]
            elif ent_type in ('LWPOLYLINE', 'POLYLINE'):
                geom = GeometryExtractor.extract_polyline(entity)
                geom['points'] = [transform_func(p) for p in geom['points']]
                return [geom]
            elif ent_type == 'CIRCLE':
                geom = GeometryExtractor.extract_circle(entity)
                geom['points'] = [transform_func(p) for p in geom['points']]
                return [geom]
            elif ent_type == 'ARC':
                geom = GeometryExtractor.extract_arc(entity)
                geom['points'] = [transform_func(p) for p in geom['points']]
                return [geom]
            elif ent_type == 'ELLIPSE':
                geom = GeometryExtractor.extract_ellipse(entity)
                geom['points'] = [transform_func(p) for p in geom['points']]
                return [geom]
            elif ent_type == '3DFACE':
                geom = GeometryExtractor.extract_3dface(entity)
                geom['points'] = [transform_func(p) for p in geom['points']]
                return [geom]
            elif ent_type == 'SPLINE':
                geom = GeometryExtractor.extract_spline(entity)
                geom['points'] = [transform_func(p) for p in geom['points']]
                return [geom]
            elif ent_type == 'MESH':
                geoms = GeometryExtractor.extract_mesh(entity)
                for g in geoms:
                    g['points'] = [transform_func(p) for p in g['points']]
                return geoms
            elif ent_type == 'INSERT':
                return GeometryExtractor._extract_insert_with_transform(entity, transform_func)
            else:
                return None
        except Exception as e:
            logger.warning(f"Error extracting {ent_type}: {e}")
            return None
    
    @staticmethod
    def _extract_insert_with_transform(entity, transform_func):
        block_def = entity.doc.blocks.get(entity.dxf.name)
        if not block_def:
            return []
        insert = entity.dxf.insert
        rot = math.radians(entity.dxf.rotation if hasattr(entity.dxf, 'rotation') else 0)
        def combined_transform(p):
            v = GeometryExtractor.to_vec3(p)
            xr = v[0] * math.cos(rot) - v[1] * math.sin(rot)
            yr = v[0] * math.sin(rot) + v[1] * math.cos(rot)
            return transform_func((xr + insert.x, yr + insert.y, v[2] + (insert.z if hasattr(insert, 'z') else 0)))
        geometries = []
        for sub_entity in block_def:
            geoms = GeometryExtractor._extract_entity_with_transform(sub_entity, combined_transform)
            if geoms:
                if isinstance(geoms, list):
                    geometries.extend(geoms)
                else:
                    geometries.append(geoms)
        return geometries
    
    @staticmethod
    def extract_entity(entity):
        ent_type = entity.dxftype()
        if ent_type == 'INSERT':
            geoms = GeometryExtractor.extract_insert(entity)
            return geoms
        else:
            geoms = GeometryExtractor._extract_entity_with_transform(entity, lambda p: p)
            return geoms

# =====================================================================
# Isometric Generator class
# =====================================================================
class IsometricGenerator:
    def __init__(self):
        self.geometries = []
    
    def load_dxf(self, file_bytes):
        self.geometries = []
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            try:
                doc = recover.read(tmp_path)[0]
            except:
                doc = ezdxf.readfile(tmp_path)
            msp = doc.modelspace()
            entity_types = {}
            for entity in msp:
                ent_type = entity.dxftype()
                entity_types[ent_type] = entity_types.get(ent_type, 0) + 1
            logger.info(f"Entity types: {entity_types}")
            geometry_count = 0
            for entity in msp:
                geoms = GeometryExtractor.extract_entity(entity)
                if geoms:
                    if isinstance(geoms, list):
                        self.geometries.extend(geoms)
                        geometry_count += len(geoms)
                    else:
                        self.geometries.append(geoms)
                        geometry_count += 1
            logger.info(f"Extracted {geometry_count} geometry objects (after block explosion)")
            return len(self.geometries) > 0
        finally:
            os.unlink(tmp_path)
    
    def render_to_png(self, rotation_deg=0):
        if not self.geometries:
            return self._render_empty_message("No wireframe geometry found.")
        try:
            fig, ax = plt.subplots(figsize=(14, 10), dpi=120)
            ax.set_aspect('equal')
            ax.axis('off')
            ax.set_title(f"Isometric from DXF (Rotation: {rotation_deg}°)", fontsize=14)
            all_2d_points = []
            for geom in self.geometries:
                points_3d = geom.get('points', [])
                if not points_3d:
                    continue
                points_3d_rot = [rotate_z(p[0], p[1], p[2], rotation_deg) for p in points_3d]
                points_2d = [project_to_2d(*p) for p in points_3d_rot]
                all_2d_points.extend(points_2d)
                color = geom.get('color', 'blue')
                alpha = geom.get('alpha', 1.0)
                geom_type = geom.get('type', 'unknown')
                if geom_type in ('line', 'polyline', 'circle', 'arc', 'spline', 'ellipse'):
                    xs, ys = zip(*points_2d)
                    if geom.get('closed', False):
                        ax.plot(list(xs) + [xs[0]], list(ys) + [ys[0]], color=color, linewidth=2, alpha=alpha)
                    else:
                        ax.plot(xs, ys, color=color, linewidth=2, alpha=alpha)
                elif geom_type == 'face':
                    if len(points_2d) >= 3:
                        polygon = MplPolygon(points_2d, closed=True, facecolor=color, edgecolor='darkblue',
                                             alpha=alpha, linewidth=1.5)
                        ax.add_patch(polygon)
            if all_2d_points:
                xs, ys = zip(*all_2d_points)
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)
                x_range = x_max - x_min if x_max != x_min else 100
                y_range = y_max - y_min if y_max != y_min else 100
                padding_x = x_range * 0.1
                padding_y = y_range * 0.1
                ax.set_xlim(x_min - padding_x, x_max + padding_x)
                ax.set_ylim(y_min - padding_y, y_max + padding_y)
            ax.grid(True, alpha=0.2, linestyle='--')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Rendering error: {e}", exc_info=True)
            return self._render_empty_message(f"Rendering error: {str(e)}")
    
    def _render_empty_message(self, message):
        fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
        ax.axis('off')
        ax.text(0.5, 0.5, message, ha='center', va='center', transform=ax.transAxes,
                fontsize=12, color='red', fontweight='bold')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    
    def get_polylines(self):
        polylines = []
        for geom in self.geometries:
            points = geom.get('points', [])
            if len(points) < 2:
                continue
            polyline = []
            for p in points:
                polyline.append([p[0], p[1], p[2]])
            if geom.get('closed', False) and len(points) > 2:
                # Close the polyline by adding the first point again
                polyline.append(polyline[0])
            polylines.append(polyline)
        return polylines

# =====================================================================
# Manual segment generator for 3D viewer
# =====================================================================
def generate_segments_from_manual(segments_list):
    """Generate 3D line segments and fitting markers from manual input."""
    if not segments_list:
        return {"segments": [], "fittings": []}
    
    points_3d = [(0.0, 0.0, 0.0)]
    current = [5.0, 0.0, 5.0]
    fittings = []
    
    for seg in segments_list:
        direction = seg['dir'].lower()
        length = seg['length']
        if direction == 'x':
            current[0] += length
        elif direction == 'y':
            current[1] += length
        elif direction == 'z':
            current[2] += length
        pos = tuple(current)
        points_3d.append(pos)
        if 'fitting' in seg and seg['fitting']:
            fittings.append({"pos": pos, "type": seg['fitting']})
    
    # Build line segments
    segments = []
    for i in range(len(points_3d)-1):
        p1 = points_3d[i]
        p2 = points_3d[i+1]
        segments.append([p1[0], p1[1], p1[2], p2[0], p2[1], p2[2]])
    
    return {"segments": segments, "fittings": fittings}
def extract_segments_from_dxf(file_bytes):
    """Extract 3D line segments from DXF as JSON-serializable list."""
    generator = IsometricGenerator()
    if not generator.load_dxf(file_bytes):
        return []
    return generator.get_segments()

# =====================================================================
# Main entry point for PNG generation
# =====================================================================
def generate_isometric(file_bytes=None, segments=None, rotation_deg=0):
    if file_bytes:
        generator = IsometricGenerator()
        if not generator.load_dxf(file_bytes):
            return generator._render_empty_message("No wireframe geometry found.")
        return generator.render_to_png(rotation_deg)
    elif segments:
        return generate_from_segments(segments, rotation_deg)
    else:
        raise ValueError("Either file_bytes or segments must be provided")