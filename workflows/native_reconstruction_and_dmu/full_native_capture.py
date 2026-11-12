"""CATIA native dual views; exact derived components; restore all display state."""
import sys,json,time,importlib.util,dataclasses,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];F=ROOT/'output/全量原生DMU检查_20261012'
P=ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/project/tools/report_capture_reference_20260920'
sys.path.insert(0,str(ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'));sys.path.insert(0,str(P))
spec=importlib.util.spec_from_file_location('native_capture_generic',P/'capture_generic_dual_view_20261010.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
g.PROP_COLOR=2;g.PROP_OPACITY=3  # Confirmed from installed InfTypeLib.tlb.
original_set_display=g.set_display

def verified_cached_states(selection,group,field,tree=False):
 """Validate previous restored state in property groups rather than per object."""
 try:
  old=json.loads((F/'capture-audit.json').read_text(encoding='utf8'))
  if not old.get('restored') or old.get('document')!='NativeDMU_Full_20261012.CATProduct':raise ValueError('No restored cache')
  cache=old[field];buckets={};states={}
  for item in group:
   state=g.DisplayState(**cache[item.key]);state.color=tuple(state.color);states[item.key]=state
   key=(state.show,state.color,state.color_inheritance,state.opacity,state.opacity_inheritance);buckets.setdefault(key,[]).append(item)
  for key,members in buckets.items():
   selection.Clear()
   for item in members:selection.Add(item.tree_object)
   show=selection.VisProperties.GetShow();selection.Clear()
   for item in members:selection.Add(item.tree_object if tree else item.display_object)
   p=selection.VisProperties;values=[show,p.GetRealColor(),p.GetRealInheritance(g.PROP_COLOR),p.GetRealOpacity(),p.GetRealInheritance(g.PROP_OPACITY)]
   if not all(isinstance(v,tuple) and v[0]==0 for v in values):raise ValueError('Mixed cache group')
   actual=(g._out_values(values[0],1,'show')[0],g._out_values(values[1],3,'color'),g._out_values(values[2],1,'inheritance')[0],g._out_values(values[3],1,'opacity')[0],g._out_values(values[4],1,'inheritance')[0])
   if actual!=key:raise ValueError('Cache changed')
  selection.Clear();return states
 except (ValueError,KeyError,TypeError):
  return {i.key:g.snapshot_display(selection,dataclasses.replace(i,display_object=i.tree_object) if tree else i) for i in group}
def inherited_display(*args,**kwargs):
 kwargs.setdefault('color_inheritance',1);kwargs.setdefault('opacity_inheritance',1)
 return original_set_display(*args,**kwargs)
g.set_display=inherited_display
from catia_mcp.connection import CATIAConnection
from report_highlight_bounds import highlight_bounds
from PIL import Image,ImageDraw
import numpy as np

def save(name,value):(F/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def event(stage,**kw):print(json.dumps({'stage':stage,**kw},ensure_ascii=False),flush=True)
c=CATIAConnection();c.connect();app=c.app;doc=app.Documents.Item('NativeDMU_Full_20261012.CATProduct');doc.Activate();sel=doc.Selection;viewer=app.ActiveWindow.ActiveViewer
boot_refresh=app.RefreshDisplay;boot_hso=app.HSOSynchronized;app.RefreshDisplay=False;app.HSOSynchronized=False
native=json.loads((F/'native-results.json').read_text(encoding='utf8'));prep=json.loads((F/'preparation-audit.json').read_text(encoding='utf8'));records={r['id']:r for r in prep['records']}
_,items=g.inventory_active_document(doc);im={str(i.tree_object.PartNumber):i for i in items}
if set(im)!=set(records):raise RuntimeError('Capture model does not match inspection registry')
actual_items=[]
event('CAPTURE_PREPARING',components=len(items))
for item in items:
 pd=item.tree_object.ReferenceProduct.Parent;part=pd.Part;sid=str(item.tree_object.PartNumber)
 if records[sid]['kind']=='SOLID':
  body=next(part.Bodies.Item(k) for k in range(1,part.Bodies.Count+1) if part.Bodies.Item(k).Shapes.Count>0)
  shape=body.Shapes.Item(body.Shapes.Count)
 else:shape=part.HybridBodies.Item(1).HybridShapes.Item(1)
 actual_items.append(g.Item(item.index,item.name,item.path,item.kind,item.tree_object,shape))
items=actual_items;im={str(i.tree_object.PartNumber):i for i in items}
before_saved=bool(doc.Saved);refresh=boot_refresh;hso=boot_hso
app.RefreshDisplay=False;app.HSOSynchronized=False
sel.Clear()
for i in items:sel.Add(i.tree_object)
tree_props=sel.VisProperties
tree_bulk=[tree_props.GetShow(),tree_props.GetRealColor(),tree_props.GetRealOpacity(),tree_props.GetRealInheritance(g.PROP_COLOR),tree_props.GetRealInheritance(g.PROP_OPACITY)]
if all(isinstance(v,tuple) and v[0]==0 for v in tree_bulk):
 tree_uniform=g.DisplayState(g._out_values(tree_bulk[0],1,'show')[0],g._out_values(tree_bulk[1],3,'color'),g._out_values(tree_bulk[3],1,'color inheritance')[0],g._out_values(tree_bulk[2],1,'opacity')[0],g._out_values(tree_bulk[4],1,'opacity inheritance')[0]);tree_states={i.key:tree_uniform for i in items}
else:tree_states=verified_cached_states(sel,items,'tree_state_before',tree=True)
sel.Clear()
for item in items:sel.Add(item.tree_object)
props=sel.VisProperties;show_result=props.GetShow();props.SetRealColor(255,255,255,0);props.SetRealOpacity(255,0)
sel.Clear()
for item in items:sel.Add(item.display_object)
props=sel.VisProperties
bulk=[show_result,props.GetRealColor(),props.GetRealOpacity(),props.GetRealInheritance(g.PROP_COLOR),props.GetRealInheritance(g.PROP_OPACITY)]
if all(isinstance(v,tuple) and v[0]==0 for v in bulk):
 uniform=g.DisplayState(g._out_values(bulk[0],1,'show')[0],g._out_values(bulk[1],3,'color'),g._out_values(bulk[3],1,'color inheritance')[0],g._out_values(bulk[2],1,'opacity')[0],g._out_values(bulk[4],1,'opacity inheritance')[0])
 states={i.key:uniform for i in items}
else:states=verified_cached_states(sel,items,'state_before')
sel.Clear();aux=[]
for item in items:
 pd=item.tree_object.ReferenceProduct.Parent;origin=pd.Part.OriginElements
 aux.extend([origin.PlaneXY,origin.PlaneYZ,origin.PlaneZX])
sel.Clear()
for obj in aux:sel.Add(obj)
aux_show=sel.VisProperties.GetShow();aux_states=None
if aux_show[0]!=0:
 aux_states=[g._read_show(sel,obj) for obj in aux]
 sel.Clear()
 for obj in aux:sel.Add(obj)
sel.VisProperties.SetShow(1);sel.Clear()
cam=g.snapshot_camera(app,viewer.Viewpoint3D);render=viewer.RenderingMode
audit={'document':doc.Name,'saved_before':before_saved,'restored':False,'state_before':{i.key:dataclasses.asdict(states[i.key]) for i in items},'tree_state_before':{k:dataclasses.asdict(v) for k,v in tree_states.items()},'camera_before':cam,'auxiliary_plane_count':len(aux),'auxiliary_plane_show_before':aux_show,'jobs':[]}
save('capture-state-before.json',audit)
layout=json.loads((F/'capture-layout.json').read_text(encoding='utf-8-sig'))
if layout.get('excluded') and isinstance(layout['excluded'][0],int):layout['excluded']=[layout['excluded']]
def display(group,show=None,color=None,opacity=None):
 sel.Clear()
 if show is not None:
  if group is items:
   # Native selection search avoids 1672 COM Add calls. Validate identity
   # before changing visibility; fall back when the query is unsupported.
   try:
    sel.Search('CATAsmSearch.Product,all')
    for k in range(sel.Count2,0,-1):
     obj=sel.Item2(k).Value
     if obj is None or str(obj.PartNumber) not in im:sel.Remove2(k)
    found={str(sel.Item2(k).Value.PartNumber) for k in range(1,sel.Count2+1)}
    if found!=set(im) or sel.Count2!=len(items):raise ValueError('Native selection differs from registry')
   except Exception:
    sel.Clear()
    for i in group:sel.Add(i.tree_object)
  else:
   for i in group:sel.Add(i.tree_object)
  sel.VisProperties.SetShow(show);sel.Clear()
 if color is None and opacity is None:return
 for i in group:sel.Add(i.display_object)
 p=sel.VisProperties
 if color is not None:p.SetRealColor(*color,1)
 if opacity is not None:p.SetRealOpacity(opacity,1)
 sel.Clear()
def capture(path):
 app.HSOSynchronized=True;app.RefreshDisplay=True;g.capture(viewer,path,.08);app.RefreshDisplay=False;app.HSOSynchronized=False
 size=Image.open(path).size
 if size!=tuple(layout['expected_size']):
  if size not in ((1844,894),(1880,894),(1632,930),(2445,1325),(2074,919)):raise RuntimeError('Unverified capture dimensions; viewport must be remeasured')
  width,height=size;center=width//2
  scale=min(width/1844,height/894);half=min(round(645*scale),center-round(250*scale));mid=height//2;vertical=round(293*scale)
  layout.update(expected_size=list(size),report_crop=[center-half,mid-vertical,center+half,mid+vertical],viewport=[round(250*scale),round(20*scale),width-round(24*scale),height-round(24*scale)],compass=[width-round(204*scale),round(35*scale),width-round(34*scale),round(185*scale)],excluded=[[width-round(104*scale),height-round(124*scale),width,height]])
  audit['verified_layout']=layout;event('CAPTURE_SIZE_ADAPTED',width=width,height=height)

def fit_visible(view):
 app.RefreshDisplay=True;app.HSOSynchronized=True
 if not math.isfinite(viewer.Viewpoint3D.Zoom):viewer.Viewpoint3D.Zoom=1.0
 viewer.Update();g.set_view(viewer,view);viewer.Reframe()
 if not math.isfinite(viewer.Viewpoint3D.Zoom):raise RuntimeError('Native camera zoom invalid after Reframe; recover before continuing')
 viewer.Viewpoint3D.Zoom*=.62;viewer.Update();app.RefreshDisplay=False;app.HSOSynchronized=False
def annotate(raw,locator,out,label):
 image=Image.open(raw).convert('RGB');loc=Image.open(locator).convert('RGB');a=np.asarray(loc);v=layout['viewport'];comp=layout['compass'];excluded=layout.get('excluded',[])
 # Isolated locator is a separate native projection of the smaller object in
 # the exact same camera, used to establish target ROI independently of context.
 mask=(a[:,:,0]>a[:,:,2]+45)&(a[:,:,0]>100)&(a[:,:,1]>60)&(a[:,:,1]<220)
 allowed=np.zeros(mask.shape,bool);allowed[v[1]:v[3],v[0]:v[2]]=True
 for r in [comp,*excluded]:allowed[r[1]:r[3],r[0]:r[2]]=False
 ys,xs=np.where(mask&allowed)
 if len(xs)<12:return {'status':'NEEDS_REVIEW','reason':'Locator projection too small','raw':str(raw)}
 roi=[max(v[0],int(xs.min())-45),max(v[1],int(ys.min())-45),min(v[2],int(xs.max())+46),min(v[3],int(ys.max())+46)]
 result=highlight_bounds(loc,viewport=v,compass=comp,target_roi=roi,excluded=excluded,pad=20)
 result.update(raw=str(raw),locator=str(locator),roi_method='ISOLATED_NATIVE_OBJECT_SAME_CAMERA_PROJECTION')
 if result['status']=='OK':
  draw=ImageDraw.Draw(image);draw.rectangle(result['box'],outline='red',width=5)
  # Crop only the documented UI-free model viewport. Box is in raw coordinates.
  crop=layout['report_crop'];image.crop(crop).save(out,quality=90);result['annotated']=str(out)
 return result

app.RefreshDisplay=False;app.HSOSynchronized=False
try:
 viewer.RenderingMode=0;display(items,show=0,color=(185,190,198),opacity=255);fit_visible('isometric')
 capture(F/'full-model-native-raw.jpg');Image.open(F/'full-model-native-raw.jpg').crop(layout['report_crop']).save(F/'full-model-native.jpg',quality=93);display(items,show=1)
 fullcam=g.snapshot_camera(app,viewer.Viewpoint3D)
 scope_path=F/'report-scope.json'
 scope=json.loads(scope_path.read_text(encoding='utf-8-sig')) if scope_path.exists() else {'minimum_depth_mm':1.0}
 previous=[];issues=sorted([r for r in native['conflicts'] if r['type']=='CLASH' and r.get('interference_depth_mm',0)>=scope['minimum_depth_mm']],key=lambda r:-r['interference_depth_mm'])
 audit['scope']=scope;audit['queue_total']=len(issues)
 accepted={}
 repair='--repair' in sys.argv
 repair_limit=next((int(arg.split('=',1)[1]) for arg in sys.argv if arg.startswith('--repair-limit=')),None);repair_count=0;prior_jobs={}
 if repair or (len(sys.argv)==1 and (F/'capture-pilot-accepted.json').exists()):
  approval=json.loads((F/'capture-pilot-accepted.json').read_text(encoding='utf-8-sig'));prior=json.loads((F/'capture-audit.json').read_text(encoding='utf8'))
  prior_jobs={j['issue_id']:j for j in prior['jobs']}
  if prior.get('restored') or prior.get('reopened_from_saved_model'):
   accepted={j['issue_id']:j for j in prior['jobs'] if (repair or j['issue_id'] in approval.get('issue_ids',[])) and j['status']=='OK'}
 if len(sys.argv)>1 and not repair:issues=issues[:int(sys.argv[1])]
 for n,conflict in enumerate(issues,1):
  ids=[conflict['first_part_number'],conflict['second_part_number']]
  # Keep the smaller object as B for a readable object-location frame.
  if (records[ids[0]].get('area_mm2') or 0)<(records[ids[1]].get('area_mm2') or 0):ids.reverse()
  pair=[im[s] for s in ids];issue=f'DMU-{n:05d}';directory=F/'evidence'/issue;directory.mkdir(parents=True,exist_ok=True)
  if repair_limit is not None and repair_count>=repair_limit:
   audit['jobs'].append(prior_jobs[issue]);continue
  cached=accepted.get(issue)
  if cached and cached['native']==conflict and all(Path(cached[k]['annotated']).is_file() for k in ('context','detail')):
   audit['jobs'].append(cached);save('capture-audit.json',audit);event('CAPTURE_REUSED',completed=n,total=len(issues));continue
  repair_count+=1
  context=items;display(context,show=0,color=(185,190,198),opacity=52)
  for i,color in zip(pair,g.DEFAULT_TARGET_COLORS):g.set_display(sel,i,show=0,color=color,opacity=255)
  fit_visible('isometric');context_cam=g.snapshot_camera(app,viewer.Viewpoint3D)
  raw=directory/'context-raw.jpg';capture(raw);display(context,show=1);g.set_display(sel,pair[1],show=0,color=g.DEFAULT_TARGET_COLORS[0],opacity=255)
  locator=directory/'context-locator.jpg';capture(locator);g.set_display(sel,pair[1],show=1)
  context_result=annotate(raw,locator,directory/'context.jpg',issue)
  context_locator_id=ids[1]
  if context_result['status']!='OK':
   # A is a genuine member of the pair; use its native projection when B is
   # too small in the complete-model view. Never invent a central frame.
   g.set_display(sel,pair[0],show=0,color=g.DEFAULT_TARGET_COLORS[0],opacity=255);capture(locator);g.set_display(sel,pair[0],show=1)
   context_result=annotate(raw,locator,directory/'context.jpg',issue);context_locator_id=ids[0]
  context_result['locator_object_id']=context_locator_id
  for i,color in zip(pair,g.DEFAULT_TARGET_COLORS):g.set_display(sel,i,show=0,color=color,opacity=255)
  fit_visible('isometric');detail_cam=g.snapshot_camera(app,viewer.Viewpoint3D)
  raw2=directory/'detail-raw.jpg';capture(raw2)
  def visible_colors(path,transparent_a=False):
   a=np.asarray(Image.open(path).convert('RGB')).astype(int);r=layout['report_crop'];a=a[r[1]:r[3],r[0]:r[2]]
   orange=(a[:,:,0]-a[:,:,2]>45)&(a[:,:,0]>90)&(a[:,:,1]>50)&(a[:,:,1]<220)
   cyan=(a[:,:,1]-a[:,:,0]>35)&(a[:,:,2]-a[:,:,0]>35)&(a[:,:,1]>80)
   if transparent_a:
    # Native orange-over-cyan blending produces green; opaque orange and
    # the blue viewport do not satisfy this mask. Still requires visual QA.
    cyan|=(a[:,:,1]-a[:,:,0]>8)&(a[:,:,1]-a[:,:,2]>8)&(a[:,:,1]>60)
   return [int(orange.sum()),int(cyan.sum())]
  pixels=visible_colors(raw2);view='isometric'
  if min(pixels)<12:
   for trial_view in ('front','back','top','right'):
    fit_visible(trial_view);capture(raw2);trial=visible_colors(raw2)
    pixels=trial;view=trial_view
    if min(trial)>=12:break
  detail_opacity_a=255
  if min(pixels)<12:
   g.set_display(sel,pair[0],opacity=127);fit_visible('isometric');capture(raw2);pixels=visible_colors(raw2,transparent_a=True);view='isometric';detail_opacity_a=127
  detail_cam=g.snapshot_camera(app,viewer.Viewpoint3D)
  g.set_display(sel,pair[0],show=1);g.set_display(sel,pair[1],color=g.DEFAULT_TARGET_COLORS[0],opacity=255)
  locator2=directory/'detail-locator.jpg';capture(locator2);detail_result=annotate(raw2,locator2,directory/'detail.jpg',issue)
  detail_result['opacity_a']=detail_opacity_a
  if detail_opacity_a!=255:detail_result['opacity_reason']='A_OCCLUDES_B_NATIVE_VIEW'
  # Red location frame is an object locator, never an exact interference boundary.
  job={'issue_id':issue,'native':conflict,'object_ids':ids,'objects':[records[s] for s in ids],'context_ids':[str(i.tree_object.PartNumber) for i in context],'context_camera':context_cam,'detail_camera':detail_cam,'detail_view':view,'detail_color_pixels':pixels,'context':context_result,'detail':detail_result,'status':'OK' if context_result['status']==detail_result['status']=='OK' and min(pixels)>=12 else 'NEEDS_REVIEW'}
  audit['jobs'].append(job);save('capture-audit.json',audit);display(pair,show=1,color=(185,190,198),opacity=52);previous=context
  if n%10==0 or n==len(issues):event('CAPTURE_PROGRESS',completed=n,total=len(issues),needs_review=sum(j['status']!='OK' for j in audit['jobs']))
finally:
 grouped={}
 for i in items:
  state=states[i.key];key=(state.show,state.color,state.color_inheritance,state.opacity,state.opacity_inheritance);grouped.setdefault(key,[]).append(i)
 for key,group in grouped.items():
  sel.Clear()
  for i in group:sel.Add(i.tree_object)
  sel.VisProperties.SetShow(key[0]);sel.Clear()
  for i in group:sel.Add(i.display_object)
  props=sel.VisProperties;props.SetRealColor(*key[1],key[2]);props.SetRealOpacity(key[3],key[4]);sel.Clear()
 tree_groups={}
 for i in items:
  t=tree_states[i.key];key=(t.show,t.color,t.color_inheritance,t.opacity,t.opacity_inheritance);tree_groups.setdefault(key,[]).append(i)
 for key,group in tree_groups.items():
  sel.Clear()
  for i in group:sel.Add(i.tree_object)
  p=sel.VisProperties;p.SetShow(key[0]);p.SetRealColor(*key[1],key[2]);p.SetRealOpacity(key[3],key[4])
 for show in (0,1):
  sel.Clear()
  for index,obj in enumerate(aux):
   original=aux_states[index] if aux_states is not None else g._out_values(aux_show,1,'aux show')[0]
   if original==show:sel.Add(obj)
  if sel.Count2:sel.VisProperties.SetShow(show)
  sel.Clear()
 g.restore_camera(viewer.Viewpoint3D,cam);viewer.RenderingMode=render;sel.Clear();app.RefreshDisplay=refresh;app.HSOSynchronized=hso;viewer.Update()
 audit['restored']=True
 try:audit['saved_after']=bool(doc.Saved)
 except Exception as exc:audit['restored']=False;audit['restore_verification_error']=str(exc)
 audit['source_saved_by_tool']=False;save('capture-audit.json',audit)
event('CAPTURE_COMPLETE',total=len(audit['jobs']))

