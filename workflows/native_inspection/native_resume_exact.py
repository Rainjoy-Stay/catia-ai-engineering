"""Exact CATIA solid intersections on owned disposable geometry copies."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_resume_fast as n
F=n.F
native=json.loads((F/'native-results.json').read_text(encoding='utf8'))
prep=json.loads((F/'preparation-audit.json').read_text(encoding='utf8'));reg={r['id']:r for r in prep['records']}
ledger=json.loads((F/'fast-display-before.json').read_text(encoding='utf8'));index={r['id']:r['index'] for r in ledger['items']}
issues=sorted([r for r in native['conflicts'] if r['type']=='CLASH' and r['interference_depth_mm']>=1],key=lambda r:-r['interference_depth_mm'])
queue=[(i+1,c) for i,c in enumerate(issues) if all(reg[k]['kind']=='SOLID' for k in [c['first_part_number'],c['second_part_number']])]
scope_count=len(queue)
if len(sys.argv)>1:queue=queue[:int(sys.argv[1])]
helpers=r'''
Function CopyBody(p,t)
 Dim sd,pt,k,b,ss,ds,before
 CATIA.RefreshDisplay=False
 CATIA.HSOSynchronized=True
 Set sd=CATIA.Documents.Open(p.ReferenceProduct.Parent.FullName)
 Set pt=sd.Part
 For k=1 To pt.Bodies.Count
  Set b=pt.Bodies.Item(k)
  If b.Shapes.Count>0 Then Exit For
 Next
 sd.Activate
 If CATIA.ActiveDocument.Name<>sd.Name Then Err.Raise 519,"CopyBody","Source document did not activate"
 Set ss=sd.Selection
 ss.Clear
 ss.Add b
 ss.Copy
 ss.Clear
 t.Activate
 Set ds=t.Selection
 before=t.Part.Bodies.Count
 ds.Clear
 ds.Add t.Part.MainBody
 ds.PasteSpecial "CATPrtResultWithOutLink"
 ds.Clear
 If t.Part.Bodies.Count<>before+1 Then Err.Raise 517
 Set CopyBody=t.Part.Bodies.Item(t.Part.Bodies.Count)
End Function
Function CheckPair(ia,ib,issue)
 Dim pa,pb,t,tp,a,b,feature,spa,m,vol,eno,desc,row,x(11),k,identity,stage
 Set pa=doc.Product.Products.Item(ia)
 Set pb=doc.Product.Products.Item(ib)
 identity=True
 For Each p In Array(pa,pb)
  p.Position.GetComponents x
  For k=0 To 11
   If k=0 Or k=4 Or k=8 Then
    If Abs(x(k)-1)>0.000001 Then identity=False
   Else
    If Abs(x(k))>0.000001 Then identity=False
   End If
  Next
 Next
 If Not identity Then Err.Raise 518,"CheckPair","Nonidentity assembly placement requires a transformed copy"
 Set t=CATIA.Documents.Add("Part")
 Set tp=t.Part
 On Error Resume Next
 stage="COPY_A"
 Set a=CopyBody(pa,t)
 If Err.Number=0 Then
  stage="COPY_B"
  Set b=CopyBody(pb,t)
 End If
 If Err.Number=0 Then
  stage="SET_IN_WORK_BODY"
  tp.InWorkObject=a
 End If
 If Err.Number=0 Then
  stage="CREATE_BOOLEAN"
  Set feature=tp.ShapeFactory.AddNewIntersect(b)
 End If
 If Err.Number=0 Then
  stage="UPDATE_BOOLEAN"
  tp.UpdateObject feature
 End If
 eno=Err.Number
 desc=Err.Description
 Err.Clear
 vol=0
 If eno=0 Then
  stage="MEASURE_COMMON_BODY"
  Set spa=t.GetWorkbench("SPAWorkbench")
  Set m=spa.GetMeasurable(tp.CreateReferenceFromObject(a))
  vol=m.Volume*1000000000
  eno=Err.Number
  desc=Err.Description
  Err.Clear
 End If
 t.Close
 On Error GoTo 0
 doc.Activate
 row="{" & Q("issue_id") & ":" & Q(issue) & "," & Q("pair") & ":[" & Q(pa.PartNumber) & "," & Q(pb.PartNumber) & "]," & Q("volume_mm3") & ":" & vol & "," & Q("stage") & ":" & Q(stage) & "," & Q("error_number") & ":" & eno & "," & Q("error") & ":" & Q(desc) & "}"
 CheckPair=row
End Function
'''
rows=[];started=time.time()
try:
 for number,c in queue:
  a,b=[index[k] for k in [c['first_part_number'],c['second_part_number']]]
  code=f'Function Run()\nRun=CheckPair({a},{b},"DMU-{number:05d}")\nEnd Function'
  row=json.loads(n.evaluate(helpers+code));row['status']='CONFIRMED_SOLID_OVERLAP' if row['error_number']==0 and row['volume_mm3']>1e-6 else 'NEEDS_REVIEW' if row['error_number'] else 'ZERO_COMMON_VOLUME'
  if row['error_number']==0:
   bound=min(reg[k]['volume_mm3'] for k in row['pair'])
   if row['volume_mm3']>bound+max(1e-6,bound*1e-7):raise RuntimeError('Common volume exceeds input volume; units or geometry must be reviewed')
  rows.append(row);n.save('resume-exact-solids.json',{'rows':rows,'tolerance_mm3':1e-6,'scope_count':scope_count,'complete':len(rows)==scope_count,'method':'CATIA_NATIVE_PARTDESIGN_INTERSECT_SPA_VOLUME_ON_DISPOSABLE_COPIES','source_saved_by_tool':False})
  print(json.dumps({'done':len(rows),'total':len(queue),**row},ensure_ascii=False),flush=True)
finally:
 n.app.Documents.Item(n.DOC).Activate();n.app.RefreshDisplay=True;n.app.HSOSynchronized=True
 print(json.dumps({'stage':'EXACT_REVIEW_STOPPED','seconds':time.time()-started}),flush=True)
