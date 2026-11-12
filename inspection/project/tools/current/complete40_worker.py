import sys,json,time,hashlib,math,itertools,subprocess,concurrent.futures
from pathlib import Path
from collections import Counter
from datetime import datetime
W=Path(__file__).resolve().parents[3];B=W;P=B/'project';O=Path(sys.argv[1]);workers=int(sys.argv[2]);sys.path[:0]=[str(P),str(B/'scripts'),str(B/'vendor/catia-v5-mcp-server/src')]
config=json.loads((O/'run-config.json').read_text(encoding='utf8'));screen=float(config['clearance_mm'])
import os
os.environ['CATIA_SCREEN_MM']=str(screen)

def save(n,v):
 target=O/n;temp=target.with_suffix(target.suffix+'.tmp');temp.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str),encoding='utf8')
 for attempt in range(100):
  try:temp.replace(target);break
  except PermissionError:
   if attempt==99:raise
   time.sleep(.05)
def event(stage,**kw):print(json.dumps(dict(stage=stage,**kw),ensure_ascii=False),flush=True)
save('revised-run-started.json',{'started':datetime.now().isoformat(),'historical_geometry_read':False,'historical_measurements_read':False})
from r18_connection import R18Connection
conn=R18Connection();info=conn.connect();doc=conn.active_document
assert doc.Name==json.loads((O/'run-config.json').read_text(encoding='utf8'))['document']
names={str(doc.Part.Bodies.Item(i).Name):i for i in range(1,doc.Part.Bodies.Count+1)};assert len(names)==doc.Part.Bodies.Count
save('connection.json',info);saved_before=bool(doc.Saved)
source=O/json.loads((O/'full-export-audit.json').read_text(encoding='utf8')).get('file','current-full-model.stp')
audit=json.loads((O/'full-export-audit.json').read_text(encoding='utf8'));assert hashlib.sha256(source.read_bytes()).hexdigest()==audit['sha256']
event('SCOPE_REVISED',operation='使用本轮刚导出的完整几何与登记面壳，不读取历史运行')
from catia_checker.catia_body_batches import export_body_batches
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.exterior import exterior_candidate
from standalone.step_pipe_semantics.route_seeds import tangent_route_seeds
plan=json.loads((O/'revised-scope-plan.json').read_text(encoding='utf8'));center=plan['center_mm'];half=plan['half_size_mm'];(O/'selected-body-export').mkdir(exist_ok=True)
body_export=export_body_batches(conn.app,doc,O/'selected-body-export',batch_size=40,body_indices=plan['selected_body_indices'],include_geometrical_sets=False,progress=lambda e:event(e.pop('stage'),**e))
model=OCCTBRepModel();event('BATCH_LOAD_START',batch_id='SELECTED_BODIES',batch_count=1,operation='导入当前空间框实体')
manifest={'shapes':[]}
for batch_index,file in enumerate(body_export['batch_files']):
 sub=OCCTBRepModel();loaded=sub.load_step(Path(file))
 for shape in loaded['shapes']:
  old_id=shape['shape_id'];sid=f'BATCH{batch_index}_'+old_id
  model.register_shape(sid,sub._shape(old_id));shape['shape_id']=sid;manifest['shapes'].append(shape)
save('selected-body-manifest.json',manifest)
chosen=[]
for i in plan['selected_body_indices']:
 name=next(name for name,index in names.items() if index==i);matches=[x for x in manifest['shapes'] if x.get('source_name')==name and x.get('solid_count')==1]
 if len(matches)==1:chosen.append((i,matches[0]))
 else:event('BODY_IMPORT_UNRESOLVED',body_index=i,source_name=name,operation=f'Body {i} 未取得唯一导入实体，保留未评价')
