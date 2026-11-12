"""Reproducible mesh-space plan for Part3.1 点.1 to 点.2."""

from __future__ import annotations

import json
import argparse
from pathlib import Path

from catia_checker.spatial_route_planning import (
    MeshFreeSpacePlanner, SpatialRouteRequest, SurfacePort, TriangleMesh,
)
from catia_checker.route_manufacturability import validate_polyline_route
from catia_checker.route_design_constraints import load_route_design_cases


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "project" / "artifacts"


def load_mesh(filename: str) -> TriangleMesh:
    data = json.loads((ARTIFACTS / filename).read_text(encoding="utf-8"))
    return TriangleMesh(
        data["component"],
        tuple(tuple(map(float, point)) for point in data["vertices"]),
        tuple(tuple(map(int, triangle)) for triangle in data["triangles"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design-config", default=str(
        ROOT / "project" / "config" / "route-design-current.json"))
    parser.add_argument("--case-index", type=int)
    parser.add_argument("--grid", type=float)
    parser.add_argument("--diameter", type=float)
    parser.add_argument("--clearance", type=float)
    parser.add_argument("--bend-radius", type=float)
    parser.add_argument("--minimum-straight", type=float)
    parser.add_argument("--candidates", type=int)
    parser.add_argument("--lead", type=float)
    args = parser.parse_args()
    design, design_cases = load_route_design_cases(args.design_config)
    if args.case_index is None and not (args.diameter is not None and args.bend_radius is not None):
        raise ValueError(
            "Configuration contains a design space; select --case-index or supply both "
            "--diameter and --bend-radius. No D/R pair is chosen implicitly."
        )
    case_index = 0 if args.case_index is None else args.case_index
    if not 0 <= case_index < len(design_cases):
        raise ValueError(f"case-index must be between 0 and {len(design_cases)-1}")
    case = design_cases[case_index]
    search = design.get("search", {})
    grid = args.grid if args.grid is not None else float(search["grid_size_mm"])
    diameter = args.diameter if args.diameter is not None else case.diameter_mm
    clearance = args.clearance if args.clearance is not None else case.clearance_mm
    bend_radius = (args.bend_radius if args.bend_radius is not None
                   else case.bend_radius_mm)
    minimum_straight = (args.minimum_straight if args.minimum_straight is not None
                        else case.minimum_straight_mm)
    candidates = (args.candidates if args.candidates is not None
                  else int(search["candidate_count"]))
    lead = args.lead if args.lead is not None else float(search["port_lead_length_mm"])
    request = SpatialRouteRequest(
        boundary_mesh=load_mesh("part2_spatial_mesh_20260922.json"),
        obstacle_meshes=tuple(load_mesh(name) for name in (
            "Part1_1_spatial_mesh_20260922.json",
            "Part3_1_spatial_mesh_20260922.json",
            "Part4_1_spatial_mesh_20260922.json",
            "Part5_1_spatial_mesh_20260922.json",
        )),
        start=SurfacePort(
            (-67.49342966262095, 93.66743457406419, 31.83392281312019),
            (-0.6008805778851174, 0.7474093186836599, 0.2834110821144346),
            lead,
        ),
        goal=SurfacePort(
            (-27.314870296099286, -201.16516176810325, 16.139489659952446),
            (-0.8107850962850802, -0.3363363969981572, 0.47906717242605046),
            lead,
        ),
        grid_size_mm=grid,
        pipe_outer_diameter_mm=diameter,
        clearance_mm=clearance,
        bend_penalty_mm=32.0,
        bend_radius_mm=bend_radius,
        minimum_straight_mm=minimum_straight,
        candidate_count=candidates,
        max_expanded_cells=int(search.get("max_expanded_cells", 400000)),
    )
    result = MeshFreeSpacePlanner().plan(request)
    bend_check = (validate_polyline_route(
        result.points, (bend_radius,), minimum_straight
    ) if result.status == "OK" else None)
    payload = {
        "schema_version": "2.0.0",
        "method": "TRIANGLE_MESH_FREE_SPACE_ASTAR",
        "design_config": str(Path(args.design_config).resolve()),
        "design_case_index": (None if args.case_index is None else case_index),
        "available_design_cases": [{
            "diameter_mm": item.diameter_mm,
            "bend_radius_mm": item.bend_radius_mm,
            "standard_id": item.standard_id,
            "standard_policy": item.standard_policy,
            "preferred_radius": item.preferred_radius,
        } for item in design_cases],
        "source_points": ["Part3.1/零件几何体/点.1", "Part3.1/零件几何体/点.2"],
        "boundary": "Part2.1 triangle mesh",
        "obstacles": [mesh.name for mesh in request.obstacle_meshes],
        "grid_size_mm": request.grid_size_mm,
        "pipe_outer_diameter_mm": request.pipe_outer_diameter_mm,
        "clearance_mm": request.clearance_mm,
        "bend_radius_mm": request.bend_radius_mm,
        "minimum_straight_mm": request.minimum_straight_mm,
        "status": result.status,
        "message": result.message,
        "points_mm": [list(point) for point in result.points],
        "start_normal_sign": result.start_normal_sign,
        "goal_normal_sign": result.goal_normal_sign,
        "expanded_cells": result.expanded_cells,
        "blocked_cells": result.blocked_cells,
        "objective_score": result.objective_score,
        "candidate_count": result.candidate_count,
        "candidate_scores": list(result.candidate_scores),
        "alternatives_mm": [[list(point) for point in route] for route in result.alternatives],
        "non_orthogonal_bends": ([] if bend_check is None else [{
            "node_index": bend.node_index,
            "angle_deg": bend.angle_deg,
            "radius_mm": bend.radius_mm,
            "tangent_start_mm": list(bend.tangent_start),
            "tangent_end_mm": list(bend.tangent_end),
            "center_mm": list(bend.center),
            "axis": list(bend.axis),
        } for bend in bend_check.bends]),
        "catia_mutation": "NONE",
    }
    output = ARTIFACTS / "part3_points_mesh_route_candidate_20260922.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
