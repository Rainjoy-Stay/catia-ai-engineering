from __future__ import annotations

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
from catia_checker.route_brep_envelope import build_route_envelope_step  # noqa: E402
from catia_checker.route_design_constraints import RouteDesignCase  # noqa: E402
from catia_checker.route_design_optimizer import optimize_route_design_space  # noqa: E402
from catia_checker.spatial_route_planning import (  # noqa: E402
    SpatialRouteRequest, SurfacePort, TriangleMesh,
)


ART = ROOT / "project" / "artifacts"
OUT = ART / "max_diameter_r25_20260922"
OUT.mkdir(parents=True, exist_ok=True)


def mesh(name: str) -> TriangleMesh:
    data = json.loads((ART / name).read_text(encoding="utf-8"))
    return TriangleMesh(
        str(data.get("component", name)),
        tuple(tuple(map(float, p)) for p in data["vertices"]),
        tuple(tuple(map(int, t)) for t in data["triangles"]),
    )


# The coarse sweep proved D >= 16 impossible in this permitted volume.  Refine
# the transition interval instead of repeating already rejected large cases.
diameters = (14.0, 12.0, 10.0, 8.0, 6.0, 4.0)
cases = tuple(RouteDesignCase(
    diameter_mm=d,
    bend_radius_mm=2.5 * d,
    clearance_mm=0.0,
    minimum_straight_mm=0.0,
    standard_id=None,
    standard_policy="USER_REQUIREMENT",
    preferred_radius=True,
) for d in diameters)

base = SpatialRouteRequest(
    boundary_mesh=mesh("part2_spatial_mesh_20260922.json"),
    obstacle_meshes=(
        mesh("Part1_1_spatial_mesh_20260922.json"),
        mesh("Part3_1_spatial_mesh_20260922.json"),
        mesh("Part4_1_spatial_mesh_20260922.json"),
        mesh("Part5_1_spatial_mesh_20260922.json"),
    ),
    start=SurfacePort(
        (-67.49342966262095, 93.66743457406419, 31.83392281312019),
        (-0.6008805778851174, 0.7474093186836599, 0.2834110821144346), 48.0),
    goal=SurfacePort(
        (-27.314870296099286, -201.16516176810325, 16.139489659952446),
        (-0.8107850962850802, -0.3363363969981572, 0.47906717242605046), 48.0),
    grid_size_mm=6.0,
    pipe_outer_diameter_mm=diameters[-1],
    clearance_mm=0.0,
    bend_radius_mm=2.5 * diameters[-1],
    minimum_straight_mm=0.0,
    candidate_count=3,
    max_expanded_cells=400_000,
)

optimized = optimize_route_design_space(
    base, cases, diameter_selection_policy="MAXIMIZE_DIAMETER")

component_shapes = {
    "Part1.1": ("STEP_SOLID_0001",),
    "Part2.1": ("STEP_SOLID_0002",),
    "Part4.1": ("STEP_SOLID_0003", "STEP_SOLID_0004"),
    "Part3.1": ("STEP_SOLID_0005", "STEP_SOLID_0006", "STEP_SOLID_0007"),
    "Part5.1": ("STEP_SOLID_0008",),
}
policies = {
    "Part1.1": ComponentRoutePolicy("ALLOW_CONTACT", 0.0),
    "Part2.1": ComponentRoutePolicy("CLEARANCE", 0.0),
    "Part4.1": ComponentRoutePolicy("CLEARANCE", 0.0),
    # Point.1/Point.2 are unlinked surface ports and are validated separately;
    # the solid Part3 B-Rep remains an obstacle here, not the port authority.
    "Part3.1": ComponentRoutePolicy("CLEARANCE", 0.0),
    "Part5.1": ComponentRoutePolicy("CLEARANCE", 0.0),
}

candidates = []
for rank, route in enumerate(
        sorted(optimized.best_by_diameter, key=lambda item: -item.diameter_mm), 1):
    step_file = OUT / f"route_D{route.diameter_mm:g}_R{2.5*route.diameter_mm:g}.stp"
    envelope = build_route_envelope_step(
        route.points, route.bend_radii_mm, route.diameter_mm, step_file, 0.0)
    validation = validate_separate_route_brep(SeparateBRepRouteValidationRequest(
        step_file,
        ART / "MiniEngine_route_brep_validation_20260922.stp",
        "STEP_SOLID_0001",
        component_shapes,
        component_policies=policies,
        boundary_component="Part2.1",
        boundary_policy=BoundaryRoutePolicy("Part2.1", "WALL_ENCLOSURE"),
    ))
    candidates.append({
        "rank": rank,
        "diameter_mm": route.diameter_mm,
        "points_mm": route.points,
        "bend_radii_mm": route.bend_radii_mm,
        "bends": [asdict(item) for item in route.bends],
        "path_score": route.path_score,
        "standard_id": None,
        "standard_policy": "USER_REQUIREMENT_R_OVER_D_2.5",
        "envelope": envelope,
        "validation": validation,
    })

passing = [item for item in candidates if item["validation"]["status"] == "PASS"]
payload = {
    "schema_version": "route-development-pipeline.v1.0",
    "status": "PASS" if passing else "NO_BREP_VALID_CANDIDATE",
    "optimization_status": optimized.status,
    "objective": "MAXIMIZE_OUTER_DIAMETER",
    "bend_rule": "R=2.5D",
    "ports": {
        "start": {"component": "Part3.1", "name": "点.1", "surface": "曲面.2"},
        "goal": {"component": "Part3.1", "name": "点.2", "surface": "曲面.3"},
    },
    "evaluated_diameters_mm": list(diameters),
    "candidates": candidates,
    "selected_rank": passing[0]["rank"] if passing else None,
    "selected_diameter_mm": passing[0]["diameter_mm"] if passing else None,
    "catia_mutation": "NONE",
}
(OUT / "route_development_result.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "status": payload["status"],
    "optimization_status": optimized.status,
    "selected_rank": payload["selected_rank"],
    "selected_diameter_mm": payload["selected_diameter_mm"],
    "candidate_count": len(candidates),
    "optimizer_message": optimized.message,
}, ensure_ascii=False))
