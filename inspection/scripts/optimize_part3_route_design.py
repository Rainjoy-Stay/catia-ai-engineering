"""Optimize configurable D/path/per-bend-R design space without CATIA mutation."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from catia_checker.route_design_constraints import load_route_design_cases
from catia_checker.route_design_optimizer import optimize_route_design_space
from catia_checker.spatial_route_planning import (
    SpatialRouteRequest, SurfacePort, TriangleMesh,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "project" / "artifacts"


def load_mesh(filename: str) -> TriangleMesh:
    data = json.loads((ARTIFACTS / filename).read_text(encoding="utf-8"))
    return TriangleMesh(
        data["component"], tuple(tuple(map(float, p)) for p in data["vertices"]),
        tuple(tuple(map(int, t)) for t in data["triangles"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design-config", default=str(
        ROOT / "project" / "config" / "route-design-current.json"))
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()
    config, cases = load_route_design_cases(args.design_config)
    search = config["search"]
    lead = float(search["port_lead_length_mm"])
    first = cases[0]
    request = SpatialRouteRequest(
        boundary_mesh=load_mesh("part2_spatial_mesh_20260922.json"),
        obstacle_meshes=tuple(load_mesh(name) for name in (
            "Part1_1_spatial_mesh_20260922.json", "Part3_1_spatial_mesh_20260922.json",
            "Part4_1_spatial_mesh_20260922.json", "Part5_1_spatial_mesh_20260922.json",
        )),
        start=SurfacePort(
            (-67.49342966262095, 93.66743457406419, 31.83392281312019),
            (-0.6008805778851174, 0.7474093186836599, 0.2834110821144346), lead),
        goal=SurfacePort(
            (-27.314870296099286, -201.16516176810325, 16.139489659952446),
            (-0.8107850962850802, -0.3363363969981572, 0.47906717242605046), lead),
        grid_size_mm=float(search["grid_size_mm"]),
        pipe_outer_diameter_mm=first.diameter_mm,
        clearance_mm=first.clearance_mm,
        bend_radius_mm=min(case.bend_radius_mm for case in cases
                           if case.diameter_mm == first.diameter_mm),
        minimum_straight_mm=first.minimum_straight_mm,
        candidate_count=int(search["candidate_count"]),
        max_expanded_cells=int(search["max_expanded_cells"]),
    )
    result = optimize_route_design_space(request, cases)
    payload = {
        "schema_version": "route-design-optimization.v1.0",
        "status": result.status,
        "message": result.message,
        "design_config": str(Path(args.design_config).resolve()),
        "catia_mutation": "NONE",
        "best_by_diameter": [_route_payload(item) for item in result.best_by_diameter],
        "ranked_top": [_route_payload(item) for item in result.ranked[:args.top]],
    }
    output = ARTIFACTS / "part3_route_design_optimization_20260922.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _route_payload(route) -> dict[str, object]:
    return {
        "diameter_mm": route.diameter_mm,
        "points_mm": [list(point) for point in route.points],
        "bend_radii_mm": list(route.bend_radii_mm),
        "bends": [asdict(bend) for bend in route.bends],
        "path_score": route.path_score,
        "standard_id": route.standard_id,
        "standard_policy": route.standard_policy,
    }


if __name__ == "__main__":
    main()
