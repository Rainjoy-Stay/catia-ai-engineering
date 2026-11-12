import sys,json,importlib.util,dataclasses
from pathlib import Path
import win32com.client
from PIL import Image
import numpy as np
import atexit
W=Path(__file__).resolve().parents[3];O=Path(sys.argv[1]).resolve();P=W/'project'
sys.path.insert(0,str(P))
s=importlib.util.spec_from_file_location('freshcap',P/'tools/report_capture_reference_20260920/capture_generic_dual_view_20261010.py');g=importlib.util.module_from_spec(s);sys.modules[s.name]=g;s.loader.exec_module(g)
a=json.loads((O/('spatial_box_analysis.json' if (O/'spatial_box_analysis.json').exists() else 'capture-staging-analysis.json')).read_text(encoding='utf8'));pipes=json.loads((O/'pipe-recognition.json').read_text(encoding='utf8'))
app=win32com.client.GetActiveObject('CATIA.Application');doc=app.ActiveDocument;sel=doc.Selection;v=app.ActiveWindow.ActiveViewer
refresh_before=bool(app.RefreshDisplay);hso_before=bool(app.HSOSynchronized)
def restore_runtime():
 try:
  app.RefreshDisplay=refresh_before;app.HSOSynchronized=hso_before;sel.Clear()
  if 'window_before' in globals():app.Width=window_before[0];app.Height=window_before[1]
 except Exception:pass
atexit.register(restore_runtime)
app.RefreshDisplay=False;app.HSOSynchronized=False
native_capture=g.capture
def capture_now(viewer,path,settle):
 sel.Clear();app.HSOSynchronized=True;app.RefreshDisplay=True
 try:native_capture(viewer,path,settle)
 finally:app.RefreshDisplay=False;app.HSOSynchronized=False
g.capture=capture_now
assert doc.Name==json.loads((O/'run-config.json').read_text(encoding='utf8'))['document'];window_before=(app.Width,app.Height);app.Width=2371;app.Height=1245;_,items=g.inventory_active_document(doc);bi={i.index:i for i in items};cam=g.snapshot_camera(app,v.Viewpoint3D);render_before=int(v.RenderingMode)
from catia_checker.catia_body_batches import iter_geometrical_elements
entities=json.loads((O/'all_entity_caches.json').read_text(encoding='utf8'));entity_map={r['shape_id']:r for r in entities};surfa=json.loads((O/'surface-import-audit.json').read_text(encoding='utf8'))
bodyitems=items;hybriditems=[];source_to_native={str(i.index):i for i in bodyitems}
for obj,identity in iter_geometrical_elements(doc.Part):
 item=g.Item(len(bodyitems)+len(hybriditems)+1,identity['source_body_name'],identity['source_path'],'surface',obj,obj);hybriditems.append(item);source_to_native[str(identity['source_body_index'])]=item
items=bodyitems+hybriditems;bi={i.index:i for i in items};finite_surfaces={str(r['index']) for r in surfa['all_finite_records']}
jobs=[]
for p in pipes:
 if p['candidate']['geometry_kind']!='UNDETERMINED':jobs.append({'id':f"PIPE_{p['source_body_index']}",'indices':[source_to_native[str(p['source_body_index'])].index],'source_indices':[p['source_body_index']],'names':[p['source_body_name']],'source_paths':[entity_map[f"BODY_{p['source_body_index']:06d}"]['source_path']],'candidate':p['candidate']})
for r in sorted(a['records'],key=lambda r:r.get('fact',{}).get('intersection_volume_mm3',0),reverse=True):
 if r.get('fact',{}).get('intersection_volume_mm3',0)>1e-6 or r.get('fact',{}).get('surface_intersection') or 'error' in r:
  ids=[r['object_a'],r['object_b']];jobs.append({'id':ids[0]+'__'+ids[1],'indices':[source_to_native[str(entity_map[sid]['index'])].index for sid in ids],'source_indices':[r['body_a'],r['body_b']],'names':[r['name_a'],r['name_b']],'source_paths':[entity_map[sid]['source_path'] for sid in ids],'fact':r.get('fact',{}),'error':r.get('error'),'category':r['decision']['category']})
