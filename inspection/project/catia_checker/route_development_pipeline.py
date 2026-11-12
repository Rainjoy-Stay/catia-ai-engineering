"""Configuration-driven route development pipeline with fail-closed gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .brep_route_validation import (
    BoundaryRoutePolicy, ComponentRoutePolicy, SeparateBRepRouteValidationRequest,
    validate_separate_route_brep,
)
from .route_brep_envelope import build_route_envelope_step
from .route_design_constraints import RouteDesignCase
from .route_design_optimizer import optimize_route_design_space
from .route_interfaces import ReducerPolicy, RoutePortConstraint
from .spatial_route_planning import (
    MeshFreeSpacePlanner, SpatialRouteRequest, SurfacePort, TriangleMesh,
)


@dataclass(frozen=True)
class RouteDevelopmentRequest:
    boundary_mesh: TriangleMesh
    obstacle_meshes: tuple[TriangleMesh, ...]
    start_port: RoutePortConstraint
    goal_port: RoutePortConstraint
    design_cases: tuple[RouteDesignCase, ...]
    port_lead_length_mm: float
    grid_size_mm: float
    candidate_count: int = 4
    max_expanded_cells: int = 400_000
    diameter_selection_policy: str = "EXTERNAL_REQUIRED"
    diameter_tolerance_mm: float = 0.1
    environment_step_file: str | Path | None = None
    component_shapes: dict[str, tuple[str, ...]] | None = None
    component_policies: dict[str, ComponentRoutePolicy] | None = None
    boundary_component: str | None = None
    boundary_policy: BoundaryRoutePolicy | None = None
    reducer_policy: ReducerPolicy = ReducerPolicy()
    top_n: int = 3


def run_route_development_pipeline(
    request: RouteDevelopmentRequest, output_directory: str | Path,
    planner: MeshFreeSpacePlanner | None = None,
) -> dict[str, Any]:
    """Run interface-gated optimization and exact-envelope validation."""
    if request.port_lead_length_mm <= 0 or request.grid_size_mm <= 0:
        raise ValueError("port lead and grid size must be positive")
    cases = _interface_compatible_cases(request)
    first = cases[0]
    base = SpatialRouteRequest(
        request.boundary_mesh, request.obstacle_meshes,
        SurfacePort(request.start_port.point_mm, request.start_port.normal,
                    request.port_lead_length_mm),
        SurfacePort(request.goal_port.point_mm, request.goal_port.normal,
                    request.port_lead_length_mm),
        grid_size_mm=request.grid_size_mm,
        pipe_outer_diameter_mm=first.diameter_mm,
        clearance_mm=first.clearance_mm,
        bend_radius_mm=min(item.bend_radius_mm for item in cases
                           if item.diameter_mm == first.diameter_mm),
        minimum_straight_mm=first.minimum_straight_mm,
        candidate_count=request.candidate_count,
        max_expanded_cells=request.max_expanded_cells,
    )
    optimized = optimize_route_design_space(
        base, cases, planner=planner,
        diameter_selection_policy=request.diameter_selection_policy,
    )
    folder = Path(output_directory).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    candidates = []
    for index, route in enumerate(optimized.ranked[:request.top_n], 1):
        step_file = folder / f"route_candidate_{index:02d}.stp"
        build = build_route_envelope_step(
            route.points, route.bend_radii_mm, route.diameter_mm, step_file,
            next(item.minimum_straight_mm for item in cases
                 if item.diameter_mm == route.diameter_mm),
            start_interface_diameter_mm=(request.start_port.diameter_candidates_mm[0]
                                         if request.start_port.diameter_candidates_mm else None),
            goal_interface_diameter_mm=(request.goal_port.diameter_candidates_mm[0]
                                        if request.goal_port.diameter_candidates_mm else None),
            start_reducer_length_mm=request.reducer_policy.start_length_mm,
            goal_reducer_length_mm=request.reducer_policy.goal_length_mm,
            maximum_reducer_half_angle_deg=request.reducer_policy.maximum_half_angle_deg,
        )
        validation: dict[str, Any] = {
            "status": "NOT_EVALUATED",
            "reason": "No environment STEP and component mapping supplied",
        }
        if request.environment_step_file is not None:
            if not request.component_shapes or not request.component_policies:
                raise ValueError("Exact environment validation requires shapes and policies")
            validation = validate_separate_route_brep(SeparateBRepRouteValidationRequest(
                step_file, request.environment_step_file, "STEP_SOLID_0001",
                request.component_shapes,
                component_policies=request.component_policies,
                boundary_component=request.boundary_component,
                boundary_policy=request.boundary_policy,
            ))
        candidates.append({
            "rank": index,
            "diameter_mm": route.diameter_mm,
            "points_mm": route.points,
            "bend_radii_mm": route.bend_radii_mm,
            "bends": [asdict(item) for item in route.bends],
            "path_score": route.path_score,
            "standard_id": route.standard_id,
            "standard_policy": route.standard_policy,
            "envelope": build,
            "validation": validation,
        })
    passing = [item for item in candidates if item["validation"]["status"] == "PASS"]
    status = optimized.status
    if request.environment_step_file is not None:
        status = "PASS" if passing else "NO_BREP_VALID_CANDIDATE"
    payload = {
        "schema_version": "route-development-pipeline.v1.0",
        "status": status,
        "optimization_status": optimized.status,
        "message": optimized.message,
        "ports": {"start": asdict(request.start_port), "goal": asdict(request.goal_port)},
        "evaluated_case_count": len(cases),
        "candidates": candidates,
        "selected_rank": passing[0]["rank"] if passing else None,
        "catia_mutation": "NONE",
    }
    (folder / "route_development_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _interface_compatible_cases(request: RouteDevelopmentRequest) -> tuple[RouteDesignCase, ...]:
    start = request.start_port.diameter_candidates_mm
    goal = request.goal_port.diameter_candidates_mm
    mismatch = start and goal and not any(
        abs(a-b) <= request.diameter_tolerance_mm for a in start for b in goal)
    if mismatch and not request.reducer_policy.enabled:
        raise ValueError("Start and goal interface diameters differ; reducer policy is required")
    permitted = (*start, *goal)
    if request.reducer_policy.enabled:
        return request.design_cases
    if not permitted:
        return request.design_cases
    result = tuple(case for case in request.design_cases
                   if any(abs(case.diameter_mm-value) <= request.diameter_tolerance_mm
                          for value in permitted))
    if not result:
        raise ValueError("No design diameter is compatible with the resolved interfaces")
    return result
