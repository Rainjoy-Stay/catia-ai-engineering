"""Tube-like exterior candidates; solid rods remain indistinguishable by intent."""
import math
from . import _cylinder_groups
from .bspline_sweep import bspline_circular_sweep_candidate


def straight_exterior_candidate(solid, faces, tolerance_mm=1e-5):
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0: raise ValueError('Invalid tolerance')
    result={'schema_version':'step-exterior-candidate.v0.1','solid_id':solid.get('shape_id'),
            'status':'NOT_EVALUATED','geometry_kind':'UNDETERMINED',
            'engineering_pipe_confirmed':False,'design_cavity_confirmed':False,
            'wall_thickness_mm':None,'fluid_channel_confirmed':False,'ports':[]}
    def reject(reason): return {**result,'reason':reason}
    if solid.get('valid') is not True or solid.get('solid_count')!=1:
        return reject('REQUIRES_VALID_SINGLE_SOLID')
    ids=[f.get('shape_id') for f in faces]
    if solid.get('face_count')!=len(faces) or not all(ids) or len(set(ids))!=len(ids) or any(f.get('valid') is not True or 'EXACT_BREP' not in f.get('capabilities',[]) for f in faces):
        return reject('INCOMPLETE_OR_INVALID_FACE_EVIDENCE')
    cylinders=[f for f in faces if (f.get('surface_features') or {}).get('surface_type')=='CYLINDER']
    planes=[f['surface_features'] for f in faces if (f.get('surface_features') or {}).get('surface_type')=='PLANE']
    if len(planes)!=2 or len(cylinders)+2!=len(faces):
        return reject('COMPOSITE_EXTERIOR_REQUIRES_ROUTE_REVIEW')
    try:
        groups=_cylinder_groups(cylinders,tolerance_mm)
        if not groups: return reject('NO_CYLINDRICAL_ENVELOPE')
        outer=max(groups,key=lambda g:g['radius_mm']); radius=outer['radius_mm']
        axis=outer['axis_direction']; origin=outer['axis_origin_mm']
        def dot(a,b): return sum(x*y for x,y in zip(a,b))
        def norm(v): return math.sqrt(dot(v,v))
        def off_axis(point):
            d=[point[i]-origin[i] for i in range(3)]; z=dot(d,axis)
            return norm([d[i]-z*axis[i] for i in range(3)])
        if any(abs(abs(dot(g['axis_direction'],axis))-1)>1e-8 or off_axis(g['axis_origin_mm'])>tolerance_mm for g in groups):
            return reject('CYLINDERS_NOT_COAXIAL')
        centers=[]
        for plane in planes:
            normal=plane['normal']; point=plane['plane_origin_mm']
            if abs(abs(dot(normal,axis))-1)>1e-8: return reject('ENDS_NOT_PERPENDICULAR')
            z=dot([point[i]-origin[i] for i in range(3)],axis)
            centers.append([origin[i]+z*axis[i] for i in range(3)])
            if off_axis(plane['centroid_mm'])>tolerance_mm: return reject('END_CENTROID_OFF_AXIS')
        length=math.dist(*centers)
        if length<=tolerance_mm: return reject('DEGENERATE_LENGTH')
        if not math.isclose(outer['area_mm2'],2*math.pi*radius*length,rel_tol=1e-6,abs_tol=1e-7):
            return reject('INCOMPLETE_OUTER_CYLINDER_AREA')
        numbers=[length,radius,solid['volume_mm3'],*(v for c in centers for v in c)]
        if not all(math.isfinite(v) for v in numbers): return reject('NONFINITE_GEOMETRY')
        if not 0<solid['volume_mm3']<=math.pi*radius*radius*length*(1+1e-6):
            return reject('VOLUME_EXCEEDS_CYLINDRICAL_ENVELOPE')
    except (KeyError,TypeError,ValueError,IndexError): return reject('INCOMPLETE_ANALYTIC_EVIDENCE')
    return {**result,'geometry_kind':'STRAIGHT_CYLINDRICAL_EXTERIOR_CANDIDATE',
            'reason':'COAXIAL_FACES_FULL_OUTER_AREA_AND_NORMAL_ENDS',
            'outer_diameter_mm':2*radius,'length_mm':length,'length_diameter_ratio':length/(2*radius),
            'axis_direction':axis,'end_plane_axis_centers_mm':centers,
            'outer_face_ids':outer['source_face_ids'],'face_ids':ids,
            'limits':'End-plane axis centers are not confirmed open ports; rods, pins and sleeves can share this exterior'}


