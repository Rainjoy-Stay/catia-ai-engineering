"""Native GSD review in one full geometry copy; never copy geometry per pair."""
import sys,json,time,traceback,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];F=ROOT/'output/全量原生DMU检查_20261012'
sys.path.insert(0,str(ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
from catia_mcp.connection import CATIAConnection
def write(name,data):
 p=F/name;tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf8')
 for attempt in range(20):
  try:os.replace(tmp,p);return
  except PermissionError:
   if attempt==19:raise
   time.sleep(.05)
def emit(stage,**kw):print(json.dumps(dict(stage=stage,**kw),ensure_ascii=False),flush=True)
def run():
 conn=CATIAConnection();conn.connect();app=conn.app;source=app.Documents.Item('涡轮发动机.CATPart');source.Activate();sp=source.Part;ss=source.Selection
 baseline={'name':source.Name,'full_name':source.FullName,'saved':bool(source.Saved),'bodies':sp.Bodies.Count,'hybrid_bodies':sp.HybridBodies.Count}
 write('single-part-source-before.json',baseline)
 native=json.loads((F/'native-results.json').read_text(encoding='utf8'));prep=json.loads((F/'preparation-audit.json').read_text(encoding='utf8'));registry={r['id']:r for r in prep['records']}
 old=json.loads((F/'native-gsd-spa-review.json').read_text(encoding='utf8'));rows=old['rows'];by_pair={tuple(r['pair']):r for r in rows}
 selected=[(n,c) for n,c in enumerate(native['conflicts'],1) if c['type']=='CLASH' and any(registry[k]['kind']=='SURFACE' for k in (c['first_part_number'],c['second_part_number']))]
 previous=json.loads((F/'single-part-progress.json').read_text(encoding='utf8')) if (F/'single-part-progress.json').exists() else {}
 resume=previous.get('copied_once',False) and not previous.get('complete',False)
 status=previous if resume else {'stage':'COPYING_FULL_PART','pid':os.getpid(),'complete':False,'copied_once':False,'done':0,'total':len(selected),'gsd_done':0,'gsd_errors':0,'source_saved_by_tool':False,'rows':[]}
 status.update(pid=os.getpid(),stage='RESUMING_DIRECT_REVIEW' if resume else 'COPYING_FULL_PART');status.pop('error',None)
 write('single-part-progress.json',status);started=time.perf_counter();refresh=app.RefreshDisplay;hso=app.HSOSynchronized
 target=None
 try:
  app.RefreshDisplay=False;app.HSOSynchronized=False
  target=app.Documents.Item('NativeGSD_FullCopy_20261013.CATPart') if resume else app.Documents.Add('Part');tp=target.Part;target.Product.PartNumber='NativeGSD_FullCopy_20261013';ds=target.Selection
  # Copy all original bodies together once, preserving their individual names.
  source.Activate();ss.Clear()
  if not resume:
   for i in range(1,sp.Bodies.Count+1):ss.Add(sp.Bodies.Item(i))
   ss.Copy();ss.Clear();target.Activate();ds.Clear();ds.Add(tp.MainBody);ds.PasteSpecial('CATPrtResultWithOutLink');ds.Clear()
  emit('SOLIDS_COPIED',count=tp.Bodies.Count)
  # Copy complete original geometric sets together, including unresolved surfaces.
  source.Activate();ss.Clear()
  if not resume:
   for i in range(1,sp.HybridBodies.Count+1):ss.Add(sp.HybridBodies.Item(i))
   ss.Copy();ss.Clear();target.Activate();inputs=tp.HybridBodies.Add();inputs.Name='OriginalSurfaceSets';ds.Clear();ds.Add(inputs);ds.PasteSpecial('CATPrtResultWithOutLink');ds.Clear()
  target.Activate()
  bodymap={};surfacemap={}
  for i in range(1,tp.Bodies.Count+1):
   b=tp.Bodies.Item(i)
   if b.Shapes.Count:bodymap.setdefault(b.Name,[]).append(b.Shapes.Item(b.Shapes.Count))
  def scan(groups):
   for i in range(1,groups.Count+1):
    group=groups.Item(i)
    for j in range(1,group.HybridShapes.Count+1):
     obj=group.HybridShapes.Item(j);surfacemap.setdefault(obj.Name,[]).append(obj)
    scan(group.HybridBodies)
  scan(tp.HybridBodies)
  if sum(map(len,bodymap.values()))!=sp.Bodies.Count:raise RuntimeError('Full-copy body count mismatch; no review performed')
  # Never guess identity when copied names are ambiguous.
  refs={}
  for sid,r in registry.items():
   matches=(bodymap if r['kind']=='SOLID' else surfacemap).get(r['name'],[])
   if len(matches)!=1:raise RuntimeError('Copy identity mismatch: '+sid+' / '+r['name'])
   refs[sid]=tp.CreateReferenceFromObject(matches[0])
  tp.Update()
  if not resume:target.SaveAs(str(F/'NativeGSD_FullCopy_20261013.CATPart'))
  status.update(stage='DIRECT_GSD_REVIEW',copied_once=True,copy_seconds=time.perf_counter()-started,body_count=sum(map(len,bodymap.values())),surface_count=sum(map(len,surfacemap.values())))
  write('single-part-progress.json',status);emit('FULL_COPY_VERIFIED',bodies=status['body_count'],surfaces=status['surface_count'],seconds=status['copy_seconds'])
  group=tp.HybridBodies.Item('NativeGSD_InspectionResults') if resume else tp.HybridBodies.Add();group.Name='NativeGSD_InspectionResults';spa=target.GetWorkbench('SPAWorkbench')
  for row in status['rows']:by_pair[tuple(row['pair'])]['gsd']=row['gsd']
  skip=status['done']
  for done,(number,c) in enumerate(selected,1):
   if done<=skip:continue
   a,b=c['first_part_number'],c['second_part_number'];intersection=None;tick=time.perf_counter()
   try:
    intersection=tp.HybridShapeFactory.AddNewIntersection(refs[a],refs[b]);intersection.Name=f'GSD_{number:05d}';group.AppendHybridShape(intersection);tp.UpdateObject(intersection)
    result={'status':'COMPLETE','intersection_created':True,'method':'CATIA_GSD_DIRECT_REFERENCES_IN_SINGLE_FULL_COPY','feature_name':intersection.Name,'document':target.Name}
    try:result['intersection_length_mm']=float(spa.GetMeasurable(tp.CreateReferenceFromObject(intersection)).Length)
    except Exception:result['measurement_note']='Intersection is not a measurable curve'
    status['gsd_done']+=1
   except Exception as exc:
    result={'status':'ERROR','intersection_created':False,'error':str(exc),'method':'CATIA_GSD_DIRECT_REFERENCES_IN_SINGLE_FULL_COPY'};status['gsd_errors']+=1
    # Delete only the failed feature we just created in our new inspection copy.
    if intersection is not None:
     ds.Clear();ds.Add(intersection);ds.Delete();ds.Clear()
   result['elapsed_seconds']=time.perf_counter()-tick;by_pair[(a,b)]['gsd']=result
   status['done']=done;status['rows'].append({'pair':[a,b],'native_index':number,'gsd':result});write('single-part-progress.json',status)
   emit('DIRECT_REVIEW_PROGRESS',completed=done,total=len(selected),gsd_done=status['gsd_done'],gsd_errors=status['gsd_errors'])
  tp.Update();target.Save();status.update(stage='COMPLETE',complete=True,elapsed_seconds=time.perf_counter()-started,inspection_file=str(F/'NativeGSD_FullCopy_20261013.CATPart'))
  write('native-gsd-spa-single-part-review.json',dict(method='CATIA_NATIVE_DMU_SPA_SINGLE_PART_GSD',rows=rows,complete=True,source_saved_by_tool=False))
 except Exception as exc:
  status.update(stage='ERROR',error=str(exc));emit('SINGLE_PART_ERROR',error=str(exc));traceback.print_exc()
 finally:
  source.Activate();ss.Clear();app.RefreshDisplay=refresh;app.HSOSynchronized=hso
  after={'name':source.Name,'full_name':source.FullName,'saved':bool(source.Saved),'bodies':sp.Bodies.Count,'hybrid_bodies':sp.HybridBodies.Count}
  status['source_state_unchanged']=after==baseline;status['elapsed_seconds']=time.perf_counter()-started;write('single-part-source-after.json',after);write('single-part-progress.json',status)
 return status
if __name__=='__main__':
 s=run();sys.exit(0 if s['complete'] else 1)
