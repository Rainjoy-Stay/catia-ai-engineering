"""Resume native checks and capture using CATIA's own scripting runtime."""
import json,sys,time,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_resume_fast as n
from PIL import Image,ImageDraw
import numpy as np
F=n.F;ROOT=n.ROOT;app=n.app
ref=ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/project/tools/report_capture_reference_20260920/capture_generic_dual_view_20261010.py'
spec=importlib.util.spec_from_file_location('resume_camera',ref);g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
native=json.loads((F/'native-results.json').read_text(encoding='utf8'))
prep=json.loads((F/'preparation-audit.json').read_text(encoding='utf8'));reg={r['id']:r for r in prep['records']}
review=json.loads((F/'native-gsd-spa-single-part-review.json').read_text(encoding='utf8'));reviews={tuple(sorted(r['pair'])):r for r in review['rows']}
exact=json.loads((F/'resume-exact-solids.json').read_text(encoding='utf8'))
assert exact['complete'],'Finish the exact solid queue before capture'
exact_map={r['issue_id']:r for r in exact['rows']}
surfaces=json.loads((F/'resume-surface-evidence.json').read_text(encoding='utf8'))
assert surfaces['complete'],'Finish focused surface review before capture'
surface_map={r['issue_id']:r for r in surfaces['rows']}
issues=sorted([r for r in native['conflicts'] if r['type']=='CLASH' and r['interference_depth_mm']>=1],key=lambda r:-r['interference_depth_mm'])
queue=[];pending=[]
for i,c in enumerate(issues,1):
 ids=[c['first_part_number'],c['second_part_number']]
 if reg[ids[0]]['area_mm2']<reg[ids[1]]['area_mm2']:ids.reverse()
 item={'issue_id':f'DMU-{i:05d}','object_ids':ids,'native':c,'objects':[reg[k] for k in ids],'review':reviews[tuple(sorted(ids))]}
 surface=any(reg[k]['kind']=='SURFACE' for k in ids)
 item['geometry_fact']=(surface_map if surface else exact_map).get(item['issue_id'],{'status':'NEEDS_REVIEW'})
 status=item['geometry_fact']['status']
 (queue if status in ('CONFIRMED_SOLID_OVERLAP','CONFIRMED_CLOSED_SKIN_OVERLAP','TWO_SIDED_SURFACE_PENETRATION_EVIDENCE') else pending).append(item)
full_queue=list(queue)
if '--pilot' in sys.argv:
 queue=queue[:2]+[next(j for j in queue if any(o['kind']=='SURFACE' for o in j['objects']))]
else:
 limit=int(sys.argv[1]) if len(sys.argv)>1 else len(queue)
 queue=queue[:limit]
