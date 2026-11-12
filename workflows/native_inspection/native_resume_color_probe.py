import ast,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_resume_fast as n
tree=ast.parse((Path(__file__).resolve().parent/'native_resume_evidence.py').read_text(encoding='utf8'))
helpers=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='helpers' for t in node.targets))
path=str(n.F/'debug-current-orange.jpg').replace('"','""')
code=r'''
Function Run()
Dim p,s,v,r,g,b,o,cr,co,visible,rootState,shapeState
doc.Activate
Set p=doc.Product.Products.Item(1)
Set s=ShapeOf(p)
Style s,0,255,161,56,255,1,1
CATIA.RefreshDisplay=True
CATIA.HSOSynchronized=True
Set v=CATIA.ActiveWindow.ActiveViewer
v.Update
sel.Clear
sel.Add s
cr=sel.VisProperties.GetVisibleColor(r,g,b)
co=sel.VisProperties.GetVisibleOpacity(o)
visible="[" & r & "," & g & "," & b & "," & o & "]"
sel.Clear
rootState=State(doc.Product)
shapeState=State(s)
Run="{" & Q("visible") & ":" & visible & "," & Q("root") & ":" & rootState & "," & Q("shape") & ":" & shapeState & "}"
End Function
'''.replace('PATH',path)
result=json.loads(n.evaluate(helpers+code));n.save('resume-color-probe.json',result);print(result,flush=True)
import time
time.sleep(.3)
n.app.ActiveWindow.ActiveViewer.CaptureToFile(5,path)
n.evaluate(helpers+'Function Run()\nStyle ShapeOf(doc.Product.Products.Item(1)),0,210,210,255,255,0,0\nCATIA.RefreshDisplay=True\nCATIA.HSOSynchronized=True\nRun="RESTORED"\nEnd Function')
