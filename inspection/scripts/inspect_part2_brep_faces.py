from __future__ import annotations
import json, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'project'))
from catia_checker.occt_brep import OCCTBRepModel
m=OCCTBRepModel(); manifest=m.load_step(root/'project'/'artifacts'/'MiniEngine_route_brep_validation_20260922.stp', lightweight=False)
s=next(x for x in manifest['shapes'] if x['shape_id']=='STEP_SOLID_0002')
rows=[]
face_ids=m.solid_face_provenance('STEP_SOLID_0002')['face_ids']
for face_id in face_ids:
    f=m.describe(face_id)
    sf=f.get('surface_features') or {}
    rows.append({'id':f['shape_id'],'type':sf.get('surface_type'),'area':sf.get('area_mm2'),
                 'bounds':f.get('bounds_mm'),'centroid':sf.get('centroid_mm'),
                 'radius':sf.get('radius_mm'),'axis':sf.get('axis_direction'),
                 'normal':sf.get('normal')})
print(json.dumps({'solid':{k:s.get(k) for k in ('volume_mm3','surface_area_mm2','bounds_mm','face_count')},'faces':rows},ensure_ascii=False,indent=2))
