import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import math
from app.cad_engine import (
    detect_offset_voting, shift_entities, estimate_proximity, compare_dxf,
    shape_key_round, approx_eq, polyline_fingerprint, bbox,
    text_similarity
)

# ----------------------------------------------------------------------
# Tests: offset detection (voting)
# ----------------------------------------------------------------------
def test_offset_voting():
    ea = [
        {'type':'LINE', 'shape_key':'LINE|len=10.0|ang=0.0|layer=0', 'cx':5, 'cy':0},
        {'type':'LINE', 'shape_key':'LINE|len=10.0|ang=0.0|layer=0', 'cx':15, 'cy':0}
    ]
    eb = [
        {'type':'LINE', 'shape_key':'LINE|len=10.0|ang=0.0|layer=0', 'cx':55, 'cy':10},
        {'type':'LINE', 'shape_key':'LINE|len=10.0|ang=0.0|layer=0', 'cx':65, 'cy':10}
    ]
    dx, dy = detect_offset_voting(ea, eb)
    assert approx_eq(dx, 50) and approx_eq(dy, 10)

def test_offset_voting_no_common_shape():
    ea = [{'type':'LINE', 'shape_key':'LINE|len=10.0|ang=0.0|layer=0', 'cx':5, 'cy':0}]
    eb = [{'type':'CIRCLE', 'shape_key':'CIRCLE|r=5.0|layer=0', 'cx':10, 'cy':0}]
    dx, dy = detect_offset_voting(ea, eb)
    assert dx == 0 and dy == 0

# ----------------------------------------------------------------------
# Tests: proximity estimation (with offset detection)
# ----------------------------------------------------------------------
def test_estimate_proximity():
    # Two lines with same shape_key, shifted by 2 units.
    # The offset detection will find that shift, shift the input, and then the distance becomes 0.
    ea = [{'type':'LINE', 'shape_key':'L1', 'cx':0, 'cy':0}]
    eb = [{'type':'LINE', 'shape_key':'L1', 'cx':2, 'cy':0}]
    prox = estimate_proximity(ea, eb)
    # After offset detection, the residual distance is 0.
    assert approx_eq(prox, 0.0)

# ----------------------------------------------------------------------
# Tests: shift_entities
# ----------------------------------------------------------------------
def test_shift_entities():
    ents = [{'cx':10, 'cy':20, 'bbox':(0,0,10,10)}]
    shifted = shift_entities(ents, 5, -5)
    assert shifted[0]['cx'] == 15
    assert shifted[0]['cy'] == 15
    assert shifted[0]['bbox'] == (5,-5,15,5)

# ----------------------------------------------------------------------
# Tests: compare_dxf (matching and classification)
# ----------------------------------------------------------------------
def test_compare_dxf_identical():
    ea = [{'type':'LINE','shape_key':'L1','cx':0,'cy':0,'bbox':(0,0,10,0)}]
    eb = [{'type':'LINE','shape_key':'L1','cx':0,'cy':0,'bbox':(0,0,10,0)}]
    diff, _ = compare_dxf(ea, eb, [])
    assert diff['moved'] == []
    assert diff['modified'] == []
    assert diff['missing'] == []
    assert diff['added'] == []

def test_compare_dxf_moved():
    # Use two entities: one stationary (same position) to anchor the offset,
    # and one moved. The global offset will be 0 because the stationary pair matches.
    ea = [
        {'type':'LINE','shape_key':'L1','cx':0,'cy':0,'bbox':(0,0,10,0)},
        {'type':'LINE','shape_key':'L2','cx':0,'cy':0,'bbox':(0,0,10,0)}
    ]
    eb = [
        {'type':'LINE','shape_key':'L1','cx':0,'cy':0,'bbox':(0,0,10,0)},
        {'type':'LINE','shape_key':'L2','cx':5,'cy':5,'bbox':(5,5,15,5)}
    ]
    diff, _ = compare_dxf(ea, eb, [])
    # The second line should be flagged as moved.
    assert len(diff['moved']) == 1
    assert 'Moved' in diff['moved'][0]['label']

def test_compare_dxf_modified_text():
    ea = [{'type':'TEXT','shape_key':'TEXT|txt=HELLO|layer=0','txt':'HELLO','norm_txt':'HELLO','cx':0,'cy':0}]
    eb = [{'type':'TEXT','shape_key':'TEXT|txt=WORLD|layer=0','txt':'WORLD','norm_txt':'WORLD','cx':0,'cy':0}]
    diff, _ = compare_dxf(ea, eb, [])
    assert len(diff['modified']) == 1
    assert 'Text' in diff['modified'][0]['label']

def test_compare_dxf_missing():
    ea = [{'type':'LINE','shape_key':'L1','cx':0,'cy':0,'bbox':(0,0,10,0)}]
    eb = []
    diff, _ = compare_dxf(ea, eb, [])
    assert len(diff['missing']) == 1

def test_compare_dxf_added():
    ea = []
    eb = [{'type':'LINE','shape_key':'L1','cx':0,'cy':0,'bbox':(0,0,10,0)}]
    diff, _ = compare_dxf(ea, eb, [])
    assert len(diff['added']) == 1

def test_compare_dxf_clash():
    ea = []
    eb = [
        {'type':'LINE','shape_key':'L1','cx':5,'cy':5,'bbox':(0,0,10,10)},
        {'type':'LINE','shape_key':'L2','cx':6,'cy':6,'bbox':(1,1,11,11)}
    ]
    diff, _ = compare_dxf(ea, eb, [])
    # Both are added; one will clash with the other
    assert len(diff['clashes']) >= 1

# ----------------------------------------------------------------------
# Tests: polyline fingerprint
# ----------------------------------------------------------------------
def test_polyline_fingerprint():
    pts = [(0,0), (10,0), (10,10), (0,10)]
    fp = polyline_fingerprint(pts, closed=True)
    closed, n, edges, angles = fp
    assert closed is True
    assert n == 4
    assert all(round(e,2) == 10.0 for e in edges)
    assert all(abs(a) == 90.0 for a in angles)

def test_polyline_fingerprint_different_start():
    pts1 = [(10,0), (10,10), (0,10), (0,0)]
    pts2 = [(0,0), (10,0), (10,10), (0,10)]
    fp1 = polyline_fingerprint(pts1, closed=True)
    fp2 = polyline_fingerprint(pts2, closed=True)
    assert fp1 == fp2

# ----------------------------------------------------------------------
# Tests: helper functions
# ----------------------------------------------------------------------
def test_bbox():
    pts = [(0,0), (10,5), (5,15)]
    xmin, ymin, xmax, ymax = bbox(pts)
    assert xmin == 0 and ymin == 0 and xmax == 10 and ymax == 15

def test_shape_key_round():
    assert shape_key_round(1.23456) == 1.235   # 3 decimal digits

def test_approx_eq():
    assert approx_eq(1.0001, 1.0002, tol=0.001)
    assert not approx_eq(1.0, 1.1, tol=0.05)

def test_text_similarity():
    assert text_similarity("HELLO", "HELLO") == 1.0
    assert text_similarity("Hello World", "Hello   World") > 0.9