ledger=json.loads((F/'fast-display-before.json').read_text(encoding='utf8'));index={r['id']:r['index'] for r in ledger['items']}
assert set(index)==set(reg)
doc=app.Documents.Item(n.DOC);doc.Activate();viewer=app.ActiveWindow.ActiveViewer
render=viewer.RenderingMode
output=F/'evidence-resume-20261013';output.mkdir(exist_ok=True)
n.save('resume-scope.json',{'queue':full_queue,'capture_queue_count':len(queue),'pending_candidates':pending,'filter':'DMU CLASH depth >= 1 mm, exact positive solid common volume or focused surface penetration evidence','source_saved_by_tool':False})
helpers=r'''
Sub Style(o,sh,r,g,b,op,ci,oi)
 CATIA.RefreshDisplay=False
 CATIA.HSOSynchronized=False
 sel.Clear
 sel.Add o
 sel.VisProperties.SetShow sh
 sel.VisProperties.SetRealColor r,g,b,ci
 sel.VisProperties.SetRealOpacity op,oi
 sel.Clear
End Sub
Sub Show(o,sh)
 CATIA.RefreshDisplay=False
 CATIA.HSOSynchronized=False
 sel.Clear
 sel.Add o
 sel.VisProperties.SetShow sh
 sel.Clear
End Sub
Sub AllShow(sh)
 Dim k,o,valid
 CATIA.RefreshDisplay=False
 CATIA.HSOSynchronized=False
 sel.Clear
 On Error Resume Next
 sel.Search "CATAsmSearch.Product,all"
 valid=(Err.Number=0)
 Err.Clear
 On Error GoTo 0
 If valid Then
  For k=sel.Count2 To 1 Step -1
   Set o=sel.Item2(k).Value
   If o.PartNumber=doc.Product.PartNumber Then sel.Remove2 k
  Next
  valid=(sel.Count2=doc.Product.Products.Count)
 End If
 If Not valid Then
  sel.Clear
  For k=1 To doc.Product.Products.Count
   sel.Add doc.Product.Products.Item(k)
  Next
 End If
 sel.VisProperties.SetShow sh
 sel.Clear
End Sub
Sub Fit(v)
 CATIA.RefreshDisplay=True
 CATIA.HSOSynchronized=True
 v.Update
 v.Reframe
 v.Viewpoint3D.Zoom=v.Viewpoint3D.Zoom*0.65
 v.Update
End Sub
Sub Snap(v,path)
 CATIA.RefreshDisplay=True
 CATIA.HSOSynchronized=True
 sel.Clear
 v.Update
 v.CaptureToFile 5,path
 CATIA.RefreshDisplay=False
 CATIA.HSOSynchronized=False
End Sub
Function Cam(v)
 Dim o(2),s(2),u(2),p
 Set p=v.Viewpoint3D
 p.GetOrigin o
 p.GetSightDirection s
 p.GetUpDirection u
 Cam="{" & Q("origin") & ":[" & Join(o,",") & "]," & Q("sight") & ":[" & Join(s,",") & "]," & Q("up") & ":[" & Join(u,",") & "]," & Q("zoom") & ":" & p.Zoom & "," & Q("focus_distance") & ":" & p.FocusDistance & "," & Q("projection_mode") & ":" & p.ProjectionMode & "}"
End Function
'''
def run(code):return n.evaluate(helpers+code)
def q(s):return '"'+str(s).replace('"','""')+'"'
def capture_external(path):
 app.RefreshDisplay=True;app.HSOSynchronized=True
 viewer.Update();time.sleep(.15);viewer.CaptureToFile(5,str(path))
def phase(ia,ib,ids,operations):
 code=f'''Function Run()
Dim pa,pb,a,b,v
Set pa=doc.Product.Products.Item({ia})
Set pb=doc.Product.Products.Item({ib})
If pa.PartNumber<>{q(ids[0])} Or pb.PartNumber<>{q(ids[1])} Then Err.Raise 514
Set a=ShapeOf(pa)
Set b=ShapeOf(pb)
Set v=CATIA.ActiveWindow.ActiveViewer
{operations}
Run=Cam(v)
End Function'''
 return json.loads(run(code))
