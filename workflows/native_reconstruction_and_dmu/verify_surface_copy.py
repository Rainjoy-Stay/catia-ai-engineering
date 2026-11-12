import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from surface_derivative_tool import get_cog
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
from catia_mcp.connection import CATIAConnection
c=CATIAConnection();c.connect();a=c.app; source=a.Documents.Item('涡轮发动机.CATPart')
folder=Path(__file__).parent; path=folder/'inspection-assembly64/surface-copy-audit.json'; audit=json.loads(path.read_text(encoding='utf8'));rows=[]
for r in audit['surfaces']:
    parent=source.Part
    for i in r['source_set_indices']:parent=parent.HybridBodies.Item(i)
    el=parent.HybridShapes.Item(r['source_element_index'])
    assert el.Name==r['name']
    target=a.Documents.Item(Path(r['file']).name); copied=target.Part.HybridBodies.Item(1).HybridShapes.Item(1)
    ms=source.GetWorkbench('SPAWorkbench').GetMeasurable(source.Part.CreateReferenceFromObject(el))
    mt=target.GetWorkbench('SPAWorkbench').GetMeasurable(target.Part.CreateReferenceFromObject(copied))
    sc,tc=get_cog(ms),get_cog(mt); delta=math.dist(sc,tc)
    assert delta<1e-6
    r.update(source_centroid=sc,copied_centroid=tc,centroid_delta_mm=delta,centroid_method='EXPLICIT_BYREF_SAFEARRAY_GETCOG',verified=True)
    rows.append({'name':r['name'],'source_centroid':sc,'copied_centroid':tc,'delta_mm':delta})
audit['centroid_verification_corrected']=True;path.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
(folder/'surface-position-verification.json').write_text(json.dumps({'count':len(rows),'max_delta_mm':max(r['delta_mm'] for r in rows),'rows':rows},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'verified_count':len(rows),'max_delta_mm':max(r['delta_mm'] for r in rows),'first':rows[0]},ensure_ascii=False))
