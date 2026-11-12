"""Analytic support tangencies, requiring separate topological verification."""
import math
from . import _cylinder_groups


def tangent_route_seeds(faces, tolerance_mm=1e-5):
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0: raise ValueError('Invalid tolerance')
    cylinders=[f for f in faces if (f.get('surface_features') or {}).get('surface_type')=='CYLINDER']
    tori=[f for f in faces if (f.get('surface_features') or {}).get('surface_type')=='TORUS']
    groups=_cylinder_groups(cylinders,tolerance_mm)
    def dot(a,b): return sum(x*y for x,y in zip(a,b))
    seeds=[]
    for group in groups:
        for face in tori:
            torus=face['surface_features']
            try:
                R,r=torus['major_radius_mm'],torus['minor_radius_mm']
                center,normal=torus['axis_origin_mm'],torus['axis_direction']
                direction,origin=group['axis_direction'],group['axis_origin_mm']
                values=[R,r,*center,*normal]
                if not all(math.isfinite(v) for v in values) or not R>r>0 or abs(dot(normal,normal)-1)>1e-7:
                    continue
                if abs(group['radius_mm']-r)>tolerance_mm or abs(dot(direction,normal))>1e-8: continue
                offset=[center[i]-origin[i] for i in range(3)]
                along=dot(offset,direction)
                point=[origin[i]+along*direction[i] for i in range(3)]
                radial=[point[i]-center[i] for i in range(3)]
                if abs(dot(radial,normal))>tolerance_mm or abs(math.sqrt(dot(radial,radial))-R)>tolerance_mm: continue
                seeds.append({'cylinder_face_ids':group['source_face_ids'],'torus_face_id':face['shape_id'],
                    'support_tangent_point_mm':point,'section_radius_mm':r,
                    'support_circle_radius_mm':R,'status':'NOT_EVALUATED',
                    'engineering_pipe_confirmed':False,'design_cavity_confirmed':False,
                    'outer_surface_confirmed':False,'topology_verified':False,
                    'limits':'Infinite supports can be tangent outside trims; shared topology and route intent require verification'})
            except (KeyError,TypeError,ValueError,IndexError): continue
    return seeds
