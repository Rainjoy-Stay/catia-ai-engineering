"""Reassemble evidence on same-support torus faces without editing source shapes."""
import math
from OCP.BRepAdaptor import BRepAdaptor_Surface,BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.GeomAbs import GeomAbs_Torus,GeomAbs_Circle
from OCP.TopAbs import TopAbs_EDGE,TopAbs_IN,TopAbs_ON
from OCP.TopTools import TopTools_ListOfShape
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt
from catia_checker.occt_brep import _subshapes


def grouped_finite_route_evidence(model,seed,face_ids,tolerance_mm=1e-5,*,sample_only_complete_boundary=False):
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0: raise ValueError('Invalid tolerance')
    reference=BRepAdaptor_Surface(TopoDS.Face_s(model._shape(seed['torus_face_id']))).Torus()
    center=reference.Location(); normal=reference.Axis().Direction()
    origin=[center.X(),center.Y(),center.Z()]; axis=[normal.X(),normal.Y(),normal.Z()]
    R,r=reference.MajorRadius(),reference.MinorRadius()
    grouped=[]
    for fid in face_ids:
        adaptor=BRepAdaptor_Surface(TopoDS.Face_s(model._shape(fid)))
        if adaptor.GetType()!=GeomAbs_Torus: continue
        t=adaptor.Torus()
        if abs(t.MajorRadius()-R)<=tolerance_mm and abs(t.MinorRadius()-r)<=tolerance_mm and t.Location().Distance(center)<=tolerance_mm and abs(abs(t.Axis().Direction().Dot(normal))-1)<=1e-8:
            grouped.append(fid)
    edges=[]
    for fid in grouped:
        for edge in _subshapes(model._shape(fid),TopAbs_EDGE):
            if not any(edge.IsSame(e) for e in edges): edges.append(edge)
    cylinders=[]
    for fid in seed['cylinder_face_ids']:
        cylinders+=_subshapes(model._shape(fid),TopAbs_EDGE)
    matched=[]; span=0
    for edge in edges:
        if not any(edge.IsSame(e) for e in cylinders): continue
        curve=BRepAdaptor_Curve(TopoDS.Edge_s(edge))
        if curve.GetType()!=GeomAbs_Circle: continue
        circle=curve.Circle(); c=circle.Location()
        if abs(circle.Radius()-r)>tolerance_mm or math.dist([c.X(),c.Y(),c.Z()],seed['support_tangent_point_mm'])>tolerance_mm: continue
        matched.append(edge); span+=abs(curve.LastParameter()-curve.FirstParameter())
    closed=False
    if matched:
        items=TopTools_ListOfShape()
        for edge in matched: items.Append(edge)
        builder=BRepBuilderAPI_MakeWire(); builder.Add(items)
        if builder.IsDone():
            wire=builder.Wire()
            closed=wire.Closed() and len(_subshapes(wire,TopAbs_EDGE))==len(matched)
    complete=closed and math.isclose(span,2*math.pi,rel_tol=1e-6,abs_tol=1e-6)
    if sample_only_complete_boundary and not complete:
        return {'status':'NOT_EVALUATED','same_support_torus_face_ids':grouped,
            'matched_shared_circle_edge_count':len(matched),'matched_boundary_span_rad':span,
            'boundary_wire_closed':closed,'complete_boundary_circle_verified':False,
            'trim_coverage_samples':[],'sampled_full_section_continuation':None,
            'coverage_deferred_reason':'INCOMPLETE_BOUNDARY_ALREADY_PREVENTS_CANDIDATE',
            'local_grouped_route_candidate':False,'centerline_reconstructed':False,
            'engineering_pipe_confirmed':False,'design_cavity_confirmed':False,
            'limits':'Incomplete boundary rejects this local test; omitted coverage samples do not claim absent surface'}
    radial=[(seed['support_tangent_point_mm'][i]-origin[i])/R for i in range(3)]
    tangent=[axis[1]*radial[2]-axis[2]*radial[1],axis[2]*radial[0]-axis[0]*radial[2],axis[0]*radial[1]-axis[1]*radial[0]]
    coverage=[]
    for sign in (-1,1):
        covered=0; total=0
        for offset in (.01,.05,.1):
            u=sign*offset
            direction=[math.cos(u)*radial[i]+math.sin(u)*tangent[i] for i in range(3)]
            for j in range(24):
                v=2*math.pi*j/24; total+=1
                point=[origin[i]+(R+r*math.cos(v))*direction[i]+r*math.sin(v)*axis[i] for i in range(3)]
                if any(BRepClass_FaceClassifier(TopoDS.Face_s(model._shape(fid)),gp_Pnt(*point),tolerance_mm).State() in (TopAbs_IN,TopAbs_ON) for fid in grouped): covered+=1
        coverage.append({'continuation_sign':sign,'covered_sample_count':covered,'sample_count':total})
    sampled=any(c['covered_sample_count']==c['sample_count'] for c in coverage)
    return {'status':'NOT_EVALUATED','same_support_torus_face_ids':grouped,
        'matched_shared_circle_edge_count':len(matched),'matched_boundary_span_rad':span,
        'boundary_wire_closed':closed,'complete_boundary_circle_verified':complete,
        'trim_coverage_samples':coverage,'sampled_full_section_continuation':sampled,
        'local_grouped_route_candidate':complete and sampled,'centerline_reconstructed':False,
        'engineering_pipe_confirmed':False,'design_cavity_confirmed':False,
        'limits':'Shared closed circle is checked topologically; continuation coverage is sampled, not a global trim or route proof'}
