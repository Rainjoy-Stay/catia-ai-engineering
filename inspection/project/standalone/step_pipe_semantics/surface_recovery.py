"""Canonical support recovery with independent sampled error; source faces unchanged."""
import math
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.GeomAdaptor import GeomAdaptor_Surface
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCP.GeomConvert import GeomConvert_SurfToAnaSurf
from OCP.GeomAbs import GeomAbs_BSplineSurface,GeomAbs_Cylinder,GeomAbs_Torus,GeomAbs_Plane,GeomAbs_Cone,GeomAbs_Sphere
from OCP.TopAbs import TopAbs_IN,TopAbs_ON
from OCP.TopoDS import TopoDS


def recover_surface_support(face,tolerance_mm=1e-5):
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0: raise ValueError('Invalid recovery tolerance')
    face=TopoDS.Face_s(face); adaptor=BRepAdaptor_Surface(face)
    result={'status':'NOT_EVALUATED','support_recovered':False,'engineering_pipe_confirmed':False,
            'design_cavity_confirmed':False,'wall_thickness_mm':None,'tolerance_mm':tolerance_mm,
            'method':'OCCT_CANONICAL_CONVERSION_WITH_INDEPENDENT_PROJECTION_SAMPLES'}
    if adaptor.GetType()!=GeomAbs_BSplineSurface: return {**result,'reason':'NOT_BSPLINE_SURFACE'}
    source=BRep_Tool.Surface_s(face); converter=GeomConvert_SurfToAnaSurf(source)
    u0,u1,v0,v1=adaptor.FirstUParameter(),adaptor.LastUParameter(),adaptor.FirstVParameter(),adaptor.LastVParameter()
    converted=converter.ConvertToAnalytical(tolerance_mm,u0,u1,v0,v1)
    if converted is None: return {**result,'reason':'CANONICAL_CONVERSION_UNAVAILABLE'}
    gap=float(converter.Gap()); result['kernel_gap_mm']=gap
    if not math.isfinite(gap) or gap<0 or gap>tolerance_mm: return {**result,'reason':'KERNEL_ERROR_EXCEEDS_LIMIT'}
    analytical=GeomAdaptor_Surface(converted)
    names={GeomAbs_Cylinder:'CYLINDER',GeomAbs_Torus:'TORUS',GeomAbs_Plane:'PLANE',GeomAbs_Cone:'CONE',GeomAbs_Sphere:'SPHERE'}
    kind=names.get(analytical.GetType())
    if not kind: return {**result,'reason':'UNSUPPORTED_CANONICAL_RESULT'}
    errors=[]
    for i in range(7):
        for j in range(7):
            point=source.Value(u0+(u1-u0)*(i+.5)/7,v0+(v1-v0)*(j+.5)/7)
            if BRepClass_FaceClassifier(face,point,tolerance_mm).State() not in (TopAbs_IN,TopAbs_ON): continue
            projection=GeomAPI_ProjectPointOnSurf(point,converted)
            if not projection.IsDone() or not projection.NbPoints():
                return {**result,'reason':'INDEPENDENT_PROJECTION_FAILED'}
            errors.append(projection.LowerDistance())
    result.update({'sample_count':len(errors),'maximum_sample_error_mm':max(errors) if errors else None})
    if len(errors)<9: return {**result,'reason':'INSUFFICIENT_IN_TRIM_SAMPLES'}
    if not all(math.isfinite(e) and e<=tolerance_mm for e in errors): return {**result,'reason':'SAMPLE_ERROR_EXCEEDS_LIMIT'}
    features={'surface_type':kind}
    axis=None
    if kind=='CYLINDER':
        cylinder=analytical.Cylinder(); axis=cylinder.Axis(); features['radius_mm']=cylinder.Radius()
    elif kind=='TORUS':
        torus=analytical.Torus(); axis=torus.Axis()
        features.update({'major_radius_mm':torus.MajorRadius(),'minor_radius_mm':torus.MinorRadius()})
    if axis is not None:
        point=axis.Location(); direction=axis.Direction()
        features.update({'axis_origin_mm':[point.X(),point.Y(),point.Z()],
                         'axis_direction':[direction.X(),direction.Y(),direction.Z()]})
    return {**result,'support_recovered':True,'recovered_support':features,
            'reason':'CANONICAL_SUPPORT_KERNEL_AND_SAMPLE_ERROR_WITHIN_LIMIT',
            'limits':'Support recovery does not change trims or topology and is not a global error proof or pipe classification'}
