import json,importlib.util,hashlib,time,os
from pathlib import Path
import win32com.client
W=Path.cwd();P=W/'CATIA管路智能检查系统_内网移植包_4.8.0_R30_详细执行与通用截图版_20260929'/'CATIA管路智能检查系统_内网移植包_4.8.0_R30_详细执行与通用截图版_20260929'
s=importlib.util.spec_from_file_location('capture',P/'project/tools/capture_generic_dual_view.py');m=importlib.util.module_from_spec(s)
import sys
sys.modules['capture']=m;s.loader.exec_module(m)
app=win32com.client.GetActiveObject('CATIA.Application');doc=app.ActiveDocument
assert str(doc.Name).endswith('.CATPart')
kind,items=m.inventory_active_document(doc);assert len(items)==1412
out=W/'output/新拍CATIA报告证据_20261008';out.mkdir(exist_ok=True)
viewer=app.ActiveWindow.ActiveViewer;vp=viewer.Viewpoint3D;camera=m.snapshot_camera(app,vp);render_mode=viewer.RenderingMode
vba='''
Public Function Snap(app)
 Dim d,s,b,o,i,r,g,bl,op,sh,ci,oi,buf
 Set d=app.ActiveDocument:Set s=d.Selection
 For i=1 To d.Part.Bodies.Count
  Set b=d.Part.Bodies.Item(i):Set o=b
  If b.Shapes.Count>0 Then Set o=b.Shapes.Item(1)
  s.Clear:s.Add b:s.VisProperties.GetShow sh
  s.Clear:s.Add o
  s.VisProperties.GetRealColor r,g,bl
  s.VisProperties.GetRealOpacity op
  s.VisProperties.GetRealInheritance 0,ci
  s.VisProperties.GetRealInheritance 1,oi
  buf=buf & i & "," & sh & "," & r & "," & g & "," & bl & "," & op & "," & ci & "," & oi & vbLf
 Next
 s.Clear:Snap=buf
End Function
Public Function Paint(app,a,b,mode)
 Dim d,s,x,o,i
 Set d=app.ActiveDocument:Set s=d.Selection
 s.Clear
 For i=1 To d.Part.Bodies.Count
  Set x=d.Part.Bodies.Item(i):s.Add x
 Next
 If mode=0 Then
  s.VisProperties.SetShow 0
  s.Clear
  For i=1 To d.Part.Bodies.Count
   Set x=d.Part.Bodies.Item(i):Set o=x
   If x.Shapes.Count>0 Then Set o=x.Shapes.Item(1)
   s.Add o
  Next
  s.VisProperties.SetRealColor 175,180,190,0
  s.VisProperties.SetRealOpacity 42,0
 Else
  s.VisProperties.SetShow 1
 End If
 s.Clear
 For i=1 To d.Part.HybridBodies.Count
  s.Add d.Part.HybridBodies.Item(i)
 Next
 If s.Count>0 Then s.VisProperties.SetShow 1
 s.Clear:Set x=d.Part.Bodies.Item(a):s.Add x:s.VisProperties.SetShow 0:s.Clear
 Set o=x:If x.Shapes.Count>0 Then Set o=x.Shapes.Item(1)
 s.Add o:s.VisProperties.SetRealColor 255,161,56,0:s.VisProperties.SetRealOpacity 255,0:s.Clear
 Set x=d.Part.Bodies.Item(b):s.Add x:s.VisProperties.SetShow 0:s.Clear
 Set o=x:If x.Shapes.Count>0 Then Set o=x.Shapes.Item(1)
 s.Add o:s.VisProperties.SetRealColor 31,214,224,0:s.VisProperties.SetRealOpacity 255,0:s.Clear
 Paint=True
End Function
Public Function Restore(app,data)
 Dim d,s,lines,line,v,b,o,i
 Set d=app.ActiveDocument:Set s=d.Selection:lines=Split(data,vbLf)
 For Each line In lines
  If Len(line)>0 Then
   v=Split(line,","):Set b=d.Part.Bodies.Item(CInt(v(0))):Set o=b
   If b.Shapes.Count>0 Then Set o=b.Shapes.Item(1)
   s.Clear:s.Add b:s.VisProperties.SetShow CInt(v(1))
   s.Clear:s.Add o:s.VisProperties.SetRealColor CInt(v(2)),CInt(v(3)),CInt(v(4)),CInt(v(6))
   s.VisProperties.SetRealOpacity CInt(v(5)),CInt(v(7))
  End If
 Next
 s.Clear:Restore=True
End Function
'''
evaluate=lambda fn,args:app.SystemService.Evaluate(vba,0,fn,args)
app.RefreshDisplay=False
app.HSOSynchronized=False
print('snapshot start',flush=True)
states=(out/'body-display-before.txt').read_text(encoding='utf8') if os.environ.get('RECAPTURE_REPORT')=='1' else evaluate('Snap',[app])
print('snapshot complete',flush=True)
(out/'body-display-before.txt').write_text(states,encoding='utf8')
hybrid=[m._read_show(doc.Selection,doc.Part.HybridBodies.Item(i)) for i in range(1,int(doc.Part.HybridBodies.Count)+1)]
cases=json.loads((W/'output/人工标注学习_20261008/第01轮_待标注.json').read_text(encoding='utf8'))['cases']
jobs=[]
for c in cases:
 objs=[m.resolve_selector(x['name'],items) for x in c['ui']['objects']]
 bounds=c['ui']['local_bounds_mm'];center=[(a+b)/2 for a,b in zip(bounds['min'],bounds['max'])];span=max(b-a for a,b in zip(bounds['min'],bounds['max']))
 jobs.append((c['case_id'],objs,center,span))
