"""Focused CATIA MCP-style tool extension: exact surface inspection derivatives."""
import json, sys, time
from pathlib import Path

def get_cog(measurable):
    import pythoncom
    values=measurable._oleobj_.InvokeTypes(measurable._oleobj_.GetIDsOfNames('GetCOG'),0,pythoncom.DISPATCH_METHOD,(pythoncom.VT_EMPTY,0),((pythoncom.VT_BYREF|pythoncom.VT_ARRAY|pythoncom.VT_VARIANT,3),),tuple(0. for _ in range(3)))
    return [float(v) for v in values]

class SurfaceDerivativeTools:
    def __init__(self, connection): self.conn=connection
    def get_tool_definitions(self):
        return [{'name':'catia_build_surface_inspection_product','description':'Copy exact indexed and named source surfaces without links, verify area/centroid, and assemble with existing inspection solids.','inputSchema':{'type':'object','properties':{'request_path':{'type':'string'}},'required':['request_path']}}]
    def execute(self, name, args):
        if name!='catia_build_surface_inspection_product': raise ValueError(name)
        request=json.loads(Path(args['request_path']).read_text(encoding='utf-8-sig'))
        app=self.conn.app; source=app.Documents.Item(request['source_document']); source.Activate()
        output=Path(request['output_directory']).resolve(); output.mkdir(parents=True,exist_ok=True)
        product_path=output/(request['product_name']+'.CATProduct')
        if product_path.exists(): raise ValueError('Output already exists')
        before=(bool(source.Saved),int(source.Part.Bodies.Count),int(source.Part.HybridBodies.Count))
        sel=source.Selection; previous=[sel.Item2(i).Value for i in range(1,sel.Count2+1)]
        spa=source.GetWorkbench('SPAWorkbench'); resolved=[]
        for item in request['surfaces']:
            parent=source.Part
            for index in item['source_set_indices']: parent=parent.HybridBodies.Item(index)
            element=parent.HybridShapes.Item(item['source_element_index'])
            if str(element.Name)!=item['name']: raise ValueError('Surface identity mismatch: '+item['name'])
            ref=source.Part.CreateReferenceFromObject(element); measurable=spa.GetMeasurable(ref)
            center=get_cog(measurable)
            resolved.append((item,element,float(measurable.Area)*1e6,center))
        audit={'source_document':source.Name,'surfaces':[],'source_saved_by_tool':False,'status':'RUNNING'}
        audit_path=output/'surface-copy-audit.json'; started=time.perf_counter()
        def save(): audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        paths=[]
        try:
            for item,element,area,center in resolved:
                source.Activate(); sel.Clear(); sel.Add(element); sel.Copy(); sel.Clear()
                target=app.Documents.Add('Part'); target.Activate(); part=target.Part
                target.Product.PartNumber=item['shape_id']; group=part.HybridBodies.Add(); group.Name='InspectionSurface'
                dest=target.Selection; dest.Clear(); dest.Add(group); dest.PasteSpecial('CATPrtResultWithOutLink'); dest.Clear()
                if group.HybridShapes.Count!=1: raise RuntimeError('Copied surface count mismatch')
                copied=group.HybridShapes.Item(1); copied.Name=item['name']; part.Update()
                m=target.GetWorkbench('SPAWorkbench').GetMeasurable(part.CreateReferenceFromObject(copied))
                copied_area=float(m.Area)*1e6; copied_center=get_cog(m)
                if abs(copied_area-area)>max(1e-6,abs(area)*1e-8) or max(abs(a-b) for a,b in zip(center,copied_center))>1e-6:
                    raise RuntimeError('Surface area or position changed during copy')
                dest.Add(copied); dest.VisProperties.SetShow(0); dest.Clear()
                path=output/(item['shape_id']+'.CATPart'); target.SaveAs(str(path)); paths.append(str(path))
                audit['surfaces'].append({**item,'file':str(path),'source_area_mm2':area,'copied_area_mm2':copied_area,'source_centroid':center,'copied_centroid':copied_center,'verified':True})
                save(); print(json.dumps({'stage':'SURFACE_COPY','completed':len(paths),'total':len(resolved)},ensure_ascii=False),flush=True)
                target.Close()
            product=app.Documents.Add('Product'); product.Product.PartNumber=request['product_name']
            for path in request['solid_files']+paths: product.Product.Products.AddComponentsFromFiles([path],'All')
            product.Product.Update()
            if product.Product.Products.Count!=len(request['solid_files'])+len(paths): raise RuntimeError('Assembly component count mismatch')
            product.SaveAs(str(product_path)); audit.update(status='COMPLETE',product=str(product_path),solid_count=len(request['solid_files']),surface_count=len(paths),elapsed_seconds=time.perf_counter()-started)
        except Exception as exc:
            audit.update(status='ERROR',error=str(exc)); raise
        finally:
            source.Activate(); sel.Clear()
            for element in previous: sel.Add(element)
            audit['source_state_unchanged']=before==(bool(source.Saved),int(source.Part.Bodies.Count),int(source.Part.HybridBodies.Count)); save()
        product.Activate(); return audit

if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/'CATIA管路智能检查系统_内网移植包_4.8.0_20260924/vendor/catia-v5-mcp-server'))
    from catia_mcp.connection import CATIAConnection
    conn=CATIAConnection(); print(conn.connect(),flush=True)
    result=SurfaceDerivativeTools(conn).execute('catia_build_surface_inspection_product',{'request_path':sys.argv[1]})
    print(json.dumps({'status':result['status'],'surface_count':result['surface_count'],'elapsed_seconds':result['elapsed_seconds']},ensure_ascii=False),flush=True)