def curved_exterior_candidate(solid, faces, tolerance_mm=1e-5):
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0: raise ValueError('Invalid tolerance')
    base={'schema_version':'step-exterior-candidate.v0.2','solid_id':solid.get('shape_id'),
          'status':'NOT_EVALUATED','geometry_kind':'UNDETERMINED','ports':[],
          'wall_thickness_mm':None,'engineering_pipe_confirmed':False,
          'design_cavity_confirmed':False,'fluid_channel_confirmed':False,
          'bend_radius_compliance':'NOT_EVALUATED'}
    def reject(reason): return {**base,'reason':reason}
    if solid.get('valid') is not True or solid.get('solid_count')!=1:
        return reject('REQUIRES_VALID_SINGLE_SOLID')
    ids=[f.get('shape_id') for f in faces]
    if solid.get('face_count')!=len(faces) or not all(ids) or len(set(ids))!=len(ids) or any(f.get('valid') is not True or 'EXACT_BREP' not in f.get('capabilities',[]) for f in faces):
        return reject('INCOMPLETE_OR_INVALID_FACE_EVIDENCE')
    features=[f.get('surface_features') or {} for f in faces]
    tori=[f for f in features if f.get('surface_type')=='TORUS']
    planes=[f for f in features if f.get('surface_type')=='PLANE']
    if len(planes)!=2 or len(tori) not in (1,2) or len(tori)+2!=len(faces):
        return reject('LOCAL_ROUNDING_OR_COMPOSITE_NOT_SUPPORTED_BEND')
    def dot(a,b): return sum(x*y for x,y in zip(a,b))
    def norm(v): return math.sqrt(dot(v,v))
    def delta(a,b): return [a[i]-b[i] for i in range(3)]
    def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    try:
        outer=max(tori,key=lambda t:t['minor_radius_mm'])
        R,r=outer['major_radius_mm'],outer['minor_radius_mm']
        origin,axis=outer['axis_origin_mm'],outer['axis_direction']
        if not all(math.isfinite(v) for v in [R,r,*origin,*axis,outer['area_mm2']]) or not R>r>0 or abs(norm(axis)-1)>1e-7:
            return reject('INVALID_TORUS_DIMENSIONS')
        sweep=outer['area_mm2']/(2*math.pi*r*R)
        if not 1e-6<sweep<math.pi-1e-6: return reject('UNSUPPORTED_SWEEP_RANGE')
        centers=[p['centroid_mm'] for p in planes]; radial=[]
        area=planes[0]['area_mm2']
        if not math.isfinite(area) or not 0<area<=math.pi*r*r*(1+1e-6): return reject('INVALID_END_AREA')
        for plane,center in zip(planes,centers):
            v=delta(center,origin)
            if abs(norm(v)-R)>tolerance_mm or abs(dot(v,axis))>tolerance_mm:
                return reject('END_NOT_ON_TORUS_CENTERLINE')
            unit=[x/R for x in v]; tangent=cross(axis,unit); radial.append(unit)
            if abs(abs(dot(tangent,plane['normal']))-1)>1e-8 or not math.isclose(plane['area_mm2'],area,rel_tol=1e-6,abs_tol=1e-7):
                return reject('END_AREA_OR_TANGENT_MISMATCH')
        if not math.isclose(dot(*radial),math.cos(sweep),rel_tol=1e-6,abs_tol=1e-7):
            return reject('OUTER_SWEEP_ENDPOINT_MISMATCH')
        inner_radius=0
        if len(tori)==2:
            inner=min(tori,key=lambda t:t['minor_radius_mm']); inner_radius=inner['minor_radius_mm']
            if not 0<inner_radius<r or abs(inner['major_radius_mm']-R)>tolerance_mm or norm(delta(inner['axis_origin_mm'],origin))>tolerance_mm or abs(abs(dot(inner['axis_direction'],axis))-1)>1e-8:
                return reject('NONCONCENTRIC_TORUS_BOUNDARIES')
            if not math.isclose(inner['area_mm2'],2*math.pi*inner_radius*R*sweep,rel_tol=1e-6,abs_tol=1e-7):
                return reject('TORUS_BOUNDARY_SWEEP_MISMATCH')
        if not math.isclose(area,math.pi*(r*r-inner_radius*inner_radius),rel_tol=1e-6,abs_tol=1e-7) or not math.isclose(solid['volume_mm3'],area*R*sweep,rel_tol=1e-6,abs_tol=1e-7):
            return reject('CURVED_VOLUME_AND_END_AREA_MISMATCH')
    except (KeyError,TypeError,ValueError,IndexError,ZeroDivisionError): return reject('INCOMPLETE_ANALYTIC_EVIDENCE')
    return {**base,'geometry_kind':'CIRCULAR_CURVED_EXTERIOR_CANDIDATE',
            'reason':'OUTER_TORUS_END_TANGENTS_AREA_AND_VOLUME_VERIFIED',
            'outer_diameter_mm':2*r,'centerline_bend_radius_mm':R,
            'sweep_angle_rad':sweep,'centerline_length_mm':R*sweep,
            'end_plane_axis_centers_mm':centers,'face_ids':ids,
            'limits':'Curved exterior can be solid; no design cavity, wall thickness or open port is inferred'}


def exterior_candidate(solid, faces, tolerance_mm=1e-5, shape=None):
    straight=straight_exterior_candidate(solid,faces,tolerance_mm)
    if straight['geometry_kind']!='UNDETERMINED': return straight
    curved=curved_exterior_candidate(solid,faces,tolerance_mm)
    if curved['geometry_kind']!='UNDETERMINED': return curved
    swept=bspline_circular_sweep_candidate(shape,solid,faces,tolerance_mm)
    return swept if swept['geometry_kind']!='UNDETERMINED' else {**straight,'curved_reason':curved['reason'],'bspline_sweep_reason':swept['reason']}
