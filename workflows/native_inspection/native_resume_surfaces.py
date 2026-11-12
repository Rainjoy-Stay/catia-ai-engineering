"""GSD intersections and two-sided temporary-neighbourhood surface review."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_resume_fast as n
F=n.F
prep=json.loads((F/'preparation-audit.json').read_text(encoding='utf8'));reg={r['id']:r for r in prep['records']}
native=json.loads((F/'native-results.json').read_text(encoding='utf8'))
old=json.loads((F/'native-gsd-spa-single-part-review.json').read_text(encoding='utf8'));rv={tuple(sorted(r['pair'])):r for r in old['rows']}
index={r['id']:r['index'] for r in json.loads((F/'fast-display-before.json').read_text(encoding='utf8'))['items']}
issues=sorted([r for r in native['conflicts'] if r['type']=='CLASH' and r['interference_depth_mm']>=1],key=lambda r:-r['interference_depth_mm'])
queue=[(i+1,c) for i,c in enumerate(issues) if any(reg[k]['kind']=='SURFACE' for k in [c['first_part_number'],c['second_part_number']]) and rv[tuple(sorted([c['first_part_number'],c['second_part_number']]))]['gsd']['status']=='COMPLETE']
helpers=r'''
Function Probe(ia,ib,reverse,closed,thickness)
 Dim pa,pb,sd,sp,s,b,k,t,tp,ss,ds,group,a,skin,ref,tool,feature,ix,spa,m,vol,eno,desc,stage,len,area,before
 CATIA.RefreshDisplay=False
 CATIA.HSOSynchronized=True
 Set pa=doc.Product.Products.Item(ia)
 Set pb=doc.Product.Products.Item(ib)
 Set t=CATIA.Documents.Add("Part")
 Set tp=t.Part
 On Error Resume Next
 stage="COPY_SOLID"
 Set sd=CATIA.Documents.Open(pa.ReferenceProduct.Parent.FullName)
 Set sp=sd.Part
 For k=1 To sp.Bodies.Count
  Set b=sp.Bodies.Item(k)
  If b.Shapes.Count>0 Then Exit For
 Next
 sd.Activate
 Set ss=sd.Selection
 ss.Clear
 ss.Add b
 ss.Copy
 ss.Clear
 t.Activate
 Set ds=t.Selection
 ds.Clear
 ds.Add tp.MainBody
 ds.PasteSpecial "CATPrtResultWithOutLink"
 ds.Clear
 Set a=tp.Bodies.Item(tp.Bodies.Count)
 If Err.Number=0 Then
  stage="COPY_SURFACE"
  Set sd=CATIA.Documents.Open(pb.ReferenceProduct.Parent.FullName)
  Set sp=sd.Part
  Set s=sp.HybridBodies.Item(1).HybridShapes.Item(1)
  sd.Activate
  Set ss=sd.Selection
  ss.Clear
  ss.Add s
  ss.Copy
  ss.Clear
  t.Activate
  Set group=tp.HybridBodies.Add()
  group.Name="ProbeInputs"
  ds.Clear
  ds.Add group
  ds.PasteSpecial "CATPrtResultWithOutLink"
  ds.Clear
  Set skin=group.HybridShapes.Item(1)
  Set ref=tp.CreateReferenceFromObject(skin)
 End If
 len=0
 area=0
 If Err.Number=0 Then
  stage="VERIFY_AREA_AND_GSD_INTERSECTION"
  Set spa=t.GetWorkbench("SPAWorkbench")
  area=spa.GetMeasurable(ref).Area*1000000
  Set ix=tp.HybridShapeFactory.AddNewIntersection(tp.CreateReferenceFromObject(a.Shapes.Item(a.Shapes.Count)),ref)
  group.AppendHybridShape ix
  tp.UpdateObject ix
  len=spa.GetMeasurable(tp.CreateReferenceFromObject(ix)).Length
 End If
 If Err.Number=0 Then
  stage="CREATE_TEMPORARY_SURFACE_NEIGHBOURHOOD"
  Set tool=tp.Bodies.Add()
  tp.InWorkObject=tool
  If closed Then
   Set feature=tp.ShapeFactory.AddNewCloseSurface(ref)
  Else
   If reverse Then
    Set feature=tp.ShapeFactory.AddNewThickSurface(ref,False,0,thickness)
   Else
    Set feature=tp.ShapeFactory.AddNewThickSurface(ref,False,thickness,0)
   End If
  End If
  tp.UpdateObject feature
 End If
 If Err.Number=0 Then
  stage="INTERSECT_TEMPORARY_NEIGHBOURHOOD"
  tp.InWorkObject=a
  Set feature=tp.ShapeFactory.AddNewIntersect(tool)
  tp.UpdateObject feature
 End If
 vol=0
 If Err.Number=0 Then
  stage="MEASURE_PROBE_COMMON_VOLUME"
  vol=spa.GetMeasurable(tp.CreateReferenceFromObject(a)).Volume*1000000000
 End If
 eno=Err.Number
 desc=Err.Description
 Err.Clear
 t.Close
 On Error GoTo 0
 doc.Activate
 Probe="{" & Q("volume_mm3") & ":" & vol & "," & Q("copied_surface_area_mm2") & ":" & area & "," & Q("intersection_length_mm") & ":" & len & "," & Q("stage") & ":" & Q(stage) & "," & Q("error_number") & ":" & eno & "," & Q("error") & ":" & Q(desc) & "}"
End Function
'''
rows=[]
try:
 for number,c in queue:
  ids=[c['first_part_number'],c['second_part_number']]
  solid=next(k for k in ids if reg[k]['kind']=='SOLID');surface=next(k for k in ids if reg[k]['kind']=='SURFACE')
  closed=reg[surface]['name'].startswith('CLOSED_SHELL')
  row={'issue_id':f'DMU-{number:05d}','pair':ids,'source_surface_name':reg[surface]['name'],'trials':[],'status':'NEEDS_REVIEW'}
  trials=[(False,0)] if closed else [(False,.02),(True,.02),(False,.01),(True,.01)]
  for reverse,epsilon in trials:
   code=f'Function Run()\nRun=Probe({index[solid]},{index[surface]},{str(reverse)},{str(closed)},{epsilon})\nEnd Function'
   result=json.loads(n.evaluate(helpers+code));result.update(side='BOTTOM' if reverse else 'TOP',epsilon_mm=epsilon,closed_surface=closed)
   row['trials'].append(result)
   if result['error_number']:break
   if abs(result['copied_surface_area_mm2']-reg[surface]['area_mm2'])>max(1e-5,reg[surface]['area_mm2']*1e-8):raise RuntimeError('Copied surface area differs from registry')
  if closed and row['trials'][0]['error_number']:
   row['closure_attempt']=row['trials'][0];row['trials']=[];closed=False
   trials=[(False,.02),(True,.02),(False,.01),(True,.01)]
   for reverse,epsilon in trials:
    code=f'Function Run()\nRun=Probe({index[solid]},{index[surface]},{str(reverse)},False,{epsilon})\nEnd Function'
    result=json.loads(n.evaluate(helpers+code));result.update(side='BOTTOM' if reverse else 'TOP',epsilon_mm=epsilon,closed_surface=False)
    row['trials'].append(result)
    if result['error_number']:break
    if abs(result['copied_surface_area_mm2']-reg[surface]['area_mm2'])>max(1e-5,reg[surface]['area_mm2']*1e-8):raise RuntimeError('Copied surface area differs from registry')
  if all(r['error_number']==0 for r in row['trials']) and len(row['trials'])==len(trials):
   if all(r['volume_mm3']>1e-6 for r in row['trials']):
    if closed:row['status']='CONFIRMED_CLOSED_SKIN_OVERLAP'
    else:
     ratios=[row['trials'][k+2]['volume_mm3']/row['trials'][k]['volume_mm3'] for k in (0,1)]
     row['half_thickness_volume_ratios']=ratios
     if all(.35<r<.65 for r in ratios):row['status']='TWO_SIDED_SURFACE_PENETRATION_EVIDENCE'
  rows.append(row);n.save('resume-surface-evidence.json',{'rows':rows,'complete':len(rows)==len(queue),'method':'CATIA_GSD_INTERSECTION_AND_TWO_SIDED_TEMPORARY_NEIGHBOURHOOD','side_definition':'Separate positive top offset with zero bottom, and positive bottom offset with zero top; orientation held fixed','probe_volumes_are_not_source_material_volumes':True,'source_saved_by_tool':False})
  print(json.dumps(row,ensure_ascii=False),flush=True)
finally:
 n.app.Documents.Item(n.DOC).Activate();n.app.RefreshDisplay=True;n.app.HSOSynchronized=True
