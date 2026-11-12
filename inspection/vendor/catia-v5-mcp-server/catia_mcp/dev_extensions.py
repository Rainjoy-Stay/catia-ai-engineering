"""Hot-reloadable CATIA development operations."""

import hashlib
import json
import os
import sys
import tempfile
import time
from array import array
from pathlib import Path
from typing import Any


def _load_locator():
    project = Path(__file__).resolve().parents[3] / "project"
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    from catia_checker.result_locator import load_issue_bodies, select_issue_bodies
    return load_issue_bodies, select_issue_bodies


def _load_target_locator():
    project = Path(__file__).resolve().parents[3] / "project"
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    from catia_checker.result_locator import load_issue_target, select_issue_target
    return load_issue_target, select_issue_target


def dispatch(connection: Any, operation: str, arguments: dict[str, Any]) -> str:
    if operation == 'read_surface_spa_identity':
        connection.ensure_connected(); doc = connection.active_document
        if str(doc.Name) != arguments['document_name'] or Path(str(doc.FullName)).resolve() != Path(arguments['document_path']).resolve():
            raise ValueError('Source document identity mismatch')
        saved = bool(doc.Saved)
        set_index = arguments['set_index']; shape_index = arguments['shape_index']
        if type(set_index) != int or not 1 <= set_index <= int(doc.Part.HybridBodies.Count):
            raise ValueError('Invalid geometrical set index')
        container = doc.Part.HybridBodies.Item(set_index)
        if str(container.Name) != arguments['set_name']: raise ValueError('Set identity mismatch')
        if type(shape_index) != int or not 1 <= shape_index <= int(container.HybridShapes.Count):
            raise ValueError('Invalid surface index')
        shape = container.HybridShapes.Item(shape_index)
        if str(shape.Name) != arguments['shape_name']: raise ValueError('Surface identity mismatch')
        measurable = doc.GetWorkbench('SPAWorkbench').GetMeasurable(doc.Part.CreateReferenceFromObject(shape))
        from catia_mcp.tools.batch_copy_benchmark import centroid_facts
        result = {'document_name':str(doc.Name), 'document_path':str(doc.FullName),
            'set_index':set_index, 'set_name':str(container.Name), 'shape_index':shape_index,
            'shape_name':str(shape.Name), 'surface_area_mm2':float(measurable.Area)*1e6,
            **centroid_facts(measurable), 'saved_before':saved, 'saved_after':bool(doc.Saved),
            'source_modified':False, 'source_saved_by_tool':False}
        if result['saved_after'] != saved: raise RuntimeError('Source saved state changed')
        path = Path(arguments['output_path']).resolve()
        if path.exists(): raise ValueError('Overwrite prohibited')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return json.dumps(result,ensure_ascii=False)
    if operation == 'read_exact_body_pair_distance':
        connection.ensure_connected();doc=connection.active_document
        if str(doc.Name)!=arguments['document_name'] or Path(str(doc.FullName)).resolve()!=Path(arguments['document_path']).resolve():
            raise ValueError('Source document identity mismatch')
        saved=bool(doc.Saved);refs=[];identities=[]
        for target in arguments['bodies']:
            index=target['index']
            if type(index)!=int or not 1<=index<=int(doc.Part.Bodies.Count):raise ValueError('Invalid Body index')
            body=doc.Part.Bodies.Item(index)
            if str(body.Name)!=target['name']:raise ValueError('Body identity mismatch')
            refs.append(doc.Part.CreateReferenceFromObject(body));identities.append(target)
        if len(refs)!=2:raise ValueError('Exactly two bodies required')
        distance=float(doc.GetWorkbench('SPAWorkbench').GetMeasurable(refs[0]).GetMinimumDistance(refs[1]))
        result={'bodies':identities,'minimum_distance_mm':distance,'source_modified':False,
                'saved_before':saved,'saved_after':bool(doc.Saved),
                'limitation':'Zero distance does not distinguish touching from penetration'}
        if result['saved_after']!=saved:raise RuntimeError('Source state changed')
        path=Path(arguments['output_path']).resolve()
        if path.exists():raise ValueError('Overwrite prohibited')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return json.dumps(result,ensure_ascii=False)
    if operation == 'read_body_spa_identity':
        connection.ensure_connected();doc=connection.active_document
        if str(doc.Name)!=arguments['document_name'] or Path(str(doc.FullName)).resolve()!=Path(arguments['document_path']).resolve():
            raise ValueError('Source document identity mismatch')
        index=arguments['body_index']
        if type(index)!=int or not 1<=index<=int(doc.Part.Bodies.Count):raise ValueError('Invalid Body index')
        body=doc.Part.Bodies.Item(index)
        if str(body.Name)!=arguments['body_name']:raise ValueError('Body name mismatch')
        from catia_mcp.tools.batch_copy_benchmark import measurements
        saved=bool(doc.Saved)
        record={'document_name':str(doc.Name),'document_path':str(doc.FullName),'body_index':index,
                'body_name':str(body.Name),'saved_before':saved,**measurements(doc,body),
                'saved_after':bool(doc.Saved),'source_modified':False}
        if record['saved_after']!=saved:raise RuntimeError('Source saved state changed')
        path=Path(arguments['output_path']).resolve()
        if path.exists():raise ValueError('Overwrite prohibited')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        return json.dumps(record,ensure_ascii=False)
    if operation == "issue_route_preflight_token":
        project = Path(__file__).resolve().parents[3] / "project"
        if str(project) not in sys.path:
            sys.path.insert(0, str(project))
        from catia_checker.route_preflight_tokens import issue_preflight_token
        return json.dumps(issue_preflight_token(
            arguments["result_file"], int(arguments.get("candidate_rank", 1))),
            ensure_ascii=False, indent=2)
    if operation == "create_validated_arrangement_run":
        import importlib
        from catia_mcp.tools import tubing as tubing_module
        tubing_module = importlib.reload(tubing_module)
        return tubing_module.TubingTools(connection).execute(
            "catia_tubing_create_validated_arrangement_run", arguments)
    if operation == "ping":
        return '{"status":"ok","hot_reload":true}'
    if operation == "import_neutral_for_inspection":
        return _import_neutral_for_inspection(connection, arguments)
    if operation == "export_inspection_bodies":
        return _export_inspection_bodies(connection, arguments)
    if operation == "select_inspection_bodies":
        return _select_inspection_bodies(connection, arguments)
    if operation == "isolate_inspection_bodies":
        return _isolate_inspection_bodies(connection, arguments)
    if operation == "rename_inspection_bodies":
        return _rename_inspection_bodies(connection, arguments)
    if operation == "restore_distinguishable_body_names":
        return _restore_distinguishable_body_names(connection, arguments)
    if operation == "show_all_inspection_bodies":
        return _show_all_inspection_bodies(connection, arguments)
    if operation == "inspect_component_route_context":
        return _inspect_component_route_context(connection, arguments)
    if operation == "inspect_part_point_candidates":
        return _inspect_part_point_candidates(connection, arguments)
    if operation == "inspect_component_body_points":
        return _inspect_component_body_points(connection, arguments)
    if operation == "inspect_component_surface_point_normals":
        return _inspect_component_surface_point_normals(connection, arguments)
    if operation == "derive_component_point_surface_normals":
        return _derive_component_point_surface_normals(connection, arguments)
    if operation == "inspect_component_vertex_bounds":
        return _inspect_component_vertex_bounds(connection, arguments)
    if operation == "export_component_mesh_json":
        return _export_component_mesh_json(connection, arguments)
    if operation == "measure_body_points_to_components":
        return _measure_body_points_to_components(connection, arguments)
    if operation == "simulate_arrangement_route":
        return _simulate_arrangement_route(connection, arguments)
    if operation == "probe_arrangement_automation":
        connection.ensure_connected()
        root = connection.active_document.Product
        arrangement = None
        for token in ("CATIAArrangementProduct", "ArrangementProduct"):
            try:
                arrangement = root.GetTechnologicalObject(token)
                if arrangement is not None: break
            except Exception: pass
        if arrangement is None: raise RuntimeError("Arrangement Product is unavailable")
        def describe(obj):
            info = obj._oleobj_.GetTypeInfo(); attr = info.GetTypeAttr(); funcs=[]
            for index in range(attr.cFuncs):
                desc=info.GetFuncDesc(index); memid=desc.memid if hasattr(desc,"memid") else desc[0]
                try: names=list(info.GetNames(memid))
                except Exception: names=[]
                funcs.append({"memid":int(memid),"names":names})
            return {"python_type":str(type(obj)),"functions":funcs}
        payload={"arrangement":describe(arrangement)}
        try: payload["runs"]=describe(arrangement.ArrangementRuns)
        except Exception as exc: payload["runs_error"]=str(exc)
        return json.dumps(payload,ensure_ascii=False,indent=2)
    if operation == "probe_component_named_objects":
        connection.ensure_connected(); root=connection.active_document.Product
        component_name=str(arguments["component_name"])
        matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        part=matches[0].ReferenceProduct.Parent.Part; rows=[]
        for name in arguments["names"]:
            obj=part.FindObjectByName(str(name)); row={"name":str(name),"found":obj is not None}
            if obj is not None:
                row["python_type"]=str(type(obj)); values={}
                for prop in ("X","Y","Z","XValue","YValue","ZValue","Direction","Surface","Support","Orientation"):
                    try: values[prop]=str(getattr(obj,prop))
                    except Exception: pass
                row["values"]=values
                try:
                    info=obj._oleobj_.GetTypeInfo(); attr=info.GetTypeAttr(); methods=[]
                    for index in range(attr.cFuncs):
                        desc=info.GetFuncDesc(index); memid=desc.memid if hasattr(desc,"memid") else desc[0]
                        try: names=list(info.GetNames(memid))
                        except Exception: names=[]
                        if names: methods.append(names)
                    row["methods"]=methods
                except Exception as exc: row["typeinfo_error"]=str(exc)
            rows.append(row)
        return json.dumps({"component":component_name,"objects":rows},ensure_ascii=False,indent=2)
    if operation == "read_component_directions":
        connection.ensure_connected(); root=connection.active_document.Product
        component_name=str(arguments["component_name"])
        matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        component=matches[0]; part=component.ReferenceProduct.Parent.Part
        import pythoncom, math
        transform=list(component.Position._oleobj_.InvokeTypes(component.Position._oleobj_.GetIDsOfNames("GetComponents"),0,
            pythoncom.DISPATCH_METHOD,(pythoncom.VT_EMPTY,0),((pythoncom.VT_BYREF|pythoncom.VT_ARRAY|pythoncom.VT_VARIANT,3),),tuple(0.0 for _ in range(12))))
        x_axis,y_axis,z_axis=transform[0:3],transform[3:6],transform[6:9]
        rows=[]
        for name in arguments["names"]:
            obj=part.FindObjectByName(str(name))
            def scalar(method, fallback):
                try: value=getattr(obj,method)()
                except Exception: value=getattr(obj,fallback)()
                try: return float(value.Value)
                except Exception: return float(value)
            local=[scalar("GetXVal","GetX"),scalar("GetYVal","GetY"),scalar("GetZVal","GetZ")]
            world=[x_axis[0]*local[0]+y_axis[0]*local[1]+z_axis[0]*local[2],
                   x_axis[1]*local[0]+y_axis[1]*local[1]+z_axis[1]*local[2],
                   x_axis[2]*local[0]+y_axis[2]*local[1]+z_axis[2]*local[2]]
            length=math.sqrt(sum(v*v for v in world)); world=[v/length for v in world]
            rows.append({"name":str(name),"local":local,"world_unit":world})
        return json.dumps({"component":component_name,"directions":rows},ensure_ascii=False,indent=2)
    if operation == "inspect_component_sketch":
        connection.ensure_connected(); root=connection.active_document.Product
        component_name=str(arguments["component_name"]); sketch_name=str(arguments["sketch_name"])
        matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        part=matches[0].ReferenceProduct.Parent.Part; sketch=None; body_name=None
        for bi in range(1,part.Bodies.Count+1):
            body=part.Bodies.Item(bi)
            for si in range(1,body.Sketches.Count+1):
                candidate=body.Sketches.Item(si)
                if str(candidate.Name)==sketch_name: sketch=candidate; body_name=str(body.Name); break
            if sketch is not None: break
        if sketch is None: raise ValueError(f"Sketch '{sketch_name}' not found")
        geometry=[]
        import pythoncom
        def point2d_coords(point):
            return list(point._oleobj_.InvokeTypes(point._oleobj_.GetIDsOfNames("GetCoordinates"),0,
                pythoncom.DISPATCH_METHOD,(pythoncom.VT_EMPTY,0),
                ((pythoncom.VT_BYREF|pythoncom.VT_ARRAY|pythoncom.VT_VARIANT,2),),(0.0,0.0)))
        for i in range(1,sketch.GeometricElements.Count+1):
            item=sketch.GeometricElements.Item(i); row={"index":i,"name":str(getattr(item,"Name",f"Geometry.{i}")),"type":str(type(item))}
            for prop in ("Radius","StartAngle","EndAngle","Construction"):
                try: row[prop]=getattr(item,prop)
                except Exception: pass
            try: row["coordinates"]=point2d_coords(item)
            except Exception: pass
            try: row["start"]=point2d_coords(item.StartPoint)
            except Exception: pass
            try: row["end"]=point2d_coords(item.EndPoint)
            except Exception: pass
            try: row["center"]=point2d_coords(item.CenterPoint)
            except Exception: pass
            geometry.append(row)
        constraints=[]
        for i in range(1,sketch.Constraints.Count+1):
            c=sketch.Constraints.Item(i); row={"index":i,"name":str(c.Name)}
            for prop in ("Type","Status"):
                try: row[prop]=getattr(c,prop)
                except Exception: pass
            try: row["value"]=float(c.Dimension.Value)
            except Exception: pass
            constraints.append(row)
        axis_data = list(sketch._oleobj_.InvokeTypes(
            sketch._oleobj_.GetIDsOfNames("GetAbsoluteAxisData"), 0,
            pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
            ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
            tuple(0.0 for _ in range(9))))
        return json.dumps({"component":component_name,"body":body_name,"sketch":sketch_name,
                           "absolute_axis_data":axis_data,"geometry":geometry,
                           "constraints":constraints},ensure_ascii=False,indent=2)
    if operation == "scale_component_parametric_geometry":
        import pythoncom
        connection.ensure_connected(); assembly=connection.active_document; root=assembly.Product
        component_names=[str(v) for v in arguments["component_names"]]; factor=float(arguments["factor"])
        if factor<=0: raise ValueError("factor must be positive")
        expected=float(arguments.get("expected_part2_max_radius",120.0)); target=float(arguments.get("target_part2_max_radius",820.0))
        if abs(expected*factor-target)>1e-6: raise ValueError("factor does not match the verified Part2 target radius")
        products={str(root.Products.Item(i).Name):root.Products.Item(i) for i in range(1,root.Products.Count+1)}
        rows=[]
        for component_name in component_names:
            if component_name not in products: raise ValueError(f"Component '{component_name}' not found")
            document=products[component_name].ReferenceProduct.Parent; part=document.Part
            scaled_points=0; scaled_circles=0; scaled_limits=0; scaled_offsets=0
            for bi in range(1,part.Bodies.Count+1):
                body=part.Bodies.Item(bi)
                for si in range(1,body.Sketches.Count+1):
                    sketch=body.Sketches.Item(si)
                    sketch.OpenEdition()
                    try:
                        for gi in range(1,sketch.GeometricElements.Count+1):
                            item=sketch.GeometricElements.Item(gi)
                            try:
                                coords=list(item._oleobj_.InvokeTypes(item._oleobj_.GetIDsOfNames("GetCoordinates"),0,
                                    pythoncom.DISPATCH_METHOD,(pythoncom.VT_EMPTY,0),
                                    ((pythoncom.VT_BYREF|pythoncom.VT_ARRAY|pythoncom.VT_VARIANT,2),),(0.0,0.0)))
                                item.SetData(float(coords[0])*factor,float(coords[1])*factor); scaled_points+=1
                            except Exception: pass
                            try:
                                radius=float(item.Radius); item.Radius=radius*factor; scaled_circles+=1
                            except Exception: pass
                    finally:
                        sketch.CloseEdition()
                for hi in range(1,int(body.HybridShapes.Count)+1):
                    shape=body.HybridShapes.Item(hi)
                    try:
                        offset=shape.Offset; offset.Value=float(offset.Value)*factor; scaled_offsets+=1
                    except Exception: pass
                for fi in range(1,int(body.Shapes.Count)+1):
                    feature=body.Shapes.Item(fi)
                    for limit_name in ("FirstLimit","SecondLimit"):
                        try:
                            dimension=getattr(feature,limit_name).Dimension
                            value=float(dimension.Value)
                            if abs(value)>1e-12: dimension.Value=value*factor; scaled_limits+=1
                        except Exception: pass
            part.Update()
            rows.append({"component":component_name,"document":str(document.Name),"scaled_points":scaled_points,
                         "scaled_circles":scaled_circles,"scaled_feature_limits":scaled_limits,
                         "scaled_point_offsets":scaled_offsets,"update_ok":bool(part.IsUpToDate(part))})
        assembly.Product.Update()
        return json.dumps({"factor":factor,"part2_radius_before_mm":expected,"part2_radius_after_mm":target,
                           "components":rows,"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "repair_component_sketch_circles":
        import pythoncom, math
        connection.ensure_connected(); root=connection.active_document.Product; rows=[]
        products={str(root.Products.Item(i).Name):root.Products.Item(i) for i in range(1,root.Products.Count+1)}
        def coords(point):
            return list(point._oleobj_.InvokeTypes(point._oleobj_.GetIDsOfNames("GetCoordinates"),0,
                pythoncom.DISPATCH_METHOD,(pythoncom.VT_EMPTY,0),
                ((pythoncom.VT_BYREF|pythoncom.VT_ARRAY|pythoncom.VT_VARIANT,2),),(0.0,0.0)))
        for component_name in [str(v) for v in arguments["component_names"]]:
            part=products[component_name].ReferenceProduct.Parent.Part; count=0
            for bi in range(1,part.Bodies.Count+1):
                body=part.Bodies.Item(bi)
                for si in range(1,body.Sketches.Count+1):
                    sketch=body.Sketches.Item(si); sketch.OpenEdition()
                    try:
                        for gi in range(1,sketch.GeometricElements.Count+1):
                            item=sketch.GeometricElements.Item(gi)
                            try:
                                center=coords(item.CenterPoint); start=coords(item.StartPoint)
                                radius=math.hypot(start[0]-center[0],start[1]-center[1])
                                item.SetData(float(center[0]),float(center[1]),float(radius)); count+=1
                            except Exception: pass
                    finally: sketch.CloseEdition()
            part.Update(); rows.append({"component":component_name,"repaired_circles":count,"update_ok":bool(part.IsUpToDate(part))})
        root.Update(); return json.dumps({"components":rows,"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "create_scaled_interface_references":
        import pythoncom
        connection.ensure_connected(); assembly=connection.active_document; root=assembly.Product
        component_name=str(arguments["component_name"]); factor=float(arguments["factor"])
        matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        component=matches[0]; document=component.ReferenceProduct.Parent; part=document.Part
        body=part.Bodies.Item(str(arguments["body_name"])); hsf=part.HybridShapeFactory
        hb=part.HybridBodies.Add(); hb.Name=str(arguments.get("set_name","ScaledInterfaceReferences"))
        center=hsf.AddNewPointCoord(0.0,0.0,0.0); center.Name="ScaleCenter_Origin"; hb.AppendHybridShape(center); part.Update()
        center_ref=part.CreateReferenceFromObject(center); created=[]
        for spec in arguments["references"]:
            source=body.HybridShapes.Item(int(spec["source_index"])); source_ref=part.CreateReferenceFromObject(source)
            scaled=hsf.AddNewHybridScaling(source_ref,center_ref,factor); hb.AppendHybridShape(scaled); part.Update()
            scaled_ref=part.CreateReferenceFromObject(scaled); kind=str(spec["kind"]).lower()
            if kind=="point": datum=hsf.AddNewPointDatum(scaled_ref)
            elif kind=="surface": datum=hsf.AddNewSurfaceDatum(scaled_ref)
            elif kind=="curve": datum=hsf.AddNewCurveDatum(scaled_ref)
            else: raise ValueError(f"Unsupported reference kind '{kind}'")
            datum.Name=str(spec["name"]); hb.AppendHybridShape(datum); part.Update(); hsf.DeleteObjectForDatum(scaled)
            created.append({"source_index":int(spec["source_index"]),"source_name":str(source.Name),"name":str(datum.Name),"kind":kind})
        part.Update(); root.Update()
        transform=list(component.Position._oleobj_.InvokeTypes(component.Position._oleobj_.GetIDsOfNames("GetComponents"),0,
            pythoncom.DISPATCH_METHOD,(pythoncom.VT_EMPTY,0),((pythoncom.VT_BYREF|pythoncom.VT_ARRAY|pythoncom.VT_VARIANT,3),),tuple(0.0 for _ in range(12))))
        x_axis,y_axis,z_axis,origin=transform[0:3],transform[3:6],transform[6:9],transform[9:12]
        spa=document.GetWorkbench("SPAWorkbench")
        for row in created:
            if row["kind"]!="point": continue
            datum=hb.HybridShapes.Item(row["name"]); measurable=spa.GetMeasurable(part.CreateReferenceFromObject(datum))
            local=list(measurable._oleobj_.InvokeTypes(measurable._oleobj_.GetIDsOfNames("GetPoint"),0,
                pythoncom.DISPATCH_METHOD,(pythoncom.VT_EMPTY,0),((pythoncom.VT_BYREF|pythoncom.VT_ARRAY|pythoncom.VT_VARIANT,3),),(0.0,0.0,0.0)))
            row["local_mm"]=local; row["world_mm"]=[origin[0]+x_axis[0]*local[0]+y_axis[0]*local[1]+z_axis[0]*local[2],
                origin[1]+x_axis[1]*local[0]+y_axis[1]*local[1]+z_axis[1]*local[2],
                origin[2]+x_axis[2]*local[0]+y_axis[2]*local[1]+z_axis[2]*local[2]]
        return json.dumps({"component":component_name,"set_name":str(hb.Name),"factor":factor,"created":created,
                           "update_ok":bool(part.IsUpToDate(part)),"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "delete_component_hybrid_body":
        connection.ensure_connected(); root=connection.active_document.Product
        component_name=str(arguments["component_name"]); set_name=str(arguments["set_name"])
        matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        document=matches[0].ReferenceProduct.Parent; part=document.Part; hb=part.HybridBodies.Item(set_name)
        try:
            part.HybridBodies.Remove(set_name)
        except Exception:
            assembly=connection.active_document; assembly.Activate(); selection=assembly.Selection; selection.Clear(); selection.Add(hb); selection.Delete(); selection.Clear()
        part.Update(); root.Update()
        return json.dumps({"component":component_name,"deleted_set":set_name,"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "create_exact_interface_basis":
        connection.ensure_connected(); root=connection.active_document.Product
        component_name=str(arguments["component_name"]); matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        document=matches[0].ReferenceProduct.Parent; part=document.Part; hsf=part.HybridShapeFactory
        hb=part.HybridBodies.Add(); hb.Name=str(arguments["set_name"]); created=[]
        for spec in arguments["interfaces"]:
            p=[float(v) for v in spec["local_point"]]; n=[float(v) for v in spec["local_normal"]]
            point=hsf.AddNewPointCoord(p[0],p[1],p[2]); point.Name=str(spec["point_name"]); hb.AppendHybridShape(point); part.Update()
            d=-(n[0]*p[0]+n[1]*p[1]+n[2]*p[2]); plane=hsf.AddNewPlaneEquation(n[0],n[1],n[2],d)
            plane.Name=str(spec["plane_name"]); hb.AppendHybridShape(plane); part.Update()
            created.append({"point":str(point.Name),"plane":str(plane.Name),"local_point":p,"local_normal":n})
        root.Update(); return json.dumps({"component":component_name,"set_name":str(hb.Name),"created":created,
                                          "update_ok":bool(part.IsUpToDate(part)),"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "measure_hybridbody_points_to_components":
        connection.ensure_connected(); assembly=connection.active_document; root=assembly.Product
        source_name=str(arguments["source_component"]); set_name=str(arguments["set_name"])
        products={str(root.Products.Item(i).Name):root.Products.Item(i) for i in range(1,root.Products.Count+1)}
        source=products[source_name]; part=source.ReferenceProduct.Parent.Part; hb=part.HybridBodies.Item(set_name)
        spa=assembly.GetWorkbench("SPAWorkbench"); rows=[]
        for point_name in arguments["point_names"]:
            point=hb.HybridShapes.Item(str(point_name)); measurable=spa.GetMeasurableInContext(part.CreateReferenceFromObject(point),source); distances={}
            for target_name in arguments["target_components"]:
                target=products[str(target_name)]; target_part=target.ReferenceProduct.Parent.Part
                distances[str(target_name)]=float(measurable.GetMinimumDistanceInContext(target_part.CreateReferenceFromObject(target_part.MainBody),target))
            rows.append({"point":str(point_name),"distances_mm":distances})
        return json.dumps({"source_component":source_name,"set_name":set_name,"results":rows,"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "set_component_sketch_points":
        connection.ensure_connected(); root=connection.active_document.Product
        component_name=str(arguments["component_name"]); sketch_name=str(arguments["sketch_name"])
        matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        part=matches[0].ReferenceProduct.Parent.Part; sketch=None
        for bi in range(1,part.Bodies.Count+1):
            body=part.Bodies.Item(bi)
            for si in range(1,body.Sketches.Count+1):
                if str(body.Sketches.Item(si).Name)==sketch_name: sketch=body.Sketches.Item(si); break
            if sketch is not None: break
        sketch.OpenEdition(); changed=[]
        try:
            for spec in arguments["points"]:
                item=sketch.GeometricElements.Item(int(spec["index"])); xy=[float(v) for v in spec["coordinates"]]
                item.SetData(xy[0],xy[1]); changed.append({"index":int(spec["index"]),"name":str(item.Name),"coordinates":xy})
        finally: sketch.CloseEdition()
        part.Update(); root.Update(); return json.dumps({"component":component_name,"sketch":sketch_name,"changed":changed,
                                                         "update_ok":bool(part.IsUpToDate(part)),"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "inspect_component_feature_status":
        connection.ensure_connected(); root=connection.active_document.Product; rows=[]
        products={str(root.Products.Item(i).Name):root.Products.Item(i) for i in range(1,root.Products.Count+1)}
        for component_name in arguments["component_names"]:
            part=products[str(component_name)].ReferenceProduct.Parent.Part; features=[]
            for bi in range(1,part.Bodies.Count+1):
                body=part.Bodies.Item(bi)
                for fi in range(1,body.Shapes.Count+1):
                    feature=body.Shapes.Item(fi); features.append({"index":fi,"name":str(feature.Name),"up_to_date":bool(part.IsUpToDate(feature))})
            rows.append({"component":str(component_name),"part_up_to_date":bool(part.IsUpToDate(part)),"features":features})
        return json.dumps({"components":rows,"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "add_component_body_scaling":
        connection.ensure_connected(); root=connection.active_document.Product
        component_name=str(arguments["component_name"]); factor=float(arguments["factor"]); feature_name=str(arguments["feature_name"])
        matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        document=matches[0].ReferenceProduct.Parent; part=document.Part; body=part.Bodies.Item(str(arguments.get("body_name","零件几何体")))
        if body.Shapes.Count<1: return json.dumps({"component":component_name,"skipped":"body has no solid features","source_saved_by_tool":False},ensure_ascii=False,indent=2)
        refset=part.HybridBodies.Add(); refset.Name=f"{feature_name}_基准"; center=part.HybridShapeFactory.AddNewPointCoord(0.0,0.0,0.0)
        center.Name=f"{feature_name}_原点"; refset.AppendHybridShape(center); part.Update()
        part.InWorkObject=body.Shapes.Item(body.Shapes.Count); scale=part.ShapeFactory.AddNewScaling(part.CreateReferenceFromObject(center),factor)
        scale.Name=feature_name; part.Update(); root.Update()
        return json.dumps({"component":component_name,"factor":factor,"feature":str(scale.Name),"reference_set":str(refset.Name),
                           "body_shape_count":int(body.Shapes.Count),"update_ok":bool(part.IsUpToDate(part)),"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "delete_component_body_feature":
        connection.ensure_connected(); root=connection.active_document.Product
        component_name=str(arguments["component_name"]); feature_name=str(arguments["feature_name"])
        matches=[root.Products.Item(i) for i in range(1,root.Products.Count+1) if str(root.Products.Item(i).Name)==component_name]
        if len(matches)!=1: raise ValueError(f"Expected one component '{component_name}', found {len(matches)}")
        document=matches[0].ReferenceProduct.Parent; part=document.Part; body=part.Bodies.Item(str(arguments.get("body_name","零件几何体")))
        before=int(body.Shapes.Count); feature=body.Shapes.Item(feature_name)
        try:
            document.Activate(); selection=document.Selection; selection.Clear(); selection.Add(feature); selection.Delete(); selection.Clear()
        except Exception:
            part.HybridShapeFactory.DeleteObjectForDatum(part.CreateReferenceFromObject(feature))
        try: connection.active_document.Activate()
        except Exception: pass
        part.Update(); root.Update()
        return json.dumps({"component":component_name,"deleted_feature":feature_name,"count_before":before,
                           "count_after":int(body.Shapes.Count),"update_ok":bool(part.IsUpToDate(part)),"source_saved_by_tool":False},ensure_ascii=False,indent=2)
    if operation == "inspect_psp_connectors":
        connection.ensure_connected()
        root = connection.active_document.Product
        wb = root.GetTechnologicalObject("PspWorkbench")
        app = wb.GetApplication(4); app.Initialization(); connection.active_document.Activate()
        out = []
        for owner_name in arguments["owner_names"]:
            matches = [root.Products.Item(i) for i in range(1, root.Products.Count + 1) if str(root.Products.Item(i).Name) == owner_name]
            if len(matches) != 1: raise ValueError(f"Expected one owner '{owner_name}', found {len(matches)}")
            physical = wb.GetInterface("CATIAPspPhysicalProduct", matches[0].ReferenceProduct)
            row = {"owner": owner_name, "connectors": []}
            for i in range(1, int(physical.Connectors.Count) + 1):
                raw = physical.Connectors.Item(i, "CATIAPspPartConnector")
                if arguments.get("set_names"):
                    raw.Name = str(arguments["set_names"].get(owner_name, raw.Name))
                psp = wb.GetInterface("CATIAPspConnector", raw)
                row["connectors"].append({"index": i, "name": str(raw.Name), "connector_name": str(getattr(psp, "ConnectorName", "")), "connected": bool(psp.IsCntrConnected())})
            out.append(row)
        return json.dumps({"owners": out}, ensure_ascii=False, indent=2)
    if operation == "probe_psp_connector_authoring":
        return _probe_psp_connector_authoring(connection, arguments)
    if operation == "test_psp_connector_authoring":
        return _test_psp_connector_authoring(connection, arguments)
    if operation == "create_tubing_interface_carriers":
        import importlib
        from catia_mcp.tools import tubing as tubing_module
        tubing_module = importlib.reload(tubing_module)
        return tubing_module.TubingTools(connection)._create_interface_carriers(arguments["interfaces"])
    if operation == "insert_open_documents_as_components":
        connection.ensure_connected()
        assembly = connection.active_document
        root = assembly.Product
        inserted = []
        for document_name in arguments["document_names"]:
            matches = [connection.app.Documents.Item(i) for i in range(1, connection.app.Documents.Count + 1)
                       if str(connection.app.Documents.Item(i).Name) == str(document_name)]
            if len(matches) != 1:
                raise ValueError(f"Expected one open document named '{document_name}', found {len(matches)}")
            component = root.Products.AddExternalComponent(matches[0])
            inserted.append({"document": document_name, "component": str(component.Name), "part_number": str(component.PartNumber)})
        root.Update()
        return json.dumps({"status": "ok", "inserted": inserted, "component_count": int(root.Products.Count)}, ensure_ascii=False, indent=2)
    if operation == "delete_exact_components":
        connection.ensure_connected()
        document = connection.active_document
        root = document.Product
        requested = [str(v) for v in arguments["component_names"]]
        resolved = []
        for name in requested:
            matches = [root.Products.Item(i) for i in range(1, root.Products.Count + 1) if str(root.Products.Item(i).Name) == name]
            if len(matches) != 1: raise ValueError(f"Expected one component '{name}', found {len(matches)}")
            resolved.append((matches[0], next(i for i in range(1, root.Products.Count + 1) if root.Products.Item(i) is matches[0] or str(root.Products.Item(i).Name) == name)))
        for _, index in sorted(resolved, key=lambda item: item[1], reverse=True):
            root.Products.Remove(index)
        root.Update()
        remaining = [str(root.Products.Item(i).Name) for i in range(1, root.Products.Count + 1)]
        if any(name in remaining for name in requested): raise RuntimeError("Exact component deletion verification failed")
        return json.dumps({"deleted": requested, "component_count": int(root.Products.Count)}, ensure_ascii=False, indent=2)
    if operation == "select_issue_bodies":
        report_path = arguments.get("report_path")
        issue_id = arguments.get("issue_id")
        if not report_path or not issue_id:
            raise ValueError("select_issue_bodies requires report_path and issue_id")
        load_issue_bodies, select_issue_bodies = _load_locator()
        resolved = load_issue_bodies(report_path, str(issue_id))
        result = select_issue_bodies(connection.active_document, resolved)
        result["hot_reload"] = True
        return json.dumps(result, indent=2, ensure_ascii=False)
    if operation == "select_issue_target":
        report_path = arguments.get("report_path")
        issue_id = arguments.get("issue_id")
        if not report_path or not issue_id:
            raise ValueError("select_issue_target requires report_path and issue_id")
        load_issue_target, select_issue_target = _load_target_locator()
        resolved = load_issue_target(report_path, str(issue_id))
        result = select_issue_target(connection.active_document, resolved)
        result["hot_reload"] = True
        return json.dumps(result, indent=2, ensure_ascii=False)
    raise ValueError(f"Unknown hot-reload CATIA operation: {operation}")


def _probe_psp_connector_authoring(connection: Any, arguments: dict[str, Any]) -> str:
    """Read available Tubing physical/connector startup classes and authoring interfaces."""
    connection.ensure_connected()
    document = connection.active_document
    if not str(document.Name).lower().endswith(".catproduct"):
        raise RuntimeError("Active document is not a CATProduct")
    root = document.Product
    workbench = root.GetTechnologicalObject("PspWorkbench")
    application = workbench.GetApplication(4)
    application.Initialization()
    document.Activate()

    def get_interface(name: str, owner: Any) -> Any:
        try:
            return workbench.GetInterface(name, owner)
        except Exception:
            return None

    def list_values(value: Any) -> list[str]:
        if value is None:
            return []
        result = []
        for index in range(1, int(getattr(value, "Count", 0)) + 1):
            try:
                result.append(str(value.Item(index)))
            except Exception:
                continue
        return result

    class_intf = get_interface("CATIAPspClass", application)
    build_intf = get_interface("CATIAPspBuildPart", application)
    app_factory = get_interface("CATIAPspAppFactory", application)
    result = {
        "document": str(document.Name),
        "application_id": 4,
        "interfaces": {
            "class": class_intf is not None,
            "build_part": build_intf is not None,
            "app_factory": app_factory is not None,
        },
        "startup_physicals": list_values(getattr(class_intf, "StartUpPhysicals", None)) if class_intf else [],
        "startup_connectors": list_values(getattr(class_intf, "StartUpConnectors", None)) if class_intf else [],
        "source_saved_by_tool": False,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def _test_psp_connector_authoring(connection: Any, arguments: dict[str, Any]) -> str:
    """Author one connector in a disposable native Tubing part, then close it unsaved."""
    connection.ensure_connected()
    assembly = connection.active_document
    root = assembly.Product
    workbench = root.GetTechnologicalObject("PspWorkbench")
    application = workbench.GetApplication(4)
    application.Initialization()
    assembly.Activate()
    build = workbench.GetInterface("CATIAPspBuildPart", application)
    if build is None:
        raise RuntimeError("CATTubing does not expose CATIAPspBuildPart")
    created_doc = None
    part_doc = None
    try:
        convert_existing = bool(arguments.get("convert_existing", False))
        if convert_existing:
            created_doc = connection.app.Documents.Add("Product")
            temp_root = created_doc.Product
            component = temp_root.Products.AddNewComponent("Part", "MCP_CONNECTOR_CONVERSION_TEST")
            ref_product = component.ReferenceProduct
            part_doc = ref_product.Parent
            workbench = temp_root.GetTechnologicalObject("PspWorkbench")
            application = workbench.GetApplication(4)
            application.Initialization()
            created_doc.Activate()
            build = workbench.GetInterface("CATIAPspBuildPart", application)
            build.ChangePartType(component, "CATTubTubingPart", "MCP_CONNECTOR_CONVERSION_TEST")
        else:
            ref_product = build.NewPart("CATTubTubingPart", "MCP_CONNECTOR_AUTHORING_TEST")
            created_doc = ref_product.Parent
            part_doc = created_doc
        part = part_doc.Part
        hb = part.HybridBodies.Add()
        hb.Name = "ConnectorGeometry"
        factory = part.HybridShapeFactory
        point = factory.AddNewPointCoord(0.0, 0.0, 0.0)
        point.Name = "InterfacePoint"
        hb.AppendHybridShape(point)
        direction = factory.AddNewDirectionByCoord(0.0, 0.0, 1.0)
        line = factory.AddNewLinePtDir(part.CreateReferenceFromObject(point), direction, -10.0, 10.0, False)
        line.Name = "InterfaceAxis"
        hb.AppendHybridShape(line)
        plane = factory.AddNewPlaneEquation(1.0, 0.0, 0.0, 0.0)
        plane.Name = "InterfaceClockPlane"
        hb.AppendHybridShape(plane)
        part.Update()
        physical = workbench.GetInterface("CATIAPspPhysicalProduct", ref_product)
        if physical is None:
            raise RuntimeError("New native Tubing part does not expose CATIAPspPhysicalProduct")
        face_reference = part.CreateReferenceFromObject(point)
        external_support = bool(arguments.get("external_part3_sketch_point", False))
        if external_support:
            assembly_root = assembly.Product
            comps = [assembly_root.Products.Item(i) for i in range(1, assembly_root.Products.Count + 1)
                     if str(assembly_root.Products.Item(i).Name) == "Part3.1"]
            source_part = comps[0].ReferenceProduct.Parent.Part
            source_sketch = source_part.Bodies.Item(1).Sketches.Item("草图.1")
            source_point = source_sketch.GeometricElements.Item(str(arguments.get("point_name", "点.1")))
            face_reference = source_part.CreateReferenceFromObject(source_point)
        connector = physical.AddConnector(
            "CATTubTubingPartConnector",
            face_reference, 3,
            part.CreateReferenceFromObject(line), 2,
            part.CreateReferenceFromObject(plane), 14,
        )
        connectors = physical.Connectors
        result = {
            "status": "ok",
            "physical_type": "CATTubTubingPart",
            "converted_existing_part": convert_existing,
            "external_part3_sketch_point": external_support,
            "connector_class": "CATTubTubingPartConnector",
            "connector_count": int(connectors.Count),
            "connector_name": str(getattr(connector, "ConnectorName", "")),
            "face_type": int(connector.FaceType),
            "align_type": int(connector.AlignType),
            "clock_type": int(connector.ClockType),
            "disposable_document_saved": False,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    finally:
        if created_doc is not None:
            try:
                created_doc.Close()
            except Exception:
                pass
        try:
            assembly.Activate()
        except Exception:
            pass


def _inspect_component_route_context(connection: Any, arguments: dict[str, Any]) -> str:
    """Read named point coordinates and solid bounds through a CATProduct reference."""
    connection.ensure_connected()
    document = connection.active_document
    if not str(document.Name).lower().endswith(".catproduct"):
        raise RuntimeError("Active document is not a CATProduct")
    root = document.Product
    component_name = str(arguments["component_name"])
    point_names = [str(value) for value in arguments.get("point_names", [])]
    matches = [root.Products.Item(i) for i in range(1, root.Products.Count + 1)
               if str(root.Products.Item(i).Name) == component_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one component named '{component_name}', found {len(matches)}")
    component = matches[0]
    source_document = component.ReferenceProduct.Parent
    part = source_document.Part

    import pythoncom
    transform = list(component.Position._oleobj_.InvokeTypes(
        component.Position._oleobj_.GetIDsOfNames("GetComponents"), 0,
        pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
        ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
        tuple(0.0 for _ in range(12))))
    x_axis, y_axis, z_axis, origin = transform[0:3], transform[3:6], transform[6:9], transform[9:12]
    spa = source_document.GetWorkbench("SPAWorkbench")
    points = []
    for name in point_names:
        feature = part.FindObjectByName(name)
        if feature is None:
            raise ValueError(f"Point feature '{name}' was not found in '{source_document.Name}'")
        measurable = spa.GetMeasurable(part.CreateReferenceFromObject(feature))
        local = list(measurable._oleobj_.InvokeTypes(
            measurable._oleobj_.GetIDsOfNames("GetPoint"), 0,
            pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
            ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
            (0.0, 0.0, 0.0)))
        world = [
            origin[0] + x_axis[0] * local[0] + y_axis[0] * local[1] + z_axis[0] * local[2],
            origin[1] + x_axis[1] * local[0] + y_axis[1] * local[1] + z_axis[1] * local[2],
            origin[2] + x_axis[2] * local[0] + y_axis[2] * local[1] + z_axis[2] * local[2],
        ]
        points.append({"name": name, "local_mm": local, "world_mm": world,
                       "type": str(getattr(feature, "Type", type(feature).__name__))})

    include_bounds = bool(arguments.get("include_bounds", True))
    from catia_mcp.arrangement_geometry import _parse_stl, mesh_bounds
    local_vertices, triangles = [], []
    if not include_bounds:
        result = {
            "schema_version": "catia.component-route-context.v1.0",
            "document": str(document.Name),
            "component": component_name,
            "referenced_document": str(source_document.Name),
            "transform": transform,
            "points": points,
            "solid_bounds_world_mm": None,
            "triangle_count": 0,
            "bounds_skipped": True,
            "source_saved_by_tool": False,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    handle, stl_path = tempfile.mkstemp(suffix=".stl", prefix="catia_route_context_")
    os.close(handle)
    os.unlink(stl_path)
    try:
        source_document.Activate()
        source_document.ExportData(stl_path, "stl")
        if os.path.exists(stl_path):
            local_vertices, triangles = _parse_stl(stl_path)
        else:
            local_vertices, triangles = [], []
    finally:
        try:
            document.Activate()
        except Exception:
            pass
        if os.path.exists(stl_path):
            os.unlink(stl_path)
    if not local_vertices:
        temporary_document = None
        try:
            selection = document.Selection
            selection.Clear()
            selection.Add(component)
            selection.Copy()
            selection.Clear()
            temporary_document = connection.app.Documents.Add("Part")
            temporary_part = temporary_document.Part
            target_selection = temporary_document.Selection
            target_selection.Add(temporary_part.MainBody)
            target_selection.PasteSpecial("CATPrtResultWithOutLink")
            target_selection.Clear()
            temporary_part.Update()
            temporary_document.ExportData(stl_path, "stl")
            local_vertices, triangles = _parse_stl(stl_path)
        finally:
            if os.path.exists(stl_path):
                os.unlink(stl_path)
            if temporary_document is not None:
                temporary_document.Close()
            document.Activate()
    vertices = [(
        origin[0] + x_axis[0] * p[0] + y_axis[0] * p[1] + z_axis[0] * p[2],
        origin[1] + x_axis[1] * p[0] + y_axis[1] * p[1] + z_axis[1] * p[2],
        origin[2] + x_axis[2] * p[0] + y_axis[2] * p[1] + z_axis[2] * p[2],
    ) for p in local_vertices]
    result = {
        "schema_version": "catia.component-route-context.v1.0",
        "document": str(document.Name),
        "component": component_name,
        "referenced_document": str(source_document.Name),
        "transform": transform,
        "points": points,
        "solid_bounds_world_mm": mesh_bounds(vertices) if vertices else None,
        "triangle_count": len(triangles),
        "source_saved_by_tool": False,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def _inspect_part_point_candidates(connection: Any, arguments: dict[str, Any]) -> str:
    """Enumerate point-like body features and sketch geometry without name guessing."""
    connection.ensure_connected()
    document = connection.active_document
    root = document.Product
    name = str(arguments["component_name"])
    matches = [root.Products.Item(i) for i in range(1, root.Products.Count + 1)
               if str(root.Products.Item(i).Name) == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one component named '{name}', found {len(matches)}")
    source = matches[0].ReferenceProduct.Parent
    component = matches[0]
    part = source.Part
    import pythoncom
    transform = list(component.Position._oleobj_.InvokeTypes(
        component.Position._oleobj_.GetIDsOfNames("GetComponents"), 0,
        pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
        ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
        tuple(0.0 for _ in range(12))))
    result = {"component": name, "document": str(source.Name), "body_shapes": [], "sketch_geometry": []}
    for bi in range(1, part.Bodies.Count + 1):
        body = part.Bodies.Item(bi)
        shapes = body.Shapes
        for si in range(1, shapes.Count + 1):
            obj = shapes.Item(si)
            result["body_shapes"].append({"body": str(body.Name), "index": si, "name": str(obj.Name), "type": str(getattr(obj, "Type", type(obj).__name__))})
        sketches = body.Sketches
        for ki in range(1, sketches.Count + 1):
            sketch = sketches.Item(ki)
            axis = list(sketch._oleobj_.InvokeTypes(
                sketch._oleobj_.GetIDsOfNames("GetAbsoluteAxisData"), 0,
                pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
                ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
                tuple(0.0 for _ in range(9))))
            elements = sketch.GeometricElements
            for gi in range(1, elements.Count + 1):
                obj = elements.Item(gi)
                entry = {"body": str(body.Name), "sketch": str(sketch.Name), "index": gi, "name": str(obj.Name), "type": str(getattr(obj, "Type", type(obj).__name__))}
                try:
                    xy = list(obj._oleobj_.InvokeTypes(
                        obj._oleobj_.GetIDsOfNames("GetCoordinates"), 0,
                        pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
                        ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
                        (0.0, 0.0)))
                    local = [axis[j] + xy[0] * axis[3 + j] + xy[1] * axis[6 + j] for j in range(3)]
                    xa, ya, za, origin = transform[0:3], transform[3:6], transform[6:9], transform[9:12]
                    world = [origin[j] + xa[j] * local[0] + ya[j] * local[1] + za[j] * local[2] for j in range(3)]
                    entry.update(sketch_xy=xy, local_mm=local, world_mm=world, sketch_axis=axis)
                except Exception:
                    pass
                for attrs in (("X", "Y"), ("CenterX", "CenterY"), ("StartPoint", "EndPoint")):
                    try:
                        entry["values"] = {attr: getattr(obj, attr) for attr in attrs}
                        break
                    except Exception:
                        continue
                result["sketch_geometry"].append(entry)
    result["source_saved_by_tool"] = False
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


def _inspect_component_body_points(connection: Any, arguments: dict[str, Any]) -> str:
    """Resolve exact point-like HybridShapes in a named Body, excluding sketch geometry."""
    connection.ensure_connected()
    document = connection.active_document
    root = document.Product
    component_name = str(arguments["component_name"])
    body_name = str(arguments["body_name"])
    point_names = [str(value) for value in arguments.get("point_names", [])]
    matches = [root.Products.Item(i) for i in range(1, root.Products.Count + 1)
               if str(root.Products.Item(i).Name) == component_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one component named '{component_name}', found {len(matches)}")
    component = matches[0]
    source = component.ReferenceProduct.Parent
    part = source.Part
    body = part.Bodies.Item(body_name)
    hybrid_shapes = body.HybridShapes
    import pythoncom
    transform = list(component.Position._oleobj_.InvokeTypes(
        component.Position._oleobj_.GetIDsOfNames("GetComponents"), 0,
        pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
        ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
        tuple(0.0 for _ in range(12))))
    xa, ya, za, origin = transform[0:3], transform[3:6], transform[6:9], transform[9:12]
    spa = source.GetWorkbench("SPAWorkbench")
    records = []
    for index in range(1, hybrid_shapes.Count + 1):
        obj = hybrid_shapes.Item(index)
        name = str(obj.Name)
        if point_names and name not in point_names:
            continue
        entry = {"index": index, "name": name,
                 "type": str(getattr(obj, "Type", type(obj).__name__))}
        properties = {}
        for attr in ("PointType", "Orientation", "Distance", "Ratio", "Offset",
                     "X", "Y", "Z", "Curve", "Surface", "Support", "Direction"):
            try:
                value = getattr(obj, attr)
                if hasattr(value, "DisplayName"):
                    value = str(value.DisplayName)
                elif hasattr(value, "Name"):
                    value = str(value.Name)
                elif not isinstance(value, (str, int, float, bool, type(None))):
                    value = str(value)
                properties[attr] = value
            except Exception:
                continue
        if properties:
            entry["properties"] = properties
        try:
            measurable = spa.GetMeasurable(part.CreateReferenceFromObject(obj))
            local = list(measurable._oleobj_.InvokeTypes(
                measurable._oleobj_.GetIDsOfNames("GetPoint"), 0,
                pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
                ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
                (0.0, 0.0, 0.0)))
            world = [origin[j] + xa[j] * local[0] + ya[j] * local[1] + za[j] * local[2]
                     for j in range(3)]
            entry.update(local_mm=local, world_mm=world)
        except Exception as exc:
            entry["measurement_error"] = str(exc)
        records.append(entry)
    return json.dumps({"component": component_name, "document": str(source.Name),
                       "body": body_name, "hybrid_shape_count": int(hybrid_shapes.Count),
                       "records": records, "source_saved_by_tool": False},
                      ensure_ascii=False, indent=2)


def _inspect_component_surface_point_normals(connection: Any, arguments: dict[str, Any]) -> str:
    """Resolve exact Body point identities and fit local normals from CATIA tessellation."""
    connection.ensure_connected()
    assembly = connection.active_document
    if not str(assembly.Name).lower().endswith(".catproduct"):
        raise RuntimeError("Active document is not a CATProduct")
    component_name = str(arguments["component_name"])
    body_name = str(arguments["body_name"])
    point_names = [str(value) for value in arguments["point_names"]]
    point_facts = json.loads(_inspect_component_body_points(connection, {
        "component_name": component_name,
        "body_name": body_name,
        "point_names": point_names,
    }))
    from catia_mcp.arrangement_geometry import component_mesh, closest_point_triangle
    import math
    root = assembly.Product
    vertices, triangles, _ = component_mesh(
        connection.app, assembly, root, component_name
    )

    def subtract(a, b):
        return [a[i] - b[i] for i in range(3)]

    def cross(a, b):
        return [a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0]]

    records = []
    for record in point_facts["records"]:
        point = [float(value) for value in record["world_mm"]]
        best = None
        for ia, ib, ic in triangles:
            a, b, c = vertices[ia], vertices[ib], vertices[ic]
            closest = closest_point_triangle(tuple(point), a, b, c)
            distance = math.sqrt(sum((point[i] - closest[i]) ** 2 for i in range(3)))
            if best is None or distance < best[0]:
                raw = cross(subtract(b, a), subtract(c, a))
                length = math.sqrt(sum(value * value for value in raw))
                if length > 1e-12:
                    best = (distance, closest, [value / length for value in raw])
        if best is None:
            raise RuntimeError(f"No non-degenerate mesh triangle near {record['name']}")
        records.append({
            "index": record["index"], "name": record["name"],
            "world_mm": point,
            "surface": record.get("properties", {}).get("Surface"),
            "nearest_mesh_point_mm": [round(float(value), 9) for value in best[1]],
            "point_to_mesh_distance_mm": round(float(best[0]), 9),
            "normal_pair_world": [
                [round(float(value), 9) for value in best[2]],
                [round(float(-value), 9) for value in best[2]],
            ],
            "normal_orientation_resolved": False,
        })
    assembly.Activate()
    return json.dumps({
        "schema_version": "catia.surface-point-normals.v1.0",
        "component": component_name, "body": body_name,
        "records": records, "mesh_vertices": len(vertices),
        "mesh_triangles": len(triangles),
        "method": "EXACT_BODY_POINT_PLUS_NEAREST_CATIA_TESSELLATION_TRIANGLE",
        "source_saved_by_tool": False,
    }, ensure_ascii=False, indent=2)


def _derive_component_point_surface_normals(connection: Any, arguments: dict[str, Any]) -> str:
    """Measure exact point-support normals with transactionally removed GSD lines."""
    connection.ensure_connected()
    assembly = connection.active_document
    root = assembly.Product
    component_name = str(arguments["component_name"])
    body_name = str(arguments["body_name"])
    names = [str(value) for value in arguments["point_names"]]
    matches = [root.Products.Item(i) for i in range(1, root.Products.Count + 1)
               if str(root.Products.Item(i).Name) == component_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one component named '{component_name}', found {len(matches)}")
    component = matches[0]
    source_doc = component.ReferenceProduct.Parent
    source_part = source_doc.Part
    body = source_part.Bodies.Item(body_name)
    shapes = body.HybridShapes
    points = {}
    point_indices = {}
    for index in range(1, shapes.Count + 1):
        obj = shapes.Item(index)
        if str(obj.Name) in names:
            points[str(obj.Name)] = obj
            point_indices[str(obj.Name)] = index
    if set(points) != set(names):
        raise ValueError(f"Exact Body points unresolved: {sorted(set(names) - set(points))}")
    import pythoncom, math
    transform = list(component.Position._oleobj_.InvokeTypes(
        component.Position._oleobj_.GetIDsOfNames("GetComponents"), 0,
        pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
        ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
        tuple(0.0 for _ in range(12))))
    xa, ya, za = transform[0:3], transform[3:6], transform[6:9]
    records = []
    transient_lines = []
    try:
        source_doc.Activate()
        factory = source_part.HybridShapeFactory
        for name in names:
            point = points[name]
            support_ref = point.Surface
            support_name = str(getattr(support_ref, "DisplayName", ""))
            point_ref = source_part.CreateReferenceFromObject(point)
            line = factory.AddNewLineNormal(support_ref, point_ref, 0.0, 10.0, False)
            line.Name = f"__MCP_TRANSIENT_NORMAL_{name}"
            body.InsertHybridShape(line)
            transient_lines.append(line)
            source_part.Update()
            measurable = source_doc.GetWorkbench("SPAWorkbench").GetMeasurable(
                source_part.CreateReferenceFromObject(line))
            local = list(measurable._oleobj_.InvokeTypes(
                measurable._oleobj_.GetIDsOfNames("GetDirection"), 0,
                pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
                ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
                (0.0, 0.0, 0.0)))
            world = [xa[j] * local[0] + ya[j] * local[1] + za[j] * local[2] for j in range(3)]
            length = math.sqrt(sum(value * value for value in world))
            world = [value / length for value in world]
            records.append({"name": name, "normal_world_unit": world,
                            "opposite_world_unit": [-value for value in world],
                            "surface": support_name,
                            "source_point_index": point_indices[name]})
    finally:
        if transient_lines or int(body.HybridShapes.Count) > 0:
            try:
                source_doc.Activate()
                # Delete by datum reference, not Selection.Delete: CATIA may
                # silently retain hybrid shapes filtered out of the CSO.
                doomed = []
                current_shapes = body.HybridShapes
                for index in range(1, current_shapes.Count + 1):
                    candidate = current_shapes.Item(index)
                    if str(candidate.Name).startswith("__MCP_TRANSIENT_NORMAL_"):
                        doomed.append(candidate)
                for candidate in reversed(doomed):
                    factory.DeleteObjectForDatum(
                        source_part.CreateReferenceFromObject(candidate))
                source_part.Update()
            except Exception:
                pass
        assembly.Activate()
    return json.dumps({"component": component_name, "body": body_name,
                       "records": records, "method": "TRANSIENT_SOURCE_GSD_LINE_NORMAL",
                       "source_modified": False, "source_saved_by_tool": False},
                      ensure_ascii=False, indent=2)


def _inspect_component_vertex_bounds(connection: Any, arguments: dict[str, Any]) -> str:
    """Read exact topological vertex coordinates of a referenced component without edits."""
    connection.ensure_connected()
    assembly = connection.active_document
    root = assembly.Product
    component_name = str(arguments["component_name"])
    matches = [root.Products.Item(i) for i in range(1, root.Products.Count + 1)
               if str(root.Products.Item(i).Name) == component_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one component named '{component_name}', found {len(matches)}")
    component = matches[0]
    source = component.ReferenceProduct.Parent
    part = source.Part
    import pythoncom
    transform = list(component.Position._oleobj_.InvokeTypes(
        component.Position._oleobj_.GetIDsOfNames("GetComponents"), 0,
        pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
        ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
        tuple(0.0 for _ in range(12))))
    xa, ya, za, origin = transform[0:3], transform[3:6], transform[6:9], transform[9:12]
    points = []
    selection = assembly.Selection
    try:
        assembly.Activate()
        selection.Clear()
        selection.Search("Topology.Vertex,all")
        spa = assembly.GetWorkbench("SPAWorkbench")
        for index in range(1, selection.Count2 + 1):
            item = selection.Item2(index)
            try:
                leaf = item.LeafProduct
                if str(getattr(leaf, "Name", "")) != component_name:
                    continue
                measurable = spa.GetMeasurableInContext(item.Reference, component)
                world = list(measurable._oleobj_.InvokeTypes(
                    measurable._oleobj_.GetIDsOfNames("GetPoint"), 0,
                    pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
                    ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
                    (0.0, 0.0, 0.0)))
                points.append(world)
            except Exception:
                continue
    finally:
        try:
            selection.Clear()
        except Exception:
            pass
        assembly.Activate()
    bounds = None
    if points:
        bounds = {"min": [min(p[i] for p in points) for i in range(3)],
                  "max": [max(p[i] for p in points) for i in range(3)]}
    return json.dumps({"component": component_name, "document": str(source.Name),
                       "vertex_count": len(points), "vertex_bounds_world_mm": bounds,
                       "source_saved_by_tool": False}, ensure_ascii=False, indent=2)


def _measure_body_points_to_components(connection: Any, arguments: dict[str, Any]) -> str:
    """Measure exact endpoint-to-solid distances using explicit Body.HybridShapes identities."""
    connection.ensure_connected()
    assembly = connection.active_document
    import pythoncom
    root = assembly.Product
    source_name = str(arguments["source_component"])
    body_name = str(arguments["body_name"])
    point_indices = [int(value) for value in arguments["point_indices"]]
    target_names = [str(value) for value in arguments["target_components"]]
    products = {str(root.Products.Item(i).Name): root.Products.Item(i)
                for i in range(1, root.Products.Count + 1)}
    if source_name not in products:
        raise ValueError(f"Source component '{source_name}' not found")
    source_component = products[source_name]
    source_part = source_component.ReferenceProduct.Parent.Part
    body = source_part.Bodies.Item(body_name)
    spa = assembly.GetWorkbench("SPAWorkbench")
    result = []
    for point_index in point_indices:
        point = body.HybridShapes.Item(point_index)
        point_ref = source_part.CreateReferenceFromObject(point)
        measurable = spa.GetMeasurableInContext(point_ref, source_component)
        distances = {}
        for target_name in target_names:
            target = products.get(target_name)
            if target is None:
                distances[target_name] = {"error": "component not found"}
                continue
            target_part = target.ReferenceProduct.Parent.Part
            target_ref = target_part.CreateReferenceFromObject(target_part.MainBody)
            try:
                value = float(measurable.GetMinimumDistanceInContext(target_ref, target))
                detail = {"distance_mm": value}
                try:
                    coords = list(measurable._oleobj_.InvokeTypes(
                        measurable._oleobj_.GetIDsOfNames("GetMinimumDistancePointsInContext"), 0,
                        pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
                        ((pythoncom.VT_DISPATCH, 0), (pythoncom.VT_DISPATCH, 0),
                         (pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3)),
                        target_ref, target, tuple(0.0 for _ in range(9))))
                    detail["minimum_distance_points"] = coords
                except Exception as exc:
                    detail["points_error"] = str(exc)
                distances[target_name] = detail
            except Exception as exc:
                distances[target_name] = {"error": str(exc)}
        result.append({"point_index": point_index, "point_name": str(point.Name),
                       "distances": distances})
    return json.dumps({"source_component": source_name, "body": body_name,
                       "results": result, "source_saved_by_tool": False},
                      ensure_ascii=False, indent=2)


def _export_component_mesh_json(connection: Any, arguments: dict[str, Any]) -> str:
    """Export one referenced CATPart to STL and transform its mesh to assembly space."""
    connection.ensure_connected()
    assembly = connection.active_document
    if not str(assembly.Name).lower().endswith(".catproduct"):
        raise RuntimeError("Active document is not a CATProduct")
    root = assembly.Product
    component_name = str(arguments["component_name"])
    matches = [root.Products.Item(i) for i in range(1, root.Products.Count + 1)
               if str(root.Products.Item(i).Name) == component_name]
    if len(matches) != 1:
        raise ValueError(f"Expected one component named '{component_name}', found {len(matches)}")
    from catia_mcp.arrangement_geometry import component_mesh, mesh_bounds
    vertices, triangles, transform = component_mesh(
        connection.app, assembly, root, component_name)
    world = [[p[0], p[1], p[2]] for p in vertices]
    output = Path(arguments["output_path"]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"component": component_name, "vertices": world,
                                  "triangles": triangles}, separators=(",", ":")), encoding="utf-8")
    return json.dumps({"component": component_name, "output_path": str(output),
                       "vertex_count": len(world), "triangle_count": len(triangles),
                       "bounds_world_mm": mesh_bounds([tuple(v) for v in world]),
                       "source_modified": False}, ensure_ascii=False, indent=2)


def _simulate_arrangement_route(connection: Any, arguments: dict[str, Any]) -> str:
    """Create and clash-check a route only in an unsaved disposable assembly."""
    connection.ensure_connected()
    source_document = connection.active_document
    if not str(source_document.Name).lower().endswith(".catproduct"):
        raise RuntimeError("Active source document is not a CATProduct")
    source_root = source_document.Product
    component_names = [str(v) for v in arguments["component_names"]]
    route_args = dict(arguments["route"])
    simulation = None
    try:
        simulation = connection.app.Documents.Add("Product")
        sim_root = simulation.Product
        for name in component_names:
            matches = [source_root.Products.Item(i) for i in range(1, source_root.Products.Count + 1)
                       if str(source_root.Products.Item(i).Name) == name]
            if len(matches) != 1:
                raise ValueError(f"Expected one source component '{name}', found {len(matches)}")
            source_component = matches[0]
            source_part_document = source_component.ReferenceProduct.Parent
            inserted = sim_root.Products.AddExternalComponent(source_part_document)
            import pythoncom
            transform = list(source_component.Position._oleobj_.InvokeTypes(
                source_component.Position._oleobj_.GetIDsOfNames("GetComponents"), 0,
                pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
                ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
                tuple(0.0 for _ in range(12))))
            inserted.Move.Apply(tuple(transform))
        simulation.Activate()
        import importlib
        from catia_mcp.tools import tubing as tubing_module
        from catia_mcp.tools import measurement as measurement_module
        tubing_module = importlib.reload(tubing_module)
        measurement_module = importlib.reload(measurement_module)
        tubing = tubing_module.TubingTools(connection)
        measurement = measurement_module.MeasurementTools(connection)
        route_data = json.loads(tubing._create_arrangement_run(route_args))
        clashes = {}
        for name in component_names:
            clashes[name] = json.loads(measurement._measure_component_interference(
                route_args["name"], name,
                float(arguments.get("contact_tolerance", 0.01)),
                int(arguments.get("max_reported_intersection_points", 10))))
        return json.dumps({"simulation_only": True, "source_modified": False,
                           "route": route_data, "clashes": clashes},
                          ensure_ascii=False, indent=2)
    finally:
        if simulation is not None:
            try:
                simulation.Close()
            except Exception:
                pass
        try:
            source_document.Activate()
        except Exception:
            pass


def _export_inspection_bodies(connection: Any, arguments: dict[str, Any]) -> str:
    """Explicit one-Body-per-STEP export; only owned disposable parts are closed."""
    connection.ensure_connected()
    document=connection.active_document
    expected_name=arguments['expected_document_name']; expected_count=int(arguments['expected_body_count'])
    indices=[int(i) for i in arguments['body_indices']]
    if not indices or len(indices)>expected_count or len(set(indices))!=len(indices):
        raise ValueError('Requires unique explicit Body indices within the verified source count')
    if str(document.Name)!=expected_name or int(document.Part.Bodies.Count)!=expected_count:
        raise RuntimeError('Active CATPart identity or Body count differs from requested baseline')
    directory=Path(arguments['output_directory']).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError('Inspection output directory must be empty')
    project=Path(__file__).resolve().parents[3]/'project'
    if str(project) not in sys.path: sys.path.insert(0,str(project))
    from catia_checker.catia_body_batches import export_body_batches
    names=[str(document.Part.Bodies.Item(i).Name) for i in range(1,expected_count+1)]
    batch_size=max(1,min(int(arguments.get('batch_size',1)),40))
    audit=export_body_batches(connection.app,document,directory,batch_size=batch_size,body_indices=indices)
    if names!=[str(document.Part.Bodies.Item(i).Name) for i in range(1,expected_count+1)]:
        raise RuntimeError('Source Body names changed during inspection export')
    audit.update(document_name=expected_name,document_path=str(document.FullName),
                 inspection_generation='NEW_IMPORT_BASELINE_NOT_LEGACY_BODY_IDENTITY',saved_by_tool=False)
    (directory/'export_audit.json').write_text(json.dumps(audit,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
    return json.dumps({'status':'ok','exported_body_count':len(indices),'source_modified':False,
                       'audit_file':str(directory/'export_audit.json')},ensure_ascii=False)


def _select_inspection_bodies(connection: Any, arguments: dict[str, Any]) -> str:
    connection.ensure_connected(); document=connection.active_document
    if str(document.Name)!=arguments['expected_document_name']:
        raise RuntimeError('Active document differs from verified baseline')
    records=arguments['body_records']; resolved=[]
    if not 1<=len(records)<=20: raise ValueError('Requires 1 to 20 explicit Body records')
    for record in records:
        body=document.Part.Bodies.Item(int(record['index']))
        if str(body.Name)!=record['name']: raise RuntimeError('Exact Body identity check failed')
        resolved.append(body)
    selection=document.Selection; selection.Clear()
    for body in resolved: selection.Add(body)
    return json.dumps({'selected_body_count':int(selection.Count2),'body_indices':[r['index'] for r in records],
                       'geometry_modified':False},ensure_ascii=False)


def _isolate_inspection_bodies(connection: Any, arguments: dict[str, Any]) -> str:
    connection.ensure_connected(); document=connection.active_document
    if str(document.Name)!=arguments['expected_document_name']:
        raise RuntimeError('Active document differs from verified baseline')
    part=document.Part; records=arguments['body_records']; targets={int(r['index']):r['name'] for r in records}
    if not 1<=len(targets)<=20 or int(part.Bodies.Count)!=int(arguments['expected_body_count']):
        raise ValueError('Body selection or source count is invalid')
    for index,name in targets.items():
        if str(part.Bodies.Item(index).Name)!=name: raise RuntimeError('Exact Body identity check failed')
    selection=document.Selection; selection.Clear()
    for index in range(1,part.Bodies.Count+1):
        if index not in targets: selection.Add(part.Bodies.Item(index))
    hidden_count=int(selection.Count2); selection.VisProperties.SetShow(1); selection.Clear()
    for index in targets: selection.Add(part.Bodies.Item(index))
    selection.VisProperties.SetShow(0)
    return json.dumps({'visible_selected_body_count':int(selection.Count2),'hidden_body_count':hidden_count,
                       'body_indices':list(targets),'geometry_modified':False,'visibility_modified':True},ensure_ascii=False)


def _show_all_inspection_bodies(connection: Any, arguments: dict[str, Any]) -> str:
    """Show every Body with one VisProperties operation for a full neutral export."""
    connection.ensure_connected(); document=connection.active_document
    if str(document.Name)!=arguments['expected_document_name']:
        raise RuntimeError('Active document differs from verified baseline')
    part=document.Part; count=int(part.Bodies.Count)
    if count!=int(arguments['expected_body_count']):
        raise RuntimeError('Body count differs from verified baseline')
    selection=document.Selection; selection.Clear()
    for index in range(1,count+1):
        body=part.Bodies.Item(index); selection.Add(body)
        try:
            for shape_index in range(1,int(body.Shapes.Count)+1): selection.Add(body.Shapes.Item(shape_index))
        except Exception:
            pass
    selected=int(selection.Count2); selection.VisProperties.SetShow(0); selection.Clear()
    return json.dumps({'shown_body_count':selected,'geometry_modified':False,
        'visibility_modified':True,'saved_by_tool':False},ensure_ascii=False)


def _rename_inspection_bodies(connection: Any, arguments: dict[str, Any]) -> str:
    """Assign deterministic unique names to all Bodies and semantic names to a selected subset."""
    connection.ensure_connected(); document=connection.active_document
    if str(document.Name)!=arguments['expected_document_name']:
        raise RuntimeError('Active document differs from verified baseline')
    part=document.Part; count=int(part.Bodies.Count)
    if count!=int(arguments['expected_body_count']):
        raise RuntimeError('Body count differs from verified baseline')
    selected={int(item['index']):str(item['label']).strip().upper() for item in arguments.get('selected_labels',[])}
    if any(not 1<=index<=count or not label for index,label in selected.items()):
        raise ValueError('Invalid selected Body label mapping')
    before=[]; mapping=[]
    for index in range(1,count+1):
        body=part.Bodies.Item(index); old=str(body.Name); before.append(old)
        label=selected.get(index,'UNCLASSIFIED')
        new=f'STP_BODY_{index:06d}__{label}'
        body.Name=new
        try:
            if int(body.Shapes.Count)==1: body.Shapes.Item(1).Name=new
        except Exception:
            pass
        mapping.append({'index':index,'original_name':old,'stp_name':new,'selected_for_report':index in selected})
    actual=[str(part.Bodies.Item(i).Name) for i in range(1,count+1)]
    if len(set(actual))!=count or any(actual[i-1]!=mapping[i-1]['stp_name'] for i in range(1,count+1)):
        raise RuntimeError('Unique Body rename verification failed')
    output=Path(arguments['mapping_output']).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'document_name':str(document.Name),'body_count':count,
        'geometry_modified':False,'metadata_modified':True,'saved_by_tool':False,'mapping':mapping},
        ensure_ascii=False,indent=2),encoding='utf-8')
    return json.dumps({'renamed_body_count':count,'selected_semantic_name_count':len(selected),
        'geometry_modified':False,'metadata_modified':True,'saved_by_tool':False,
        'mapping_output':str(output)},ensure_ascii=False)


def _restore_distinguishable_body_names(connection: Any, arguments: dict[str, Any]) -> str:
    """Restore original distinguishable names; suffix only exact duplicates."""
    connection.ensure_connected(); document=connection.active_document
    if str(document.Name)!=arguments['expected_document_name']:
        raise RuntimeError('Active document differs from verified baseline')
    part=document.Part; count=int(part.Bodies.Count)
    if count!=int(arguments['expected_body_count']): raise RuntimeError('Body count differs from verified baseline')
    source=Path(arguments['previous_mapping']).resolve(); payload=json.loads(source.read_text(encoding='utf-8'))
    rows=payload['mapping']
    if len(rows)!=count: raise RuntimeError('Previous mapping does not cover all Bodies')
    originals=[str(row['original_name']) for row in rows]
    counts={name:originals.count(name) for name in set(originals)}
    result=[]; used=set()
    for row in rows:
        index=int(row['index']); body=part.Bodies.Item(index)
        if str(body.Name)!=str(row['stp_name']): raise RuntimeError(f'Current Body {index} differs from rename audit')
        original=str(row['original_name']); final=original if counts[original]==1 else f'{original}__BODY_{index:06d}'
        if final in used: raise RuntimeError('Final Body names are not unique')
        used.add(final); body.Name=final
        try:
            if int(body.Shapes.Count)==1: body.Shapes.Item(1).Name=final
        except Exception: pass
        result.append({'index':index,'original_name':original,'final_stp_name':final,
            'renamed_because_duplicate':counts[original]>1,'selected_for_report':bool(row.get('selected_for_report'))})
    actual=[str(part.Bodies.Item(i).Name) for i in range(1,count+1)]
    if actual!=[row['final_stp_name'] for row in result]: raise RuntimeError('Restored name verification failed')
    output=Path(arguments['mapping_output']).resolve();output.write_text(json.dumps({
        'document_name':str(document.Name),'body_count':count,'preserved_original_name_count':sum(not x['renamed_because_duplicate'] for x in result),
        'duplicate_name_body_count':sum(x['renamed_because_duplicate'] for x in result),'geometry_modified':False,
        'metadata_modified':True,'mapping':result},ensure_ascii=False,indent=2),encoding='utf-8')
    return json.dumps({'body_count':count,'preserved_original_name_count':sum(not x['renamed_because_duplicate'] for x in result),
        'duplicate_name_body_count':sum(x['renamed_because_duplicate'] for x in result),'geometry_modified':False,
        'metadata_modified':True,'mapping_output':str(output)},ensure_ascii=False)


def _document_record(document: Any) -> dict[str, Any]:
    record = {"name": str(document.Name), "path": str(getattr(document, "FullName", "") or "")}
    try:
        part = document.Part
        record.update(type="CATPart", body_count=int(part.Bodies.Count),
                      bodies=[str(part.Bodies.Item(i).Name) for i in range(1, part.Bodies.Count + 1)])
    except Exception:
        try:
            product = document.Product
            record.update(type="CATProduct", component_count=int(product.Products.Count))
        except Exception:
            record["type"] = "Other"
    return record


def _import_neutral_for_inspection(connection: Any, arguments: dict[str, Any]) -> str:
    """Resolve the native CATPart or CATProduct created by CATIA's neutral translator."""
    source = os.path.abspath(os.fspath(arguments.get("source_file", "")))
    timeout_s = max(5.0, min(float(arguments.get("timeout_s", 90.0)), 600.0))
    activate = bool(arguments.get("activate", True))
    if not os.path.isfile(source):
        raise FileNotFoundError(source)
    if os.path.splitext(source)[1].lower() not in {".stp", ".step", ".igs", ".iges"}:
        raise ValueError("source_file must be STEP/STP/IGES/IGS")
    connection.ensure_connected()
    app, documents = connection.app, connection.app.Documents
    original = app.ActiveDocument
    original_record = _document_record(original)
    before = {str(documents.Item(i).Name) for i in range(1, documents.Count + 1)}
    with open(source, "rb") as stream:
        source_sha256 = hashlib.sha256(stream.read()).hexdigest()
    documents.Open(source)
    deadline, imported, observed = time.monotonic() + timeout_s, None, []
    while time.monotonic() < deadline:
        observed = []
        for index in range(1, documents.Count + 1):
            document = documents.Item(index)
            record = _document_record(document)
            observed.append(record)
            if record["name"] not in before and record["type"] in {"CATPart", "CATProduct"}:
                if imported is None or record["type"] == "CATProduct":
                    imported = document
        if imported is not None:
            break
        time.sleep(0.25)
    if imported is None:
        try:
            original.Activate()
        except Exception:
            pass
        raise RuntimeError("CATIA neutral import did not create a native CATPart/CATProduct before timeout; "
                           + json.dumps(observed, ensure_ascii=False))
    (imported if activate else original).Activate()
    if activate and app.ActiveDocument.Name != imported.Name:
        raise RuntimeError("Imported neutral document activation verification failed")
    imported_record = _document_record(imported)
    imported_record.update(source_file=source, source_sha256=source_sha256,
                           temporary=True, saved_by_tool=False)
    return json.dumps({"status": "ok", "method": "CATIA_NATIVE_NEUTRAL_TRANSLATOR",
                       "imported": imported_record, "original_active_document": original_record,
                       "restore_document_name": original_record["name"]}, ensure_ascii=False, indent=2)