targets={i for j in jobs for i in j['indices']};states={i:g.snapshot_display(sel,bi[i]) for i in targets}
def select(objects):
 sel.Clear()
 for obj in objects:sel.Add(obj)
 return sel.VisProperties
props=select(i.tree_object for i in items);show_result=props.GetShow();sel.Clear()
props=select(i.display_object for i in items);opacity_result=props.GetRealOpacity();inherit_result=props.GetRealInheritance(g.PROP_OPACITY);sel.Clear()
# A CATIA defined status of zero proves all selected nodes share this property.
opacity_groups={}
if opacity_result[0]!=0:
 for item in items:
  props=select([item.display_object]);values=props.GetRealOpacity();flags=props.GetRealInheritance(g.PROP_OPACITY)
  key=(g._out_values(values,1,'opacity')[0],g._out_values(flags,1,'inherit')[0]);opacity_groups.setdefault(key,[]).append(item)
 sel.Clear();print('OPACITY_SNAPSHOT', {str(k):len(v) for k,v in opacity_groups.items()},flush=True)
 (O/'original-opacity-groups.json').write_text(json.dumps({str(k):[i.index for i in group] for k,group in opacity_groups.items()}),encoding='utf8')
show_groups={}
if show_result[0]!=0:
 for item in items:show_groups.setdefault(g._read_show(sel,item.tree_object),[]).append(item)
inherit_groups={}
if inherit_result[0]!=0:
 for item in items:
  values=select([item.display_object]).GetRealInheritance(g.PROP_OPACITY)
  value=g._out_values(values,1,'inherit')[0]
  inherit_groups.setdefault(value,[]).append(item)
 sel.Clear()
 print('INHERITANCE_SNAPSHOT', {k:len(v) for k,v in inherit_groups.items()},flush=True)
