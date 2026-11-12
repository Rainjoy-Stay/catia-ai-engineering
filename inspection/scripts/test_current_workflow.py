"""Deployment regression: thresholds, shell semantics, pipe exclusion and report."""
import os,sys,json,subprocess,tempfile,itertools,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(sys.argv[1]).resolve();sys.path.insert(0,str(ROOT/'project'))
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.exterior import exterior_candidate
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Pnt,gp_Pln,gp_Dir
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRep import BRep_Builder
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS_Shape
O=ROOT/'validation/current-workflow';O.mkdir(parents=True,exist_ok=True)
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def script(name,*args,env=None):
 cp=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'project/tools/current'/name),str(O),*map(str,args)],env=env,cwd=ROOT,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180)
 (O/(name+'.log')).write_text(cp.stdout+cp.stderr,encoding='utf8');assert cp.returncode==0,cp.stderr[-1500:]
model=OCCTBRepModel();entities=[];pipes=[]
shapes=[('SOLID',BRepPrimAPI_MakeBox(1,1,1).Shape()),('SOLID',BRepPrimAPI_MakeBox(gp_Pnt(.5,0,0),1,1,1).Shape()),('SOLID',BRepPrimAPI_MakeBox(gp_Pnt(1.2,0,0),1,1,1).Shape()),('SOLID',BRepPrimAPI_MakeCylinder(1,10).Shape()),('FACE',BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(.5,0,0),gp_Dir(1,0,0)),-2,2,-2,2).Face())]
fixture=TopoDS_Shape();assert BRepTools.Read_s(fixture,str(ROOT/'project/artifacts/spatial_local_15/exterior_scan/BODY_000840_SOLID_0001.brep'),BRep_Builder());shapes.append(('SOLID',fixture))
for idx,(kind,shape) in enumerate(shapes,1):
 sid=f'BODY_{idx:06d}';v=model.register_shape(sid,shape);path=O/(sid+'.brep');model.write_brep(sid,path)
 e={'index':idx,'name':'Regression_'+str(idx),'shape_id':sid,'cache_file':str(path),'geometry_kind':kind,'source_path':'SyntheticRegression/'+sid,'bounds_mm':v['bounds_mm'],'valid':v['valid']};entities.append(e)
 if kind=='SOLID':
  faces=[model.describe(f) for f in model.solid_face_provenance(sid)['face_ids']];pipes.append({'source_body_index':idx,'source_body_name':e['name'],'candidate':exterior_candidate(v,faces),'support_tangency_seeds':[],'valid':v['valid'],'face_count':v['face_count']})
save('all_entity_caches.json',entities);save('pipe-recognition.json',pipes);save('check.json',{'document':'SyntheticRegression','findings':[],'counts':{}})
results=[]
for index,(ia,ib,screen,status) in enumerate([(0,1,.1,'FAIL'),(0,2,.1,'PASS'),(0,2,.3,'NOT_EVALUATED'),(0,4,.1,'NOT_EVALUATED')]):
 req=O/f'pair{index}.input.json';out=O/f'pair{index}.json';req.write_text(json.dumps([entities[ia],entities[ib]]),encoding='utf8')
 cp=subprocess.run([sys.executable,str(ROOT/'project/tools/current/complete40_pair.py'),str(req),str(out)],cwd=ROOT,env=dict(os.environ,CATIA_SCREEN_MM=str(screen)),capture_output=True,text=True,timeout=60)
 assert cp.returncode==0,cp.stderr
 row=json.loads(out.read_text(encoding='utf8'));assert row['decision']['status']==status,(screen,row);results.append(row)
script('reclassify40_piping.py')
pins=json.loads((O/'pipe-recognition.json').read_text(encoding='utf8'));assert next(r for r in pins if r['source_body_index']==4)['candidate'].get('excluded_from_pipe_recognition')
script('scan40_swept_routes.py')
routes=json.loads((O/'样条管路中心线检查.json').read_text(encoding='utf8'));assert any(r['shape_id']=='BODY_000006' for r in routes['routes']),routes['scan_audit'][-1]
assert not any(r['shape_id']=='BODY_000004' for r in routes['routes'])
counts=dict(Counter(r['decision']['status'] for r in results));c=json.loads((O/'check.json').read_text(encoding='utf8'));c.update(document='SyntheticRegression',counts=counts);save('check.json',c)
save('run-config.json',{'document':'SyntheticRegression','clearance_mm':.1,'workers':2,'target_bodies':5})
save('spatial_box_analysis.json',{'pair_count':len(results),'records':results,'body_count':5,'surface_count':1})
for n in ['full-export-audit.json','full-body-mapping-audit.json','selected-body-import-audit.json','surface-import-audit.json']:save(n,{'test_fixture':True,'status':'REGRESSION_ONLY'})
script('portable_report.py')
import pymupdf
pdf=pymupdf.open(O/'report.pdf');text=''.join(p.get_text() for p in pdf);assert 'SyntheticRegression' in text and '未评价' in text
save('acceptance.json',{'status':'PASS','checks':['positive_volume_fail','configured_clearance_0_1_vs_0_3','surface_intersection_pending','solid_pin_excluded','bspline_route_from_model','pdf_docx_csv_generated'],'pipe_route_count':len(routes['routes']),'pages':len(pdf),'fixture_only':True})
print('CURRENT_WORKFLOW_PASS',flush=True)