assert chosen, 'No uniquely mapped solid in selected region'
save('selected-body-import-audit.json',{'selected_native_count':len(plan['selected_body_indices']),'mapped_solid_count':len(chosen),'unresolved_body_indices':sorted(set(plan['selected_body_indices'])-{i for i,x in chosen})})
surface_export=json.loads((O/'surface-export-audit.json').read_text(encoding='utf8'))
save('spatial_selection.json',{'center_mm':center,'half_size_mm':[half]*3,'box_bounds_mm':{'min':[v-half for v in center],'max':[v+half for v in center]},'selected_body_indices':plan['selected_body_indices'],'body_count':len(chosen),'selection_method':'CURRENT_RUN_FRESH_AABB_OPPOSITE_LOWER_SIDE','historical_data_used':False})
save('export-audit.json',{'status':'EXPORTED','exported_body_count':len(plan['selected_body_indices']),'expected_body_count':len(plan['selected_body_indices']),'batch_files':body_export['batch_files'],'source_saved_by_tool':False})
records=[];pipes=[]
for i,s in chosen:
 sid=s['shape_id'];cache=O/f'BODY_{i:06d}.brep';model.write_brep(sid,cache)
 records.append({'index':i,'name':s['source_name'],'shape_id':f'BODY_{i:06d}','original_shape_id':sid,'cache_file':str(cache),'bounds_mm':s['bounds_mm'],'valid':s['valid'],'geometry_kind':'SOLID','source_path':f"Part/Body#{i}/{s['source_name']}"})
 faces=[model.describe(f) for f in model.solid_face_provenance(sid)['face_ids']]
 candidate=exterior_candidate(s,faces)
 try:seeds=tangent_route_seeds(faces)
 except Exception:seeds=[]
 pipes.append({'source_body_index':i,'source_body_name':s['source_name'],'candidate':candidate,'support_tangency_seeds':seeds,'valid':s['valid'],'face_count':s['face_count']})
save('box_body_caches.json',records);save('pipe-recognition.json',pipes)
event('BATCH_LOAD_COMPLETE',batch_id='FULL_BODIES',operation='本轮空间框实体导入完成')
surface_records=[];mapping_issues=[];mapped_indices=set()
for path in surface_export['batch_files']:
 path=Path(path);sm=OCCTBRepModel();event('BATCH_LOAD_START',batch_id=path.stem,batch_count=1+len(surface_export['batch_files']),operation='导入面壳 '+path.stem)
 mf=sm.load_step(path);save('surfaces/'+path.stem+'.manifest.json',mf)
 for identity in [x for x in surface_export['mapping'] if x['batch_id']==path.stem]:
  matches=[x for x in mf['shapes'] if x.get('source_name')==identity['source_body_name'] and x.get('solid_count',0)==0 and x.get('face_count',0)>0]
  if len(matches)!=1:
   mapping_issues.append({'identity':identity,'reason':'NAME_MAPPING_NOT_UNIQUE','match_count':len(matches)});continue
  shape=matches[0];bounds=shape.get('bounds_mm');mapped_indices.add(identity['source_body_index'])
  if not bounds or max(abs(v) for v in bounds['min']+bounds['max'])>=1e6:
   mapping_issues.append({'identity':identity,'reason':'NONFINITE_BOUNDS'});continue
  sid='GEOM_'+identity['source_body_index'].replace(':','_').replace('.','_');cache=O/(sid+'.brep');sm.write_brep(shape['shape_id'],cache)
  surface_records.append({'index':identity['source_body_index'],'name':identity['source_body_name'],'shape_id':sid,'cache_file':str(cache),'bounds_mm':bounds,'valid':shape['valid'],'geometry_kind':'FACE' if shape['face_count']==1 else 'SHELL','source_path':identity['source_path'],'source_set_indices':identity['source_set_indices'],'source_element_index':identity['source_element_index'],'source_body_index':identity['source_body_index'],'source_body_name':identity['source_body_name']})
 event('BATCH_LOAD_COMPLETE',batch_id=path.stem,operation='面壳导入完成 '+path.stem)
