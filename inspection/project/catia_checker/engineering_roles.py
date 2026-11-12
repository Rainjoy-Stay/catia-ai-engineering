"""Deterministic engineering-role hypotheses for recovered tubular patches."""

from __future__ import annotations

import itertools
import math
from typing import Any, Iterable, Mapping


def _axial_span(component: Mapping[str, Any]) -> float | None:
    bounds = component.get("bounds_mm")
    directions = component.get("axis_directions") or []
    if not isinstance(bounds, dict) or not directions:
        return None
    direction = [float(value) for value in directions[0]]
    corners = itertools.product(*zip(bounds["min"], bounds["max"]))
    projections = [sum(float(value) * axis for value, axis in zip(point, direction))
                   for point in corners]
    return max(projections) - min(projections)


def classify_tubular_roles(logical: Mapping[str, Any],
                           pair_facts: Iterable[Mapping[str, Any]], *,
                           vessel_radius_floor_mm: float = 150.0,
                           slenderness_threshold: float = 2.0,
                           host_radius_ratio: float = 2.5) -> dict[str, Any]:
    """Classify PIPE/NOZZLE/VESSEL candidates while preserving uncertainty."""
    components = {item["logical_component_id"]: dict(item)
                  for item in logical.get("components", [])}
    face_map = dict(logical.get("face_to_component") or {})
    adjacency: dict[str, set[str]] = {key: set() for key in components}
    intersections: set[tuple[str, str]] = set()
    for fact in pair_facts:
        first = face_map.get(str(fact.get("object_a")))
        second = face_map.get(str(fact.get("object_b")))
        if not first or not second or first == second:
            continue
        if fact.get("intersects") or fact.get("boundary_contact") or fact.get("minimum_distance_mm") == 0:
            adjacency[first].add(second)
            adjacency[second].add(first)
        if fact.get("surface_intersection"):
            intersections.add(tuple(sorted((first, second))))

    results = []
    for component_id, component in components.items():
        geometry_type = component.get("engineering_object_type")
        if geometry_type not in {"TUBULAR_COMPONENT_CANDIDATE", "PIPE_BEND_CANDIDATE"}:
            continue
        radius = component.get("representative_radius_mm")
        radius = float(radius) if radius is not None else None
        span = _axial_span(component)
        slenderness = span / (2.0 * radius) if span is not None and radius and radius > 0 else None
        neighbors = sorted(adjacency.get(component_id, set()))
        larger_hosts = []
        for neighbor_id in neighbors:
            neighbor_radius = components[neighbor_id].get("representative_radius_mm")
            if radius and neighbor_radius and float(neighbor_radius) >= radius * host_radius_ratio:
                larger_hosts.append(neighbor_id)
        intersects_larger_host = any(
            tuple(sorted((component_id, host))) in intersections for host in larger_hosts)
        reasons = []
        if geometry_type == "PIPE_BEND_CANDIDATE":
            role, confidence = "PIPE_BEND", 0.94
            reasons.append("ANALYTIC_TORUS_WITH_PIPE_MINOR_RADIUS")
        elif intersects_larger_host:
            role, confidence = "NOZZLE", 0.9
            reasons.extend(["TUBULAR_PATCH_INTERSECTS_LARGER_CYLINDRICAL_HOST",
                            "HOST_TO_TUBE_RADIUS_RATIO_CONFIRMED"])
        elif radius is not None and radius >= vessel_radius_floor_mm:
            role, confidence = "VESSEL_SHELL", 0.86
            reasons.extend(["LARGE_ANALYTIC_CYLINDER", "RADIUS_ABOVE_CONFIGURED_VESSEL_FLOOR"])
        elif slenderness is not None and slenderness >= slenderness_threshold:
            role, confidence = "PIPE", 0.84
            reasons.extend(["SLENDER_ANALYTIC_CYLINDER", "AXIAL_SPAN_TO_DIAMETER_CONFIRMED"])
        else:
            role, confidence = "TUBULAR_COMPONENT", 0.55
            reasons.append("TUBULAR_GEOMETRY_WITH_INSUFFICIENT_ENGINEERING_CONTEXT")
        results.append({"logical_component_id": component_id,
                        "engineering_role": role, "confidence": confidence,
                        "radius_mm": radius, "axial_span_mm": span,
                        "axial_span_to_diameter": slenderness,
                        "neighbor_component_ids": neighbors,
                        "larger_host_component_ids": larger_hosts,
                        "intersects_larger_host": intersects_larger_host,
                        "basis": reasons,
                        "status": "CANDIDATE" if confidence >= 0.8 else "REVIEW"})
    results.sort(key=lambda item: item["logical_component_id"])
    counts: dict[str, int] = {}
    for item in results:
        counts[item["engineering_role"]] = counts.get(item["engineering_role"], 0) + 1
    return {"schema_version": "engineering-roles.v1.0", "candidate_count": len(results),
            "role_counts": counts, "candidates": results,
            "policy": {"vessel_radius_floor_mm": vessel_radius_floor_mm,
                       "slenderness_threshold": slenderness_threshold,
                       "host_radius_ratio": host_radius_ratio},
            "mesh_used": False}
