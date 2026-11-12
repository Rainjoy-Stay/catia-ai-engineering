import sys,json,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];F=ROOT/'output/全量原生DMU检查_20261012';V=ROOT/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924'
sys.path.insert(0,str(V/'vendor/catia-v5-mcp-server'))
spec=importlib.util.spec_from_file_location('probe_generic',V/'project/tools/report_capture_reference_20260920/capture_generic_dual_view_20261010.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g);g.PROP_COLOR=2;g.PROP_OPACITY=3
from catia_mcp.connection import CATIAConnection
c=CATIAConnection();c.connect();app=c.app;doc=app.Documents.Item('NativeDMU_Full_20261012.CATProduct');doc.Activate();sel=doc.Selection;viewer=app.ActiveWindow.ActiveViewer;cam=g.snapshot_camera(app,viewer.Viewpoint3D);rows=[]
for sid in ('BODY_000872','BODY_000817'):
 index=int(sid.split('_')[1]);product=doc.Product.Products.Item(index)
 if product.PartNumber!=sid:raise RuntimeError('Identity mismatch')
 part=product.ReferenceProduct.Parent.Part;body=next(part.Bodies.Item(i) for i in range(1,part.Bodies.Count+1) if part.Bodies.Item(i).Shapes.Count);shape=body.Shapes.Item(body.Shapes.Count);item=g.Item(index,sid,sid,'component',product,shape);state=g.snapshot_display(sel,item)
 try:
  g.set_display(sel,item,show=0,color=(255,161,56),opacity=255,color_inheritance=1,opacity_inheritance=1);sel.Clear();sel.Add(shape);p=sel.VisProperties;row={'id':sid,'visible_color':p.GetVisibleColor(),'show':p.GetShow(),'inheritance':p.GetRealInheritance(2)};sel.Clear();g.set_view(viewer,'isometric');viewer.Update();viewer.Reframe();viewer.Update();g.capture(viewer,F/(sid+'-isolated-probe.jpg'),.5);rows.append(row)
 finally:g.restore_display(sel,item,state);g.restore_camera(viewer.Viewpoint3D,cam);sel.Clear();viewer.Update()
(F/'isolated-probe.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(rows))