def in_box(r):return all(r['bounds_mm']['min'][k]<=center[k]+half and r['bounds_mm']['max'][k]>=center[k]-half for k in range(3))
selected_surfaces=[r for r in surface_records if in_box(r)];entities=records+selected_surfaces
save('surface-import-audit.json',{'registered':surface_export['element_count'],'exported':len(surface_export['mapping']),'finite_mapped':len(surface_records),'selected_count':len(selected_surfaces),'selected':selected_surfaces,'mapping_issues':mapping_issues,'all_finite_records':surface_records,'export_errors':surface_export['errors']})
save('all_entity_caches.json',entities)
objects={r['shape_id']:{**r,'source_body_index':r['index'],'source_body_name':r['name'],'source_name':r['name'],'bounds_mm':r['bounds_mm']} for r in entities};candidates=[];tasks=[];results=[]
for number,(a,b) in enumerate(itertools.combinations(entities,2)):
 pair=[a['shape_id'],b['shape_id']];candidates.append(pair);r={'body_a':a['index'],'name_a':a['name'],'body_b':b['index'],'name_b':b['name'],'object_a':pair[0],'object_b':pair[1],'kind_a':a['geometry_kind'],'kind_b':b['geometry_kind']}
 lower=math.sqrt(sum(max(a['bounds_mm']['min'][k]-b['bounds_mm']['max'][k],b['bounds_mm']['min'][k]-a['bounds_mm']['max'][k],0)**2 for k in range(3)))
 if lower>screen and a.get('valid') and b.get('valid'):results.append({**r,'aabb_distance_lower_bound_mm':lower,'decision':{'status':'PASS','category':'OUTSIDE_CONFIGURED_SCREEN','reason':'包围盒距离下界超过本轮筛查阈值；非工程验收'}})
 else:tasks.append((number,a,b,r))
registry={'objects':objects,'candidates':candidates,'catia_bodies':[{'source_body_index':i,'source_body_name':next(name for name,index in names.items() if index==i)} for i in plan['selected_body_indices']],'catia_geometry':selected_surfaces,'mapping_errors':mapping_issues};save('registry.json',registry)
from catia_checker.monitor_preview import export_preview
pm=OCCTBRepModel()
for r in entities:pm.load_brep(r['shape_id'],Path(r['cache_file']))
event('PREVIEW_START',operation='生成实体与面壳三维显示网格')
export_preview([pm],{'shapes':list(objects.values()),'mapping':{sid:{'batch_id':0,'local_shape_id':sid} for sid in objects}},O,triangle_budget=900000)
event('PREVIEW_COMPLETE',operation=f'{len(chosen)}实体及{len(selected_surfaces)}个面壳已载入UI')
fingerprint=hashlib.sha256(source.read_bytes()).hexdigest();(O/'revised-pairs').mkdir(exist_ok=True);PAIRDIR=O/'revised-pairs'
def publish():
 findings=[];completed=[]
 for r in results:
  fact=r.get('fact',{});vol=fact.get('intersection_volume_mm3',0);pair=[r['object_a'],r['object_b']]
  completed.append({'pair':pair,'fact':{'distance':{'minimum_distance_mm':fact.get('minimum_distance_mm'),'exact_brep':bool(fact)},'common':{'intersection_volume_mm3':fact.get('intersection_volume_mm3'),'exact_brep':bool(fact)},'surface':fact,'error':r.get('error')}})
  findings.append({'issue_id':pair[0]+'__'+pair[1],'status':r['decision']['status'],'title':r['decision']['category'],'object_a':r['name_a'],'object_b':r['name_b'],'measured_value':vol if vol>1e-6 else fact.get('minimum_distance_mm'),'unit':'mm³' if vol>1e-6 else 'mm','rule_id':'CONFIGURED_GEOMETRY_SCREEN_PENDING_APPROVAL','severity':'REVIEW' if r['decision']['status']!='PASS' else 'INFO','rationale':r['decision']['reason'],'evidence':fact,'recommendation':'复核实体、面壳接触及设计允许性；计算失败项专项补算。','metadata':{'geometry_object_a':pair[0],'geometry_object_b':pair[1],'source_body_a':{'source_body_index':r['body_a'],'source_body_name':r['name_a']},'source_body_b':{'source_body_index':r['body_b'],'source_body_name':r['name_b']},'step_interference_filter':{'reason':r['decision']['reason']}}})
 save('checkpoint.json',{'completed_pairs':completed,'geometry_fingerprint':'FRESH-'+fingerprint})
 save('check.json',{'schema_version':'1.1.0','run_id':O.name,'document':doc.Name,'counts':dict(Counter(f['status'] for f in findings)),'findings':findings,'source':{'body_count':len(chosen),'surface_count':len(selected_surfaces),'pair_count':len(candidates),'fresh_export':str(source)},'audit':{'exceptions':[],'source_saved_by_tool':False,'historical_measurements_used':False,'historical_geometry_used':False},'confidence_budget':{'is_complete':False},'pipe_recognition':pipes,'rule_snapshot':{'screening_clearance_mm':screen,'approved_for_engineering_acceptance':False}})
