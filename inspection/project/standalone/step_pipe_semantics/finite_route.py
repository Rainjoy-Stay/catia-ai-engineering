"""Finite boundary validation; partial fillet faces cannot confirm tube centerlines."""
import math
from OCP.BRepAdaptor import BRepAdaptor_Curve,BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Circle,GeomAbs_Torus
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from catia_checker.occt_brep import _subshapes


def finite_route_evidence(model,seed,tolerance_mm=1e-5):
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0: raise ValueError('Invalid tolerance')
    result={'status':'NOT_EVALUATED','centerline_reconstructed':False,
            'engineering_pipe_confirmed':False,'design_cavity_confirmed':False}
    torus=model._shape(seed['torus_face_id'])
    adaptor=BRepAdaptor_Surface(TopoDS.Face_s(torus))
    if adaptor.GetType()!=GeomAbs_Torus:
        return {**result,'reason':'FINITE_TORUS_PARAMETERS_UNAVAILABLE'}
    bounds=[adaptor.FirstUParameter(),adaptor.LastUParameter(),adaptor.FirstVParameter(),adaptor.LastVParameter()]
    result['torus_uv_bounds']=bounds
    result['torus_cross_section_span_rad']=bounds[3]-bounds[2]
    shared=[]; torus_edges=_subshapes(torus,TopAbs_EDGE)
    for fid in seed.get('shared_edge_cylinder_face_ids',[]):
        for edge in _subshapes(model._shape(fid),TopAbs_EDGE):
            if any(edge.IsSame(t) for t in torus_edges) and not any(edge.IsSame(e) for e in shared): shared.append(edge)
    curves=[]; spans=[]
    for edge in shared:
        curve=BRepAdaptor_Curve(TopoDS.Edge_s(edge))
        item={'curve_type':str(curve.GetType())}
        if curve.GetType()==GeomAbs_Circle:
            circle=curve.Circle(); center=circle.Location()
            xyz=[center.X(),center.Y(),center.Z()]
            span=abs(curve.LastParameter()-curve.FirstParameter())
            item.update({'radius_mm':circle.Radius(),'center_mm':xyz,'span_rad':span,
                         'center_distance_to_support_tangency_mm':math.dist(xyz,seed['support_tangent_point_mm'])})
            matched=abs(circle.Radius()-seed['section_radius_mm'])<=tolerance_mm and item['center_distance_to_support_tangency_mm']<=tolerance_mm
            item['matches_target_cross_section']=matched
            if matched: spans.append(span)
        curves.append(item)
    result['shared_boundary_curves']=curves
    result['complete_boundary_circle_verified']=bool(curves) and len(spans)==len(curves) and math.isclose(sum(spans),2*math.pi,rel_tol=1e-6,abs_tol=1e-6)
    result['complete_torus_cross_section_envelope']=math.isclose(bounds[3]-bounds[2],2*math.pi,rel_tol=1e-6,abs_tol=1e-6)
    result['local_full_section_route_candidate']=result['complete_boundary_circle_verified'] and result['complete_torus_cross_section_envelope']
    result['reason']=('FULL_SECTION_LOCAL_JOIN_NEEDS_WHOLE_ROUTE_AND_SURFACE_ROLE' if result['local_full_section_route_candidate']
                      else 'SHARED_BOUNDARY_OR_TORUS_SECTION_INCOMPLETE_FOR_ROUTE')
    result['limits']='UV bounds describe an envelope, not trim coverage; a local join never confirms a complete route or cavity'
    return result