orig_show=g._out_values(show_result,1,'show')[0];orig_opacity=g._out_values(opacity_result,1,'opacity')[0];orig_inherit=g._out_values(inherit_result,1,'inherit')[0]
sets=[(doc.Part.HybridBodies.Item(k),g._read_show(sel,doc.Part.HybridBodies.Item(k))) for k in range(1,doc.Part.HybridBodies.Count+1)]
audit={'document':doc.Name,'body_count':len(bodyitems),'hybrid_count':len(hybriditems),'jobs':jobs,'states':{str(i):dataclasses.asdict(s) for i,s in states.items()},'uniform_original':{'show':orig_show,'opacity':orig_opacity,'opacity_inheritance':orig_inherit},'show_groups':{str(k):[i.index for i in v] for k,v in show_groups.items()},'opacity_inheritance_groups':{str(k):[i.index for i in v] for k,v in inherit_groups.items()},'camera_before':cam,'rendering_before':render_before,'capture_rendering':0,'capture_view':'ISOMETRIC','restored':False}
(O/'capture-state-before.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
def allshow(show):select(i.tree_object for i in items).SetShow(show);sel.Clear()
def allopacity(op,inherit=0):select(i.display_object for i in items).SetRealOpacity(op,inherit);sel.Clear()
try:
 v.RenderingMode=0
 allshow(0)
 for obj,_ in sets:select([obj]).SetShow(0)
 for item in hybriditems:
  if next((key for key,value in source_to_native.items() if value is item),None) not in finite_surfaces:select([item.tree_object]).SetShow(1)
 sel.Clear();g.set_view(v,'isometric');v.Reframe();v.Viewpoint3D.Zoom*=.60;fullcam=g.snapshot_camera(app,v.Viewpoint3D)
 allopacity(52)
 for j in jobs:
  d=O/'native-evidence'/j['id'];d.mkdir(parents=True,exist_ok=True)
  for role in ['context_image','context_locator','detail_image','detail_locator']:j[role]=str(d/(role+'.jpg'))
  for n,i in enumerate(j['indices']):g.set_display(sel,bi[i],show=0,color=g.DEFAULT_TARGET_COLORS[n],opacity=255)
  g.restore_camera(v.Viewpoint3D,fullcam);g.capture(v,Path(j['context_image']),.2);j['macro_visible_body_count']=len(bodyitems);j['macro_visible_surface_count']=len(finite_surfaces);j['macro_background_opacity']=52;j['full_camera']=fullcam
  for i in j['indices']:g.restore_display(sel,bi[i],states[i]);g.set_display(sel,bi[i],show=0,opacity=52)
  print('MACRO_CAPTURED',j['id'],flush=True)
 allshow(1);last=None
 for j in jobs:
  if last is not None:g.set_display(sel,last,show=1)
  b=bi[j['indices'][-1]];g.set_display(sel,b,show=0,color=(255,161,56),opacity=255);g.restore_camera(v.Viewpoint3D,fullcam);g.capture(v,Path(j['context_locator']),.2);last=b
 # Local images contain precisely the one candidate or the interference pair.
 if last is not None:g.set_display(sel,last,show=1)
 for j in jobs:
  b=bi[j['indices'][-1]];g.set_display(sel,b,show=0,color=(255,161,56),opacity=255)
  g.set_view(v,'isometric');v.Reframe();v.Viewpoint3D.Zoom*=.62
  trial=Path(j['detail_locator']);g.capture(v,trial,.2)
  arr=np.asarray(Image.open(trial).convert('RGB'));h,w=arr.shape[:2];roi=arr[int(h*.20):int(h*.92),int(w*.18):int(w*.88)]
  mask=(roi[:,:,0]>180)&(roi[:,:,1]>65)&(roi[:,:,1]<210)&(roi[:,:,2]<130);ys,xs=np.where(mask)
  if len(xs)<30 or (len(xs) and max(np.ptp(xs)+1,np.ptp(ys)+1)/max(1,min(np.ptp(xs)+1,np.ptp(ys)+1))>8):
   v.Viewpoint3D.PutSightDirection((1.,-1.,-1.));v.Viewpoint3D.PutUpDirection((0.,1.,0.));v.Reframe();v.Viewpoint3D.Zoom*=.62
  for n,i in enumerate(j['indices']):g.set_display(sel,bi[i],show=0,color=g.DEFAULT_TARGET_COLORS[n],opacity=52 if n==0 and len(j['indices'])==2 else 255)
  g.capture(v,Path(j['detail_image']),.2);j['local_visible_body_indices']=j['indices'];j['detail_camera']=g.snapshot_camera(app,v.Viewpoint3D)
  if len(j['indices'])==2:g.set_display(sel,bi[j['indices'][0]],show=1)
  g.set_display(sel,b,show=0,color=(255,161,56),opacity=255);g.capture(v,Path(j['detail_locator']),.2)
  g.set_display(sel,b,show=1);print('LOCAL_CAPTURED',j['id'],flush=True)
finally:
 if opacity_groups:
  for (op,flag),group in opacity_groups.items():select(i.display_object for i in group).SetRealOpacity(op,flag)
  sel.Clear()
 elif inherit_groups:
  for flag,group in inherit_groups.items():select(i.display_object for i in group).SetRealOpacity(orig_opacity,flag)
  sel.Clear()
 else:allopacity(orig_opacity,orig_inherit)
 for i,state in states.items():g.restore_display(sel,bi[i],state)
 if show_groups:
  for flag,group in show_groups.items():select(i.tree_object for i in group).SetShow(flag)
  sel.Clear()
 else:allshow(orig_show)
 for obj,show in sets:select([obj]).SetShow(show)
 sel.Clear();v.RenderingMode=render_before;g.restore_camera(v.Viewpoint3D,cam);v.Update();app.Width=window_before[0];app.Height=window_before[1];audit['restored']=True;audit['source_saved_by_tool']=False
 (O/'capture-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
print('FRESH_CAPTURE_COMPLETE',len(jobs),flush=True)
