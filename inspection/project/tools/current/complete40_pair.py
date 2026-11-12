import sys,json
from pathlib import Path
P=Path(__file__).resolve().parents[2];sys.path.insert(0,str(P))
import os
screen=float(os.environ.get("CATIA_SCREEN_MM","0.1"))
from catia_checker.occt_brep import OCCTBRepModel
a,b=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'));m=OCCTBRepModel()
for x in (a,b):m.load_brep(x['shape_id'],Path(x['cache_file']))
valid=[m.describe(x['shape_id'])['valid'] for x in (a,b)]
if not all(valid):
 result={'body_a':a['index'],'name_a':a['name'],'body_b':b['index'],'name_b':b['name'],'object_a':a['shape_id'],'object_b':b['shape_id'],'kind_a':a['geometry_kind'],'kind_b':b['geometry_kind'],'fact':{'input_valid':valid},'decision':{'status':'NOT_EVALUATED','category':'INPUT_INVALID','reason':'输入未通过 B-Rep 有效性检查，需要修复或独立验证。'}}
 Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');raise SystemExit(0)
if a['geometry_kind']==b['geometry_kind']=='SOLID':
 d=m.distance(a['shape_id'],b['shape_id']);o=m.local_overlap_evidence(a['shape_id'],b['shape_id']);fact={'minimum_distance_mm':d['minimum_distance_mm'],'intersection_volume_mm3':max(0,o['volume_mm3']),'exact_brep':True};evidence={'distance':d,'overlap':o}
else:
 evidence=m.surface_pair_fact(a['shape_id'],b['shape_id'],entity_a=a,entity_b=b);fact={'minimum_distance_mm':evidence['minimum_distance_mm'],'surface_intersection':evidence.get('surface_intersection',False),'section_edge_count':evidence.get('section_edge_count',0),'exact_brep':True}
 distance=fact['minimum_distance_mm']
status='PASS' if fact['minimum_distance_mm']>screen and not fact.get('surface_intersection') else 'NOT_EVALUATED'
if a['geometry_kind']==b['geometry_kind']=='SOLID' and fact.get('intersection_volume_mm3',0)>1e-6:status='FAIL'
category='OUTSIDE_CONFIGURED_SCREEN' if status=='PASS' else 'POSITIVE_COMMON_VOLUME' if fact.get('intersection_volume_mm3',0)>1e-6 else 'SURFACE_INTERSECTION_REVIEW' if fact.get('surface_intersection') else 'CONTACT_OR_CLEARANCE_REVIEW'
result={'body_a':a['index'],'name_a':a['name'],'body_b':b['index'],'name_b':b['name'],'object_a':a['shape_id'],'object_b':b['shape_id'],'kind_a':a['geometry_kind'],'kind_b':b['geometry_kind'],'fact':fact,'exact_evidence':evidence,'decision':{'status':status,'category':category,'reason':'超过本轮几何筛查阈值；非工程验收' if status=='PASS' else '几何接触、交线或净距需结合设计允许性复核'}}
if status=='FAIL':result['decision'].update(category='SOLID_VOLUME_INTERFERENCE',reason='精确实体公共体积大于数值容差，几何干涉未通过；设计允许性另行复核。')
Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
