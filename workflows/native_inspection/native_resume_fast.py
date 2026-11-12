"""Structured CATIA in-process display inventory and reversible evidence capture."""
import json,sys,time,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
F=ROOT/'output/全量原生DMU检查_20261012'
sys.path.insert(0,str(ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
from catia_mcp.connection import CATIAConnection
c=CATIAConnection();c.connect();app=c.app
DOC='NativeDMU_Full_20261012.CATProduct'
base=r'''
Dim doc, sel
Set doc=CATIA.Documents.Item("NativeDMU_Full_20261012.CATProduct")
Set sel=doc.Selection
Function Q(s)
 Q=Chr(34) & Replace(Replace(CStr(s),"\", "\\"),Chr(34),"\" & Chr(34)) & Chr(34)
End Function
Function State(o)
 Dim p,r,g,b,ci,oi,op,sh,cs,os
 sel.Clear
 sel.Add o
 Set p=sel.VisProperties
 cs=p.GetRealColor(r,g,b)
 os=p.GetRealOpacity(op)
 p.GetRealInheritance 2,ci
 p.GetRealInheritance 3,oi
 p.GetShow sh
 State="{" & Q("show") & ":" & sh & "," & Q("color") & ":[" & r & "," & g & "," & b & "]," & Q("color_inheritance") & ":" & ci & "," & Q("opacity") & ":" & op & "," & Q("opacity_inheritance") & ":" & oi & "," & Q("color_status") & ":" & cs & "," & Q("opacity_status") & ":" & os & "}"
 sel.Clear
End Function
Function ShapeOf(p)
 Dim pt,k,b
 Set pt=p.ReferenceProduct.Parent.Part
 For k=1 To pt.Bodies.Count
  Set b=pt.Bodies.Item(k)
  If b.Shapes.Count>0 Then
   Set ShapeOf=b.Shapes.Item(b.Shapes.Count)
   Exit Function
  End If
 Next
 Set ShapeOf=pt.HybridBodies.Item(1).HybridShapes.Item(1)
End Function
'''
def evaluate(code):return app.SystemService.Evaluate(base+code,1,'Run',())
def save(name,obj):
 (F/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
snapshot_code='''
Function Run()
 Dim i,p,pt,k,b,s,rows,entry,bs,aux,origin,x(11)
 CATIA.RefreshDisplay=False
 CATIA.HSOSynchronized=False
 rows=""
 For i=1 To doc.Product.Products.Count
  Set p=doc.Product.Products.Item(i)
  Set pt=p.ReferenceProduct.Parent.Part
  Set s=ShapeOf(p)
  p.Position.GetComponents x
  bs=""
  For k=1 To pt.Bodies.Count
   Set b=pt.Bodies.Item(k)
   If k>1 Then bs=bs & ","
   bs=bs & State(b)
  Next
  Set origin=pt.OriginElements
  aux="[" & State(origin.PlaneXY) & "," & State(origin.PlaneYZ) & "," & State(origin.PlaneZX) & "]"
  entry="{" & Q("index") & ":" & i & "," & Q("id") & ":" & Q(p.PartNumber) & "," & Q("source_file") & ":" & Q(p.ReferenceProduct.Parent.FullName) & "," & Q("shape_name") & ":" & Q(s.Name) & "," & Q("shape_type") & ":" & Q(TypeName(s)) & "," & Q("position") & ":[" & Join(x,",") & "]," & Q("component") & ":" & State(p) & "," & Q("bodies") & ":[" & bs & "]," & Q("shape") & ":" & State(s) & "," & Q("aux") & ":" & aux & "}"
  If i>1 Then rows=rows & ","
  rows=rows & entry
 Next
 sel.Clear
 Run="{" & Q("document") & ":" & Q(doc.Name) & "," & Q("path") & ":" & Q(doc.FullName) & "," & Q("saved") & ":" & LCase(CStr(doc.Saved)) & "," & Q("items") & ":[" & rows & "]}"
End Function
'''
def snapshot():return json.loads(evaluate(snapshot_code))

if __name__=='__main__':
 started=time.time();data=snapshot();save('fast-display-before.json',data)
 print(json.dumps({'stage':'FAST_SNAPSHOT','count':len(data['items']),'seconds':time.time()-started}),flush=True)