jobs.append(('OVERLAP',[m.resolve_selector('BREP_WITH_VOIDS #3066',items),m.resolve_selector('MANIFOLD_SOLID_BREP #38581',items)],[-39.83925039555,92.776780998,4.60027385367],12))
only=os.environ.get('ONLY_CASE')
if only:jobs=[j for j in jobs if j[0]==only]
audit={'document':str(doc.Name),'source_step_sha256':hashlib.sha256(Path('F:/涡轮发动机_爱给网_aigei_com/涡轮发动机.stp').read_bytes()).hexdigest(),'camera_before':camera,'jobs':[],'saved_by_script':False}
if only:
 prior=json.loads((out/'capture-audit.json').read_text(encoding='utf8'));audit['jobs']=[j for j in prior['jobs'] if j['id']!=only]
def focus(center,span,view):
 m.set_view(viewer,view)
 sight=m.VIEWS[view][0];distance=max(span*5,20)
 vp.ProjectionMode=0
 vp.FocusDistance=distance
 vp.PutOrigin([center[i]-sight[i]*distance for i in range(3)])
 viewer.Update()
try:
 for ident,objs,center,span in jobs:
  folder=out/ident;folder.mkdir(exist_ok=True)
  rec={'id':ident,'objects':[{'index':o.index,'name':o.name,'path':f'{doc.Name}/Part/Bodies[{o.index}]/{o.name}'} for o in objs],'images':[],'focus_mm':center,'focus_basis':'recorded interface bounding box or internal witness, not measured clash boundary'}
  evaluate('Paint',[app,objs[0].index,objs[1].index,0]);viewer.RenderingMode=0;focus(center,min(max(span*8,40),80),'isometric')
  path=folder/'context.jpg';m.capture(viewer,path,1);rec['images'].append(str(path))
  evaluate('Paint',[app,objs[0].index,objs[1].index,1])
  viewer.RenderingMode=1
  for view in (['front','isometric','top','bottom'] if ident=='L03' else ['front','isometric']):
   focus(center,span,view);path=folder/(view+'-local.jpg');m.capture(viewer,path,1);rec['images'].append(str(path))
  audit['jobs'].append(rec);print(ident+' captured',flush=True)
finally:
 evaluate('Restore',[app,states])
 for i,sh in enumerate(hybrid,1):
  sel=doc.Selection;sel.Clear();sel.Add(doc.Part.HybridBodies.Item(i));sel.VisProperties.SetShow(sh);sel.Clear()
 m.restore_camera(vp,camera);viewer.RenderingMode=render_mode;viewer.Update()
 after=evaluate('Snap',[app]);audit['display_restored_exactly']=after==states
 audit['camera_after']=m.snapshot_camera(app,vp)
 (out/'capture-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
 app.RefreshDisplay=True
 app.HSOSynchronized=True
 print('restored '+str(after==states),flush=True)