camera=json.loads(run('Function Run()\nRun=Cam(CATIA.ActiveWindow.ActiveViewer)\nEnd Function'))
n.save('resume-camera-before.json',{'camera':camera,'rendering_mode':render,'document':doc.Name,'saved':bool(doc.Saved)})
def restore():
 from collections import defaultdict
 buckets=defaultdict(list)
 for row in ledger['items']:
  for role,state in [('component',row['component']),('shape',row['shape'])]:
   key=(role,state['show'],tuple(state['color']),state['opacity'],state['color_inheritance'],state['opacity_inheritance'])
   buckets[key].append(row['index'])
 lines=['Function Run()','Dim p,pt,s,k','doc.Activate']
 for row in ledger['items']:
  lines+= [f'Set p=doc.Product.Products.Item({row["index"]})',f'If p.PartNumber<>{q(row["id"])} Then Err.Raise 513']
 for key,indices in buckets.items():
  role,show,color,opacity,ci,oi=key
  lines.append('sel.Clear')
  for i in indices:
   lines.append(f'Set p=doc.Product.Products.Item({i})')
   lines.append('sel.Add p' if role=='component' else 'sel.Add ShapeOf(p)')
  lines += [f'sel.VisProperties.SetShow {show}',f'sel.VisProperties.SetRealColor {",".join(map(str,color))},{ci}',f'sel.VisProperties.SetRealOpacity {opacity},{oi}','sel.Clear']
 for show in (0,1):
  lines.append('sel.Clear')
  for row in ledger['items']:
   lines += [f'Set p=doc.Product.Products.Item({row["index"]})','Set pt=p.ReferenceProduct.Parent.Part']
   for k,state in enumerate(row['bodies'],1):
    if state['show']==show:lines.append(f'sel.Add pt.Bodies.Item({k})')
   for attr,state in zip(['PlaneXY','PlaneYZ','PlaneZX'],row['aux']):
    if state['show']==show:lines.append(f'sel.Add pt.OriginElements.{attr}')
  lines += [f'If sel.Count2>0 Then sel.VisProperties.SetShow {show}','sel.Clear']
 lines+=['CATIA.RefreshDisplay=True','CATIA.HSOSynchronized=True','Run="RESTORED"','End Function']
 run('\n'.join(lines));g.restore_camera(viewer.Viewpoint3D,camera);viewer.RenderingMode=render;viewer.Update()
 after=n.snapshot();n.save('fast-display-after.json',after)
 app.RefreshDisplay=True;app.HSOSynchronized=True;viewer.Update()
 camera_after=json.loads(run('Function Run()\nRun=Cam(CATIA.ActiveWindow.ActiveViewer)\nEnd Function'))
 n.save('resume-camera-after.json',camera_after)
 import math
 camera_ok=all(math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-6) for key in ('origin','sight','up') for a,b in zip(camera[key],camera_after[key])) and math.isclose(camera['zoom'],camera_after['zoom'],rel_tol=1e-6,abs_tol=1e-9)
 return {'verified':after['items']==ledger['items'] and camera_ok,'display_verified':after['items']==ledger['items'],'camera_verified':camera_ok,'saved_before':ledger['saved'],'saved_after':after['saved'],'source_saved_by_tool':False}
audit={'jobs':[],'restoration':None,'started':time.time()}
accepted={}
if '--pilot' not in sys.argv and (F/'resume-pilot-accepted.json').exists():
 acceptance=json.loads((F/'resume-pilot-accepted.json').read_text(encoding='utf8'))
 previous=json.loads((F/'resume-capture-audit.json').read_text(encoding='utf8'))
 if previous.get('restoration',{}).get('verified'):
  accepted={j['issue_id']:j for j in previous['jobs'] if j['issue_id'] in acceptance['issue_ids']}
