"""Joint free-space path and per-bend-radius design-space optimization."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from .route_design_constraints import RouteDesignCase
from .route_manufacturability import BendGeometry, optimize_bend_radii
from .spatial_route_planning import MeshFreeSpacePlanner, Point, SpatialRouteRequest


@dataclass(frozen=True)
class OptimizedRoute:
    diameter_mm: float
    points: tuple[Point, ...]
    bend_radii_mm: tuple[float, ...]
    bends: tuple[BendGeometry, ...]
    path_score: float
    standard_id: str | None
    standard_policy: str


@dataclass(frozen=True)
class RouteDesignOptimizationResult:
    status: str
    ranked: tuple[OptimizedRoute, ...]
    best_by_diameter: tuple[OptimizedRoute, ...]
    message: str = ""


def optimize_route_design_space(
    base_request: SpatialRouteRequest, cases: Iterable[RouteDesignCase],
    planner: MeshFreeSpacePlanner | None = None,
    diameter_selection_policy: str = "EXTERNAL_REQUIRED",
) -> RouteDesignOptimizationResult:
    """Search once per diameter, then optimize every bend radius independently."""
    planner = planner or MeshFreeSpacePlanner()
    grouped: dict[float, list[RouteDesignCase]] = {}
    for case in cases:
        grouped.setdefault(case.diameter_mm, []).append(case)
    ranked: list[OptimizedRoute] = []
    failures: list[str] = []
    for diameter, diameter_cases in sorted(grouped.items()):
        radius_values = tuple(sorted({item.bend_radius_mm for item in diameter_cases}))
        preferred = tuple(
            item.bend_radius_mm for item in diameter_cases
            if item.preferred_radius and item.standard_policy in {"PREFERRED", "MANDATORY"}
        )
        seed = min(radius_values)
        exemplar = diameter_cases[0]
        result = planner.plan(replace(
            base_request, pipe_outer_diameter_mm=diameter,
            clearance_mm=exemplar.clearance_mm,
            minimum_straight_mm=exemplar.minimum_straight_mm,
            bend_radius_mm=seed,
        ))
        if result.status != "OK":
            failures.append(f"D={diameter:g}:{result.status}:{result.message}")
            continue
        paths = (result.points, *result.alternatives)
        scores = result.candidate_scores or tuple(
            result.objective_score or 0.0 for _ in paths)
        for path, score in zip(paths, scores):
            radii = optimize_bend_radii(
                path, radius_values, preferred, exemplar.minimum_straight_mm)
            if not radii.ok or radii.validation is None:
                failures.append(f"D={diameter:g}:R_OPT:{radii.message}")
                continue
            ranked.append(OptimizedRoute(
                diameter, path, radii.radii_mm, radii.validation.bends, score,
                exemplar.standard_id, exemplar.standard_policy,
            ))
    ranked.sort(key=lambda item: (
        item.path_score,
        -sum(item.bend_radii_mm),
        len(item.bend_radii_mm),
        item.points,
    ))
    best: dict[float, OptimizedRoute] = {}
    for route in ranked:
        best.setdefault(route.diameter_mm, route)
    best_by_diameter = tuple(best[key] for key in sorted(best))
    if not ranked:
        return RouteDesignOptimizationResult("NO_FEASIBLE_DESIGN", (), (), "; ".join(failures))
    if len(best_by_diameter) > 1 and diameter_selection_policy == "EXTERNAL_REQUIRED":
        return RouteDesignOptimizationResult(
            "REVIEW_DIAMETER_SELECTION", tuple(ranked), best_by_diameter,
            "Several diameters are geometrically feasible; hydraulic/interface selection is required",
        )
    return RouteDesignOptimizationResult("OK", tuple(ranked), best_by_diameter)
