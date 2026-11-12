"""Focused structured native SPA measurements and GSD surface intersections."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];F=ROOT/'output/全量原生DMU检查_20261012'
sys.path.insert(0,str(ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
from catia_mcp.connection import CATIAConnection

class NativeGsdSpaReviewTools:
 def __init__(self,conn):self.conn=conn
 def execute(self):
  app=self.conn.app;source=app.Documents.Item('涡轮发动机.CATPart');source.Activate();part=source.Part;sel=source.Selection;spa=source.GetWorkbench('SPAWorkbench')
  native=json.loads((F/'native-results.json').read_text(encoding='utf8'));prep=json.loads((F/'preparation-audit.json').read_text(encoding='utf8'));registry={r['id']:r for r in prep['records']};objects={};references={}
  limit=int(sys.argv[1]) if len(sys.argv)>1 else None
  if limit:
   native['conflicts']=[r for r in native['conflicts'] if r['type']=='CLASH' and any(registry[s]['kind']=='SURFACE' for s in (r['first_part_number'],r['second_part_number']))][:limit]
  needed={s for r in native['conflicts'] for s in (r['first_part_number'],r['second_part_number'])}
  for sid,r in registry.items():
   if sid not in needed:continue
   if r['kind']=='SOLID':
    obj=part.Bodies.Item(r['index']);feature=obj.Shapes.Item(obj.Shapes.Count)
   else:
    parent=part
    for index in r['set_indices']:parent=parent.HybridBodies.Item(index)
    obj=parent.HybridShapes.Item(r['index']);feature=obj
   if obj.Name!=r['name']:raise RuntimeError('Source identity changed')
   objects[sid]=obj;references[sid]=part.CreateReferenceFromObject(feature)
  before=(bool(source.Saved),int(part.Bodies.Count),int(part.HybridBodies.Count));refresh=app.RefreshDisplay;hso=app.HSOSynchronized;app.RefreshDisplay=False;app.HSOSynchronized=False
  rows=[];started=time.perf_counter()
  path=F/('native-gsd-spa-preview.json' if limit else 'native-gsd-spa-review.json')
  def save():path.write_text(json.dumps({'method':'CATIA_NATIVE_DMU_GSD_SPA','rows':rows,'complete':len(rows)==len(native['conflicts']),'elapsed_seconds':time.perf_counter()-started,'source_saved_by_tool':False},ensure_ascii=False,indent=2),encoding='utf8')
  def resolve_copied(tp,r):
   if r['kind']=='SOLID':
    body=next(tp.Bodies.Item(i) for i in range(1,tp.Bodies.Count+1) if tp.Bodies.Item(i).Name==r['name'] and tp.Bodies.Item(i).Shapes.Count>0)
    return body.Shapes.Item(body.Shapes.Count)
   def find(groups):
    for i in range(1,groups.Count+1):
     group=groups.Item(i)
     for j in range(1,group.HybridShapes.Count+1):
      obj=group.HybridShapes.Item(j)
      if obj.Name==r['name']:return obj
     obj=find(group.HybridBodies)
     if obj is not None:return obj
   obj=find(tp.HybridBodies)
   if obj is None:raise RuntimeError('Copied surface not found')
   return obj
  try:
   for n,conflict in enumerate(native['conflicts'],1):
    a,b=conflict['first_part_number'],conflict['second_part_number'];row={'pair':[a,b],'native_type':conflict['type'],'spa':{},'gsd':{'status':'NOT_REQUIRED'}};target=None
    try:
     row['spa']={'status':'COMPLETE','minimum_distance_mm':float(spa.GetMeasurable(references[a]).GetMinimumDistance(references[b])),'method':'CATIA_SPA_EXACT_SOURCE_FEATURE_REFERENCES'}
    except Exception as exc:row['spa']={'status':'ERROR','error':str(exc)}
    if conflict['type']=='CLASH' and any(registry[s]['kind']=='SURFACE' for s in (a,b)):
     try:
      target=app.Documents.Add('Part');tp=target.Part;input_surfaces=tp.HybridBodies.Add();input_surfaces.Name='InputSurfaces'
      for sid in (a,b):
       source.Activate();sel.Clear();sel.Add(objects[sid]);sel.Copy();sel.Clear();target.Activate();ds=target.Selection;ds.Clear();ds.Add(tp.MainBody if registry[sid]['kind']=='SOLID' else input_surfaces);ds.PasteSpecial('CATPrtResultWithOutLink');ds.Clear()
      oa,ob=resolve_copied(tp,registry[a]),resolve_copied(tp,registry[b]);group=tp.HybridBodies.Add();group.Name='GSD_IntersectionEvidence'
      intersection=tp.HybridShapeFactory.AddNewIntersection(tp.CreateReferenceFromObject(oa),tp.CreateReferenceFromObject(ob));intersection.Name='NativeIntersection';group.AppendHybridShape(intersection);tp.UpdateObject(intersection)
      measurable=target.GetWorkbench('SPAWorkbench').GetMeasurable(tp.CreateReferenceFromObject(intersection))
      row['gsd']={'status':'COMPLETE','intersection_created':True,'method':'CATIA_GSD_AddNewIntersection_ON_DISPOSABLE_COPY'}
      try:row['gsd']['intersection_length_mm']=float(measurable.Length)
      except Exception:row['gsd']['measurement_note']='Intersection is not a measurable curve'
      target.ExportData(str(F/'gsd-evidence'/f'{n:05d}.stp'),'stp')
      row['gsd']['evidence_file']=str(F/'gsd-evidence'/f'{n:05d}.stp')
     except Exception as exc:row['gsd']={'status':'ERROR','error':str(exc),'intersection_created':False}
     finally:
      if target is not None:
       try:target.Close()
       except Exception:pass
      source.Activate()
    rows.append(row)
    if n%20==0 or n==len(native['conflicts']):save();print(json.dumps({'stage':'NATIVE_REVIEW_PROGRESS','completed':n,'total':len(native['conflicts']),'spa_errors':sum(r['spa']['status']=='ERROR' for r in rows),'gsd_complete':sum(r['gsd']['status']=='COMPLETE' for r in rows),'gsd_errors':sum(r['gsd']['status']=='ERROR' for r in rows)},ensure_ascii=False),flush=True)
  finally:
   source.Activate();sel.Clear();app.RefreshDisplay=refresh;app.HSOSynchronized=hso
   save();data=json.loads(path.read_text(encoding='utf8'));data['source_state_unchanged']=before==(bool(source.Saved),int(part.Bodies.Count),int(part.HybridBodies.Count));path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
  return rows

if __name__=='__main__':
 (F/'gsd-evidence').mkdir(exist_ok=True);c=CATIAConnection();c.connect();NativeGsdSpaReviewTools(c).execute()