publish()
def work(t,budget=60):
 number,a,b,r=t;req=PAIRDIR/f'{number}.input.json';out=PAIRDIR/f'{number}.result.json';req.write_text(json.dumps([a,b]),encoding='utf8');pair=[a['shape_id'],b['shape_id']]
 event('EXACT_PAIR_START',pair=pair,object_a=pair[0],object_b=pair[1],index=number,operation='检查 '+str(a['index'])+' / '+str(b['index']))
 try:
  process=subprocess.run([sys.executable,str(W/'project/tools/current/complete40_pair.py'),str(req),str(out)],capture_output=True,timeout=budget)
  if process.returncode:raise RuntimeError(process.stderr[-500:].decode(errors='replace'))
  r=json.loads(out.read_text(encoding='utf8'));status='COMPLETE'
 except Exception as e:r={**r,'error':str(e),'decision':{'status':'NOT_EVALUATED','category':'UNDETERMINED','reason':'未取得可信精算结果'}};status='TIMEOUT' if isinstance(e,subprocess.TimeoutExpired) else 'ERROR'
 event('EXACT_PAIR_COMPLETE',pair=pair,object_a=pair[0],object_b=pair[1],index=number,status=status,operation='完成 '+str(a['index'])+' / '+str(b['index']));return r
with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
 for future in concurrent.futures.as_completed([pool.submit(work,t) for t in tasks]):results.append(future.result());publish()
retry=[t for t in tasks if any('error' in r and r['object_a']==t[3]['object_a'] and r['object_b']==t[3]['object_b'] for r in results)]
if retry:
 event('RETRY_START',operation=f'{len(retry)}对未完成项延长至180秒、2路并行专项补算')
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for future in concurrent.futures.as_completed([pool.submit(work,t,180) for t in retry]):
   r=future.result();results[:]=[v for v in results if (v['object_a'],v['object_b'])!=(r['object_a'],r['object_b'])];results.append(r);publish()
save('spatial_box_analysis.json',{'status':'PARTIAL','body_count':len(chosen),'surface_count':len(selected_surfaces),'pair_count':len(candidates),'exact_candidate_count':len(tasks),'screening_clearance_mm':screen,'records':results,'body_records':records,'decision_counts':dict(Counter(r['decision']['status'] for r in results)),'pair_errors':sum('error' in r for r in results),'positive_volume_overlap_pairs':sum(r.get('fact',{}).get('intersection_volume_mm3',0)>1e-6 for r in results)})
event('FRESH_CHECK_COMPLETE',pair_count=len(candidates),operation='实体、实体—面壳及面壳之间的本轮检查结束，未知项保留待复核')
