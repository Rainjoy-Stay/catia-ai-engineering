"""Actual shared circle-wire evidence independent of surface parameterization."""
import math
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire
from OCP.GeomAbs import GeomAbs_Circle
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopTools import TopTools_ListOfShape
from OCP.TopoDS import TopoDS
from catia_checker.occt_brep import _subshapes

def shared_section_boundary(model,seed,torus_face_ids,section_normal,tolerance_mm=1e-5):
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0: raise ValueError('Invalid tolerance')
    if len(section_normal)!=3 or not all(math.isfinite(v) for v in section_normal) or abs(sum(v*v for v in section_normal)-1)>1e-7:
        raise ValueError('Invalid section normal')
    edges=[]
    for fid in torus_face_ids:
        for edge in _subshapes(model._shape(fid),TopAbs_EDGE):
            if not any(edge.IsSame(e) for e in edges): edges.append(edge)
    cylinders=[e for fid in seed['cylinder_face_ids'] for e in _subshapes(model._shape(fid),TopAbs_EDGE)]
    matched=[]; span=0; curves=[]
    for edge in edges:
        if not any(edge.IsSame(e) for e in cylinders): continue
        curve=BRepAdaptor_Curve(TopoDS.Edge_s(edge)); item={'curve_type':str(curve.GetType()),'matches_target_section':False}
        if curve.GetType()==GeomAbs_Circle:
            circle=curve.Circle(); center=circle.Location(); axis=circle.Axis().Direction()
            distance=math.dist([center.X(),center.Y(),center.Z()],seed['support_tangent_point_mm'])
            alignment=abs(sum(a*b for a,b in zip([axis.X(),axis.Y(),axis.Z()],section_normal)))
            angle=abs(curve.LastParameter()-curve.FirstParameter())
            match=distance<=tolerance_mm and abs(circle.Radius()-seed['section_radius_mm'])<=tolerance_mm and abs(alignment-1)<=1e-8
            item.update(radius_mm=circle.Radius(),center_error_mm=distance,normal_alignment=alignment,span_rad=angle,matches_target_section=match)
            if match: matched.append(edge); span+=angle
        curves.append(item)
    closed=False
    if matched:
        items=TopTools_ListOfShape()
        for edge in matched: items.Append(edge)
        builder=BRepBuilderAPI_MakeWire(); builder.Add(items)
        if builder.IsDone():
            wire=builder.Wire(); closed=wire.Closed() and len(_subshapes(wire,TopAbs_EDGE))==len(matched)
    complete=closed and math.isclose(span,2*math.pi,rel_tol=1e-6,abs_tol=1e-6)
    partial=bool(matched) and len(matched)==len(curves) and not closed and 0<span<2*math.pi-1e-6
    classification='COMPLETE_LOCAL_SHARED_CIRCLE' if complete else ('ANALYTIC_PARTIAL_OPEN_SECTION' if partial else 'UNRESOLVED_BOUNDARY')
    return {'status':'NOT_EVALUATED','shared_boundary_curves':curves,'matched_circle_edge_count':len(matched),
        'matched_span_rad':span,'boundary_wire_closed':closed,
        'complete_boundary_circle_verified':complete,'boundary_evidence_class':classification,
        'quarter_circle_only':partial and math.isclose(span,math.pi/2,rel_tol=1e-6,abs_tol=1e-6),
        'eligible_for_centerline_continuation_test':complete,
        'trim_coverage_confirmed':False,'centerline_reconstructed':False,'engineering_pipe_confirmed':False,
        'design_cavity_confirmed':False,'limits':'Closed local shared circle only; no UV equivalence, surface role or route proof'}
