"""Structured full-model inspection derivative and native clash operation."""
import sys,json,time,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
sys.path.insert(0,str(Path(__file__).parent))
from catia_mcp.connection import CATIAConnection
from catia_mcp.tools.measurement import MeasurementTools
from surface_derivative_tool import get_cog

class FullNativeInspectionTools:
 def __init__(self,conn):self.conn=conn
 def execute(self,name,args):
  if name!='catia_full_native_inspection':raise ValueError(name)
  folder=Path(args['output_directory']).resolve();folder.mkdir(parents=True,exist_ok=True)
  parts=folder/'parts';parts.mkdir(exist_ok=True)
  c=self.conn;app=c.app;source=app.Documents.Item(args['source_document']);source.Activate();part=source.Part;spa=source.GetWorkbench('SPAWorkbench')
  before=(bool(source.Saved),int(part.Bodies.Count),int(part.HybridBodies.Count));sel=source.Selection
  saved_selection=[sel.Item2(i).Value for i in range(1,sel.Count2+1)]
  objects=[]
  for i in range(1,part.Bodies.Count+1):
   obj=part.Bodies.Item(i);objects.append({'id':f'BODY_{i:06d}','name':str(obj.Name),'source_path':f'Part/Bodies[{i}]/{obj.Name}','kind':'SOLID','object':obj,'index':i})
  def walk(collection,indices=[],path='Part'):
   for i in range(1,collection.Count+1):
    group=collection.Item(i);ii=indices+[i];gp=path+'/'+str(group.Name)
    for j in range(1,group.HybridShapes.Count+1):
     obj=group.HybridShapes.Item(j);objects.append({'id':'GEOM_'+'_'.join(map(str,ii))+f'_E{j:04d}','name':str(obj.Name),'source_path':gp+'/'+str(obj.Name),'kind':'SURFACE','object':obj,'set_indices':ii,'index':j})
    walk(group.HybridBodies,ii,gp)
  walk(part.HybridBodies)
  def serial(r):return {k:v for k,v in r.items() if k!='object'}
  def save(name,value):(folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
  audit={'source_document':source.Name,'registered':len(objects),'registered_bodies':part.Bodies.Count,'registered_geometry':len(objects)-part.Bodies.Count,'records':[],'errors':[],'excluded_nonphysical':[],'status':'RUNNING','source_saved_by_tool':False}
  def event(stage,**kw):print(json.dumps({'stage':stage,**kw},ensure_ascii=False),flush=True)
  save('inventory.json',[serial(r) for r in objects]);original_refresh=app.RefreshDisplay;original_hso=app.HSOSynchronized;start=time.perf_counter()
  app.RefreshDisplay=False;app.HSOSynchronized=False
  try:
   for n,r in enumerate(objects,1):
    p=parts/(r['id']+'.CATPart');target=None
    try:
     source.Activate();m=spa.GetMeasurable(part.CreateReferenceFromObject(r['object']))
     try:r['area_mm2']=float(m.Area)*1e6
     except Exception:r['area_mm2']=None
     if r['kind']=='SURFACE' and (r['area_mm2'] is None or r['area_mm2']<=0):
      r['coverage']='UNRESOLVED_SURFACE_MEASUREMENT';audit['errors'].append({**serial(r),'error':'Surface area unavailable; retained as unresolved, not silently excluded'});continue
     try:r['centroid_mm']=get_cog(m)
     except Exception:r['centroid_mm']=None
     if r['kind']=='SOLID':
      try:r['volume_mm3']=float(m.Volume)*1e9
      except Exception:r['volume_mm3']=None
     sel.Clear();sel.Add(r['object']);sel.Copy();sel.Clear();target=app.Documents.Add('Part');target.Product.PartNumber=r['id'];tp=target.Part;dest=target.Selection
     container=tp.MainBody if r['kind']=='SOLID' else tp.HybridBodies.Add();container.Name=r['name'];dest.Clear();dest.Add(container);dest.PasteSpecial('CATPrtResultWithOutLink');dest.Clear()
     tp.Update()
     if r['kind']=='SOLID':
      nonempty=[tp.Bodies.Item(i) for i in range(1,tp.Bodies.Count+1) if tp.Bodies.Item(i).Shapes.Count>0]
      if len(nonempty)!=1:raise RuntimeError('Copied solid body count mismatch')
      copied=nonempty[0].Shapes.Item(1)
     else:
      if container.HybridShapes.Count!=1:raise RuntimeError('Surface count mismatch')
      copied=container.HybridShapes.Item(1)
     cm=target.GetWorkbench('SPAWorkbench').GetMeasurable(tp.CreateReferenceFromObject(copied))
     ca=float(cm.Area)*1e6
     if r['area_mm2'] is not None and abs(ca-r['area_mm2'])>max(1e-5,abs(ca)*1e-8):raise RuntimeError('Copy area mismatch')
     cc=get_cog(cm)
     if r['centroid_mm'] is not None and math.dist(cc,r['centroid_mm'])>1e-5:raise RuntimeError('Copy location mismatch')
     dest.Add(copied);dest.VisProperties.SetShow(0);dest.Clear();target.SaveAs(str(p));r.update(file=str(p),copied_area_mm2=ca,copied_centroid_mm=cc,coverage='COPIED_VERIFIED');audit['records'].append(serial(r));target.Close();target=None
    except Exception as exc:
     audit['errors'].append({**serial(r),'error':str(exc)})
     if target is not None:
      try:target.Close()
      except Exception:pass
    finally:
     if n%10==0 or n==len(objects):save('preparation-audit.json',audit);event('COPY_PROGRESS',processed=n,total=len(objects),copied=len(audit['records']),errors=len(audit['errors']),elapsed_seconds=time.perf_counter()-start)
   product=app.Documents.Add('Product');product.Product.PartNumber=args['product_name']
   for n,r in enumerate(audit['records'],1):
    product.Product.Products.AddComponentsFromFiles([r['file']],'All')
    if n%100==0:event('ASSEMBLY_PROGRESS',loaded=n,total=len(audit['records']))
   product.Product.Update();product.SaveAs(str(folder/(args['product_name']+'.CATProduct')))
   audit.update(status='COMPLETE' if not audit['errors'] else 'PARTIAL',elapsed_seconds=time.perf_counter()-start,component_count=product.Product.Products.Count)
  finally:
   source.Activate();sel.Clear()
   for obj in saved_selection:sel.Add(obj)
   audit['source_state_unchanged']=before==(bool(source.Saved),int(part.Bodies.Count),int(part.HybridBodies.Count));save('preparation-audit.json',audit);app.RefreshDisplay=original_refresh;app.HSOSynchronized=original_hso
  product.Activate();event('CLASH_START',component_count=product.Product.Products.Count)
  started=time.perf_counter();native=json.loads(MeasurementTools(c)._scan_product_clashes(args['clearance_mm'],None,[],1000000));native['tool_seconds']=time.perf_counter()-started
  save('native-results.json',native);event('CLASH_COMPLETE',seconds=native['tool_seconds'],counts=native['counts'],total=native['raw_conflict_count'])
  return native

if __name__=='__main__':
 c=CATIAConnection();print(c.connect(),flush=True)
 FullNativeInspectionTools(c).execute('catia_full_native_inspection',{'source_document':'涡轮发动机.CATPart','output_directory':str(ROOT/'output/全量原生DMU检查_20261012'),'product_name':'NativeDMU_Full_20261012','clearance_mm':.1})
