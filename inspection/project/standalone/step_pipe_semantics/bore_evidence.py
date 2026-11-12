"""Exact clear-cylinder witnesses and radial wall samples, not design semantics."""
import math
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir, gp_Lin


def inspect_straight_bore(model, solid_id, centers, inner_radius, outer_radius, tolerance=1e-7):
    solid=model.describe(solid_id)
    if solid.get('valid') is not True or solid.get('solid_count') != 1:
        raise ValueError('Requires a valid single solid')
    values=[inner_radius,outer_radius,tolerance,*centers[0],*centers[1]]
    if not all(math.isfinite(v) for v in values) or not outer_radius>inner_radius>10*tolerance>0:
        raise ValueError('Invalid bore dimensions or tolerance')
    length=math.dist(*centers)
    if length<=10*tolerance: raise ValueError('Bore too short')
    direction=[(centers[1][i]-centers[0][i])/length for i in range(3)]
    clearance=max(10*tolerance,.05*inner_radius)
    axis=gp_Ax2(gp_Pnt(*centers[0]),gp_Dir(*direction))
    # A smaller full-length cylinder proves only this finite clear passage.
    witness_id=solid_id+'::BORE_WITNESS'
    model.register_shape(witness_id,BRepPrimAPI_MakeCylinder(axis,inner_radius-clearance,length).Shape())
    common=model.common_volume(solid_id,witness_id)
    distance=model.distance(solid_id,witness_id)
    confirmed=(common['intersection_volume_mm3']==0 and distance['minimum_distance_mm']>tolerance)
    x=axis.XDirection(); y=axis.YDirection()
    xv=[x.X(),x.Y(),x.Z()]; yv=[y.X(),y.Y(),y.Z()]
    samples=[]
    intersector=IntCurvesFace_ShapeIntersector(); intersector.Load(model._shape(solid_id),tolerance)
    for fraction in (.01,.1,.5,.9,.99):
        point=[centers[0][i]+fraction*length*direction[i] for i in range(3)]
        for j in range(8):
            angle=j*math.pi/4
            radial=[math.cos(angle)*xv[i]+math.sin(angle)*yv[i] for i in range(3)]
            intersector.Perform(gp_Lin(gp_Pnt(*point),gp_Dir(*radial)),0,outer_radius*1.5)
            hits=[]
            if intersector.IsDone():
                for value in sorted(intersector.WParameter(k) for k in range(1,intersector.NbPnt()+1)):
                    if not hits or abs(value-hits[-1])>10*tolerance: hits.append(value)
            sample={'axial_fraction':fraction,'angle_rad':angle,'radial_hits_mm':hits}
            if len(hits)==2 and abs(hits[0]-inner_radius)<=10*tolerance and hits[1]>hits[0]:
                sample['sampled_wall_thickness_mm']=hits[1]-hits[0]
            samples.append(sample)
    thickness=[s['sampled_wall_thickness_mm'] for s in samples if 'sampled_wall_thickness_mm' in s]
    return {'exact_brep':True,'status':'NOT_EVALUATED','engineering_pipe_confirmed':False,
            'design_cavity_confirmed':False,'fluid_channel_confirmed':False,
            'evidence_scope':'CLEAR_TEST_CYLINDER_RELATIVE_TO_THIS_SOLID_ONLY',
            'clear_passage_witness_confirmed':confirmed,'witness_radius_mm':inner_radius-clearance,
            'witness_length_mm':length,'common_volume_mm3':common['intersection_volume_mm3'],
            'witness_minimum_distance_mm':distance['minimum_distance_mm'],
            'radial_samples':samples,'valid_wall_sample_count':len(thickness),
            'sampled_wall_min_mm':min(thickness) if thickness else None,
            'sampled_wall_max_mm':max(thickness) if thickness else None,
            'limits':'Nonintersection only proves this test cylinder is outside this Solid material; not a design cavity, fluid passage, whole-assembly clearance or global minimum wall thickness'}
