"""Conservative centerline recovery for circular B-spline sweep exteriors."""
import math

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt, gp_Vec


def _distance(a, b):
    return math.dist((a.X(), a.Y(), a.Z()), (b.X(), b.Y(), b.Z()))


def bspline_circular_sweep_candidate(shape, solid, faces, tolerance_mm=1e-5, samples=2001):
    """Recover a centerline only from a verified four-face circular sweep solid.

    The supported topology is two equal planar disk caps plus two B-spline side
    faces bounded by a pair of antipodal longitudinal seam edges.  Midpoints of
    those seams form the circular-section centerline.  No hollow bore or
    engineering pipe intent is inferred.
    """
    base = {'schema_version': 'step-exterior-candidate.v0.3',
            'solid_id': solid.get('shape_id'), 'status': 'NOT_EVALUATED',
            'geometry_kind': 'UNDETERMINED', 'ports': [],
            'wall_thickness_mm': None, 'engineering_pipe_confirmed': False,
            'design_cavity_confirmed': False, 'fluid_channel_confirmed': False,
            'bend_radius_compliance': 'NOT_EVALUATED'}
    def reject(reason): return {**base, 'reason': reason}
    if shape is None or solid.get('valid') is not True or solid.get('solid_count') != 1:
        return reject('REQUIRES_EXACT_VALID_SINGLE_SOLID_SHAPE')
    features = [face.get('surface_features') or {} for face in faces]
    planes = [item for item in features if item.get('surface_type') == 'PLANE']
    bsplines = [item for item in features if item.get('surface_type') == 'BSPLINE']
    if len(faces) != 4 or len(planes) != 2 or len(bsplines) != 2:
        return reject('REQUIRES_TWO_BSPLINE_SIDES_AND_TWO_PLANAR_CAPS')
    cap_areas = [float(item.get('area_mm2', 0)) for item in planes]
    # STEP B-spline cap integration can differ slightly after translation; the
    # antipodal end-edge check below remains the stronger geometric guard.
    if min(cap_areas) <= 0 or not math.isclose(*cap_areas, rel_tol=5e-4, abs_tol=1e-8):
        return reject('UNEQUAL_OR_INVALID_CIRCULAR_CAP_AREAS')
    diameter = 2 * math.sqrt(sum(cap_areas) / (2 * math.pi))
    edge_map = TopTools_IndexedMapOfShape(); TopExp.MapShapes_s(shape, TopAbs_EDGE, edge_map)
    curves = []
    for index in range(1, edge_map.Extent() + 1):
        curve = BRepAdaptor_Curve(TopoDS.Edge_s(edge_map.FindKey(index)))
        first, last = curve.FirstParameter(), curve.LastParameter()
        length = GCPnts_AbscissaPoint.Length_s(curve, first, last)
        curves.append((length, curve, first, last))
    if len(curves) != 6:
        return reject('EXPECTED_SIX_UNIQUE_EDGES')
    a, b = sorted(curves, key=lambda item: -item[0])[:2]
    length_a, curve_a, first_a, last_a = a
    length_b, curve_b, first_b, last_b = b
    if min(length_a, length_b) <= 4 * diameter:
        return reject('LONGITUDINAL_EDGES_TOO_SHORT')
    a0, a1 = curve_a.Value(first_a), curve_a.Value(last_a)
    b0, b1 = curve_b.Value(first_b), curve_b.Value(last_b)
    reverse_b = _distance(a0, b1) + _distance(a1, b0) < _distance(a0, b0) + _distance(a1, b1)
    end_separations = [_distance(a0, b1 if reverse_b else b0),
                       _distance(a1, b0 if reverse_b else b1)]
    end_tolerance = max(0.01, 0.03 * diameter)
    if max(abs(value - diameter) for value in end_separations) > end_tolerance:
        return reject('ANTIPODAL_EDGE_PAIR_NOT_CONFIRMED')
    radii = []
    for index in range(1, samples - 1):
        fraction = index / (samples - 1)
        ua = first_a + (last_a - first_a) * fraction
        ub = (last_b - (last_b-first_b)*fraction if reverse_b
              else first_b + (last_b-first_b)*fraction)
        pa, da1, da2, pb, db1, db2 = gp_Pnt(), gp_Vec(), gp_Vec(), gp_Pnt(), gp_Vec(), gp_Vec()
        curve_a.D2(ua, pa, da1, da2); curve_b.D2(ub, pb, db1, db2)
        d1 = ((da1.X()+db1.X())/2, (da1.Y()+db1.Y())/2, (da1.Z()+db1.Z())/2)
        d2 = ((da2.X()+db2.X())/2, (da2.Y()+db2.Y())/2, (da2.Z()+db2.Z())/2)
        cross = (d1[1]*d2[2]-d1[2]*d2[1], d1[2]*d2[0]-d1[0]*d2[2], d1[0]*d2[1]-d1[1]*d2[0])
        denominator = math.sqrt(sum(value*value for value in cross))
        if denominator > 1e-12:
            radii.append(((sum(value*value for value in d1))**1.5/denominator, fraction))
    if not radii:
        return reject('CENTERLINE_CURVATURE_UNAVAILABLE')
    minimum_radius, location = min(radii)
    return {**base, 'geometry_kind': 'BSPLINE_CIRCULAR_SWEEP_EXTERIOR_CANDIDATE',
            'reason': 'ANTIPODAL_SEAMS_EQUAL_DISK_CAPS_AND_CURVATURE_VERIFIED',
            'outer_diameter_mm': diameter,
            'centerline_bend_radius_mm': minimum_radius,
            'minimum_radius_ratio_r_over_d': minimum_radius/diameter,
            'minimum_curvature_location_fraction': location,
            'centerline_length_mm': (length_a+length_b)/2,
            'end_antipodal_separations_mm': end_separations,
            'centerline_reconstruction_method': 'MIDPOINT_OF_ANTIPODAL_BSPLINE_SEAMS_D2',
            'face_ids': [face.get('shape_id') for face in faces],
            'limits': 'Exterior sweep may be a solid rod; no cavity, wall thickness, port, material or forming process is inferred'}
