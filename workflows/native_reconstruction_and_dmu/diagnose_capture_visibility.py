import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];F=ROOT/'output/全量原生DMU检查_20261012'
sys.path.insert(0,str(ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
from catia_mcp.connection import CATIAConnection
c=CATIAConnection();c.connect();app=c.app;doc=app.Documents.Item('NativeDMU_Full_20261012.CATProduct');doc.Activate();sel=doc.Selection
audit=json.loads((F/'capture-audit.json').read_text(encoding='utf8'));selected=[audit['jobs'][i] for i in (0,19,100)]
ids={sid for j in selected for sid in j['object_ids']};registry={r['id']:r for r in json.loads((F/'preparation-audit.json').read_text(encoding='utf8'))['records']};rows=[]
def props(obj):
 sel.Clear();sel.Add(obj);p=sel.VisProperties;v={'show':p.GetShow(),'color':p.GetRealColor(),'visible_color':p.GetVisibleColor(),'color_inheritance':p.GetRealInheritance(2),'opacity':p.GetRealOpacity(),'visible_opacity':p.GetVisibleOpacity(),'opacity_inheritance':p.GetRealInheritance(3)};sel.Clear();return v
for i in range(1,doc.Product.Products.Count+1):
 product=doc.Product.Products.Item(i);sid=product.PartNumber
 if sid not in ids:continue
 pd=product.ReferenceProduct.Parent;part=pd.Part;r={'id':sid,'document':pd.Name,'component':props(product),'bodies':[],'surfaces':[],'expected_area':registry[sid].get('area_mm2')}
 for k in range(1,part.Bodies.Count+1):
  b=part.Bodies.Item(k);entry={'name':b.Name,'count':b.Shapes.Count,'display':props(b)}
  if b.Shapes.Count:
   shape=b.Shapes.Item(b.Shapes.Count);entry['shape']={'name':shape.Name,'display':props(shape)}
   try:entry['area']=pd.GetWorkbench('SPAWorkbench').GetMeasurable(part.CreateReferenceFromObject(shape)).Area
   except Exception as e:entry['area_error']=str(e)
  r['bodies'].append(entry)
 for k in range(1,part.HybridBodies.Count+1):
  h=part.HybridBodies.Item(k);entry={'name':h.Name,'display':props(h),'count':h.HybridShapes.Count}
  if h.HybridShapes.Count:entry['shape']=props(h.HybridShapes.Item(1))
  r['surfaces'].append(entry)
 rows.append(r)
sel.Clear();(F/'visibility-diagnostic.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print(json.dumps(rows,ensure_ascii=False,default=str))
