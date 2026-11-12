"""Merged CATIA engineering MCP entrypoint; stdio transport.

The default ``full`` mode exposes modeling, assembly, tubing and inspection
tools. Set ``CATIA_AGENT_MODE=inspection`` for the legacy read-only allowlist.
"""
import asyncio
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'validation').mkdir(exist_ok=True)
os.chdir(ROOT/'validation')
import catia_mcp.server as upstream
from r18_connection import V5Connection
INSPECTION_ALLOWED={
 'catia_check_assembly','catia_prepare_clearance_investigation','catia_finalize_clearance_investigation',
 'catia_connect','catia_disconnect','catia_list_documents','catia_get_active_document_info',
 'catia_list_components','catia_list_constraints','catia_get_model_manifest',
 'catia_list_bodies_detailed','catia_list_sketches','catia_get_sketch_details',
 'catia_get_feature_details','catia_get_selection','catia_select_elements','catia_get_parameters',
 'catia_scan_product_clashes','catia_get_body_geometry_batch','catia_screenshot','catia_set_view','catia_fit_all'
 ,'catia_measure_distance','catia_measure_product_distance','catia_measure_route_to_component','catia_measure_component_interference'
 ,'catia_measure_face_distance','catia_measure_surface_id_distance','catia_extract_exact_faces','catia_get_part_geometry_inventory'
 ,'catia_dev_dispatch'
 ,'catia_tubing_get_capabilities','catia_tubing_list_native_objects','catia_tubing_list_logical_lines'
 ,'catia_tubing_inspect_route','catia_tubing_get_attributes','catia_tubing_inspect_physical_tube'
}
ALLOWED=set(INSPECTION_ALLOWED)
def make_server():
    upstream.CATIAConnection=V5Connection
    server=upstream.CATIAMCPServer()
    from check_tool import CheckTool
    from route_planning_tool import RoutePlanningTool
    checker=CheckTool(server.measurement_tools, server.tubing_tools)
    planner=RoutePlanningTool(server.connection)
    from spatial_tool import SpatialTool
    spatial=SpatialTool()
    server._tool_modules.append(spatial)
    for definition in spatial.get_tool_definitions():server._tool_router[definition["name"]]=spatial
    server._tool_modules.append(checker)
    server._tool_modules.append(planner)
    server._tool_router["catia_check_assembly"]=checker
    server._tool_router["catia_prepare_clearance_investigation"]=checker
    server._tool_router["catia_finalize_clearance_investigation"]=checker
    server._tool_router["catia_plan_orthogonal_route"]=planner
    server._tool_router["catia_plan_route_in_active_product"]=planner
    server._tool_router["catia_route_issue_preflight_token"]=planner
    mode=os.environ.get('CATIA_AGENT_MODE','full').strip().lower()
    if mode=='inspection':
        enabled=set(INSPECTION_ALLOWED)|{'catia_open_spatial_inspection_ui','catia_get_spatial_inspection_result'}
        for module in server._tool_modules:
            definitions=[d for d in module.get_tool_definitions() if d['name'] in enabled]
            module.get_tool_definitions=lambda definitions=definitions: definitions
        server._tool_router={k:v for k,v in server._tool_router.items() if k in enabled}
    elif mode!='full':
        raise ValueError("CATIA_AGENT_MODE must be 'full' or 'inspection'")
    ALLOWED.clear()
    ALLOWED.update(server._tool_router)
    return server
if __name__=='__main__':
    asyncio.run(make_server().run())
