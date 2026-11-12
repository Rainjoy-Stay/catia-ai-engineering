from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "project"))

from catia_checker.brep_route_validation import (  # noqa: E402
    BoundaryRoutePolicy, ComponentRoutePolicy,
    SeparateBRepRouteValidationRequest, validate_separate_route_brep,
)
from catia_checker.permitted_volume import (  # noqa: E402
    AxialSection, build_axisymmetric_permitted_volume,
)
from catia_checker.route_brep_envelope import build_route_envelope_step  # noqa: E402
from catia_checker.route_design_constraints import RouteDesignCase  # noqa: E402
from catia_checker.route_design_optimizer import optimize_route_design_space  # noqa: E402
from catia_checker.spatial_route_planning import (  # noqa: E402
    SpatialRouteRequest, SurfacePort, TriangleMesh,
)


def _mesh(path: Path) -> TriangleMesh:
    data = json.loads(path.read_text(encoding="utf-8"))
    return TriangleMesh(
        str(data.get("component", path.name)),
        tuple(tuple(map(float, point)) for point in data["vertices"]),
        tuple(tuple(map(int, triangle)) for triangle in data["triangles"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument(
        "--objective", choices=("max-diameter", "shortest-d6"),
        default="max-diameter")
    parser.add_argument("--grid-size-mm", type=float, default=6.0)
    parser.add_argument("--max-expanded-cells", type=int, default=400_000)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "project" / "artifacts" / "part2_cavity_optimization_latest")
    args = parser.parse_args()
    source = args.source_artifacts.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    cavity = build_axisymmetric_permitted_volume((
        AxialSection(-262.0, -220.0, 60.0, 60.0),
        AxialSection(-220.0, -60.0, 60.0, 110.0),
        AxialSection(-60.0, 160.0, 110.0, 110.0),
    ), output / "Part2_1_inner_cavity_closed.stp",
       output / "Part2_1_inner_cavity_closed_mesh.json")

    diameters = ((6.0,) if args.objective == "shortest-d6"
                 else (14.0, 12.0, 10.0, 8.0, 6.0, 4.0))
    cases = tuple(RouteDesignCase(
        diameter_mm=value, bend_radius_mm=2.5*value, clearance_mm=0.0,
        minimum_straight_mm=0.0, standard_id=None,
        standard_policy="USER_REQUIREMENT", preferred_radius=True,
    ) for value in diameters)
    request = SpatialRouteRequest(
        boundary_mesh=_mesh(Path(cavity["mesh_file"])),
        boundary_is_closed_permitted_volume=True,
        obstacle_meshes=tuple(_mesh(source/name) for name in (
            "Part1_1_spatial_mesh_20260922.json",
            "Part3_1_spatial_mesh_20260922.json",
            "Part4_1_spatial_mesh_20260922.json",
            "Part5_1_spatial_mesh_20260922.json",
        )),
        start=SurfacePort(
            (-67.49342966262095, 93.66743457406419, 31.83392281312019),
            (-0.6008805778851174, 0.7474093186836599, 0.2834110821144346), 24.0),
        goal=SurfacePort(
            (-27.314870296099286, -201.16516176810325, 16.139489659952446),
            (-0.8107850962850802, -0.3363363969981572, 0.47906717242605046), 24.0),
        grid_size_mm=args.grid_size_mm,
        pipe_outer_diameter_mm=diameters[-1], clearance_mm=0.0,
        bend_radius_mm=2.5*diameters[-1], minimum_straight_mm=0.0,
        bend_penalty_mm=0.0 if args.objective == "shortest-d6" else 20.0,
        candidate_count=1 if args.objective == "shortest-d6" else 3,
        max_expanded_cells=args.max_expanded_cells,
    )
    optimized = optimize_route_design_space(
        request, cases, diameter_selection_policy="MAXIMIZE_DIAMETER")
    environment = source / "MiniEngine_route_brep_validation_20260922.stp"
    component_shapes = {
        "Part1.1": ("STEP_SOLID_0001",),
        "Part2.1": ("STEP_SOLID_0002",),
        "Part4.1": ("STEP_SOLID_0003", "STEP_SOLID_0004"),
        "Part3.1": ("STEP_SOLID_0005", "STEP_SOLID_0006", "STEP_SOLID_0007"),
        "Part5.1": ("STEP_SOLID_0008",),
    }
    policies = {name: ComponentRoutePolicy("CLEARANCE", 0.0)
                for name in component_shapes}
    policies["Part1.1"] = ComponentRoutePolicy("ALLOW_CONTACT", 0.0)
    candidates = []
    for rank, route in enumerate(
            sorted(optimized.best_by_diameter, key=lambda item: -item.diameter_mm), 1):
        route_step = output / f"route_D{route.diameter_mm:g}_R{2.5*route.diameter_mm:g}.stp"
        envelope = build_route_envelope_step(
            route.points, route.bend_radii_mm, route.diameter_mm, route_step, 0.0)
        validation = validate_separate_route_brep(SeparateBRepRouteValidationRequest(
            route_step, environment, "STEP_SOLID_0001", component_shapes,
            component_policies=policies,
            boundary_policy=BoundaryRoutePolicy(
                "Part2.1", "PERMITTED_VOLUME", 0.999999),
            permitted_volume_step_file=cavity["step_file"],
        ))
        candidates.append({
            "rank": rank, "diameter_mm": route.diameter_mm,
            "points_mm": route.points, "bend_radii_mm": route.bend_radii_mm,
            "bends": [asdict(item) for item in route.bends],
            "path_score": route.path_score, "envelope": envelope,
            "validation": validation,
        })
    passing = [item for item in candidates if item["validation"]["status"] == "PASS"]
    payload = {
        "schema_version": "route-development-pipeline.v1.0",
        "status": "PASS" if passing else "NO_BREP_VALID_CANDIDATE",
        "optimization_status": optimized.status,
        "objective": ("MINIMIZE_CENTERLINE_LENGTH_FIXED_D6_R15"
                      if args.objective == "shortest-d6"
                      else "MAXIMIZE_OUTER_DIAMETER"),
        "bend_rule": "R=2.5D",
        "search_grid_size_mm": args.grid_size_mm,
        "search_max_expanded_cells": args.max_expanded_cells,
        "evaluated_diameters_mm": list(diameters), "permitted_volume": cavity,
        "candidates": candidates,
        "selected_rank": passing[0]["rank"] if passing else None,
        "selected_diameter_mm": passing[0]["diameter_mm"] if passing else None,
        "catia_mutation": "NONE",
    }
    result = output / "route_development_result.json"
    result.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": payload["status"], "optimization_status": optimized.status,
        "selected_diameter_mm": payload["selected_diameter_mm"],
        "candidate_count": len(candidates), "result": str(result),
    }, ensure_ascii=False))
    return 0 if passing else 2


if __name__ == "__main__":
    raise SystemExit(main())
