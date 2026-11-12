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

ledger=json.loads((F/'capture-state-before.json').read_text(encoding='utf8'))
audit=json.loads((F/'capture-audit.json').read_text(encoding='utf8'))
states={k:g.DisplayState(**v) for k,v in ledger['state_before'].items()}
tree_states={k:g.DisplayState(**v) for k,v in ledger['tree_state_before'].items()}

for state in list(states.values())+list(tree_states.values()):state.color=tuple(state.color)
cam=ledger['camera_before'];render=viewer.RenderingMode;refresh=True;hso=True
aux=[]
for item in items:
 origin=item.tree_object.ReferenceProduct.Parent.Part.OriginElements
 aux.extend([origin.PlaneXY,origin.PlaneYZ,origin.PlaneZX])
aux_show=tuple(ledger['auxiliary_plane_show_before']);aux_states=None
if aux_show[0]!=0:raise RuntimeError('Nonuniform auxiliary state requires recovery')
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
audit['restored']=True;audit['saved_after']=bool(doc.Saved);audit['source_saved_by_tool']=False;save('capture-audit.json',audit)
backup=json.loads((F/'capture-audit-before-resume-pilot.json').read_text(encoding='utf8'))
merged={j['issue_id']:j for j in backup['jobs']}
merged.update({j['issue_id']:j for j in audit['jobs']})
audit['jobs']=[merged[k] for k in sorted(merged)]
save('capture-audit.json',audit)
event('INTERRUPTED_BATCH_RECOVERED',total=len(audit['jobs']))
