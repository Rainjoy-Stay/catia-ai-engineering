"""Bounded OCCT display tessellation; never used for geometric verdicts."""
import json
from pathlib import Path


def export_preview(models, plan, directory, triangle_budget=None):
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.TopLoc import TopLoc_Location
    objects=[];count=0
    shapes=[s for s in plan['shapes'] if s.get('bounds_mm')]
    if not shapes: raise ValueError('No bounded physical geometry to display')
    minimum=[min(s['bounds_mm']['min'][i] for s in shapes) for i in range(3)]
    maximum=[max(s['bounds_mm']['max'][i] for s in shapes) for i in range(3)]
    for record in shapes:
        item=plan['mapping'][record['shape_id']]
        shape=models[item['batch_id']]._shape(item['local_shape_id'])
        BRepMesh_IncrementalMesh(shape,0.3,False,0.3,False).Perform()
        explorer=TopExp_Explorer(shape,TopAbs_FACE);vertices=[]
        while explorer.More():
            face=TopoDS.Face_s(explorer.Current());location=TopLoc_Location()
            triangulation=BRep_Tool.Triangulation_s(face,location)
            if triangulation is not None:
                for index in range(1,triangulation.NbTriangles()+1):
                    indices=list(triangulation.Triangle(index).Get())
                    if face.Orientation()==TopAbs_REVERSED:indices.reverse()
                    for node in indices:
                        point=triangulation.Node(node).Transformed(location.Transformation())
                        vertices.extend([round(point.X(),4),round(point.Y(),4),round(point.Z(),4)])
                    count+=1
            explorer.Next()
        objects.append({'id':record['shape_id'],'name':record.get('source_body_name'),
                        'geometry_kind':record.get('geometry_kind') or ('SOLID' if record.get('solid_count') else 'SURFACE'),
                        'source_path':record.get('source_path'),'volume_mm3':record.get('volume_mm3') if record.get('solid_count') else None,
                        'surface_area_mm2':record.get('surface_area_mm2'),
                        'source_body_index':record.get('source_body_index'),
                        'mapping_method':record.get('mapping_method'),'bounds':record['bounds_mm'],'vertices':vertices})
    payload={'objects':objects,'bounds':{'min':minimum,'max':maximum},'triangle_count':count,'truncated':False,'display_only':True,'source_object_count':len(shapes)}
    destination=Path(directory)/'preview.json';temporary=destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8');temporary.replace(destination)