try:
 init=r'''
Function Run()
 Dim i,p,pt,s,k,origin
 doc.Activate
 CATIA.RefreshDisplay=False
 CATIA.HSOSynchronized=False
 AllShow 0
 sel.Clear
 For i=1 To doc.Product.Products.Count
  Set p=doc.Product.Products.Item(i)
  Set s=ShapeOf(p)
  sel.Add s
 Next
 sel.VisProperties.SetShow 0
 sel.VisProperties.SetRealColor 185,190,198,1
 sel.VisProperties.SetRealOpacity 52,1
 sel.Clear
 For i=1 To doc.Product.Products.Count
  Set p=doc.Product.Products.Item(i)
  Set pt=p.ReferenceProduct.Parent.Part
  For k=1 To pt.Bodies.Count
   sel.Add pt.Bodies.Item(k)
  Next
 Next
 sel.VisProperties.SetShow 0
 sel.Clear
 For i=1 To doc.Product.Products.Count
  Set pt=doc.Product.Products.Item(i).ReferenceProduct.Parent.Part
  Set origin=pt.OriginElements
  sel.Add origin.PlaneXY
  sel.Add origin.PlaneYZ
  sel.Add origin.PlaneZX
 Next
 sel.VisProperties.SetShow 1
 sel.Clear
 CATIA.RefreshDisplay=True
 CATIA.HSOSynchronized=True
 Run="READY"
End Function
'''
 print(run(init),flush=True);g.set_view(viewer,'isometric');viewer.RenderingMode=0
 for item in queue:
  cached=accepted.get(item['issue_id'])
  if cached and cached['native']==item['native'] and cached['geometry_fact']==item['geometry_fact']:
   audit['jobs'].append(cached);n.save('resume-capture-audit.json',audit);print(json.dumps({'stage':'REUSE_VERIFIED_PILOT','id':item['issue_id']}),flush=True);continue
  folder=output/item['issue_id'];folder.mkdir(exist_ok=True)
  ia,ib=[index[s] for s in item['object_ids']]
  ids=item['object_ids']
  item['context_camera']=phase(ia,ib,ids,'AllShow 0\nStyle a,0,255,161,56,255,1,1\nStyle b,0,31,214,224,255,1,1\nFit v')
  capture_external(folder/'context-raw.jpg')
  phase(ia,ib,ids,'AllShow 1\nShow pb,0\nStyle b,0,255,161,56,255,1,1')
  capture_external(folder/'context-locator.jpg')
  phase(ia,ib,ids,'Show pb,1\nShow pa,0\nStyle a,0,255,161,56,255,1,1')
  capture_external(folder/'context-locator-a.jpg')
  item['detail_camera']=phase(ia,ib,ids,'Show pa,0\nShow pb,0\nStyle a,0,255,161,56,255,1,1\nStyle b,0,31,214,224,255,1,1\nFit v')
  capture_external(folder/'detail-raw.jpg')
  phase(ia,ib,ids,'Show pa,1\nStyle b,0,255,161,56,255,1,1')
  capture_external(folder/'detail-locator.jpg')
  item['folder']=str(folder);item['detail_opacity_a']=255
  arr=np.asarray(Image.open(folder/'detail-raw.jpg').convert('RGB')).astype(int)
  hh,ww=arr.shape[:2];arr=arr[int(hh*.15):int(hh*.9),int(ww*.2):int(ww*.88)]
  cyan=(arr[:,:,1]-arr[:,:,0]>50)&(arr[:,:,2]-arr[:,:,0]>50)&(arr[:,:,1]>90)
  item['opaque_cyan_pixels']=int(cyan.sum())
  loc=np.asarray(Image.open(folder/'detail-locator.jpg').convert('RGB')).astype(int)
  loc=loc[int(hh*.15):int(hh*.9),int(ww*.2):int(ww*.88)]
  orange=(loc[:,:,0]-loc[:,:,2]>35)&(loc[:,:,0]>75)&(loc[:,:,1]>30)&(loc[:,:,1]<230)
  item['isolated_b_pixels']=int(orange.sum())
  item['opaque_b_visible_fraction']=item['opaque_cyan_pixels']/max(1,item['isolated_b_pixels'])
  if item['opaque_cyan_pixels']<30 or item['opaque_b_visible_fraction']<.5:
   phase(ia,ib,ids,'Show pa,0\nShow pb,0\nStyle a,0,255,161,56,127,1,1\nStyle b,0,31,214,224,255,1,1')
   capture_external(folder/'detail-raw.jpg');item['detail_opacity_a']=127;item['opacity_reason']='OPAQUE_A_OCCLUDES_B'
  phase(ia,ib,ids,'Style a,0,185,190,198,52,1,1\nStyle b,0,185,190,198,52,1,1\nShow pa,1\nShow pb,1')
  audit['jobs'].append(item);n.save('resume-capture-audit.json',audit)
  print(json.dumps({'stage':'CAPTURE','done':len(audit['jobs']),'total':len(queue),'id':item['issue_id']}),flush=True)
finally:
 audit['restoration']=restore();n.save('resume-capture-audit.json',audit)
 print(json.dumps({'stage':'RESTORED',**audit['restoration']}),flush=True)
