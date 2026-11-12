"""Merge analytic inner/outer cylindrical faces into physical nozzle records."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence


def _vec(value: Sequence[float], field: str) -> tuple[float, float, float]:
    if len(value) != 3:
        raise ValueError(f"{field} must contain X, Y and Z")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{field} must contain finite values")
    return result  # type: ignore[return-value]


def _unit(value: Sequence[float]) -> tuple[float, float, float]:
    vector = _vec(value, "axis_direction")
    length = math.sqrt(sum(item * item for item in vector))
    if length <= 1e-12:
        raise ValueError("axis_direction must not be zero")
    axis = tuple(item / length for item in vector)
    for item in axis:
        if abs(item) > 1e-12:
            return tuple(-value for value in axis) if item < 0 else axis
    return axis


def _axis_offset(first: Mapping[str, Any], second: Mapping[str, Any]) -> float:
    axis = first["axis"]
    delta = tuple(first["point"][i] - second["point"][i] for i in range(3))
    along = sum(delta[i] * axis[i] for i in range(3))
    normal = tuple(delta[i] - along * axis[i] for i in range(3))
    return math.sqrt(sum(item * item for item in normal))


def _prepare(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    point = _vec(raw["axis_point_mm"], "axis_point_mm")
    raw_axis_value = _vec(raw["axis_direction"], "axis_direction")
    raw_length = math.sqrt(sum(item * item for item in raw_axis_value))
    if raw_length <= 1e-12:
        raise ValueError("axis_direction must not be zero")
    raw_axis = tuple(item / raw_length for item in raw_axis_value)
    axis = _unit(raw_axis_value)
    radius = float(raw["surface_radius_mm"])
    local_start, local_end = float(raw["axis_start_mm"]), float(raw["axis_end_mm"])
    endpoints = [tuple(point[i] + value * raw_axis[i] for i in range(3))
                 for value in (local_start, local_end)]
    start, end = sorted(sum(endpoint[i] * axis[i] for i in range(3)) for endpoint in endpoints)
    point_scalar = sum(point[i] * axis[i] for i in range(3))
    axis_foot = tuple(point[i] - point_scalar * axis[i] for i in range(3))
    if radius <= 0 or end <= start:
        raise ValueError("cylinder radius and axial span must be positive")
    return {"raw": dict(raw), "id": str(raw.get("surface_id") or f"CYL-{index}"),
            "component": raw.get("component_id"), "point": axis_foot, "axis": axis,
            "radius": radius, "start": start, "end": end}


def merge_coaxial_cylinders(records: Iterable[Mapping[str, Any]], *,
                            axis_angle_tolerance_deg: float = 0.1,
                            axis_offset_tolerance_mm: float = 0.05,
                            axial_overlap_tolerance_mm: float = 0.05,
                            radius_tolerance_mm: float = 0.01) -> dict[str, Any]:
    """Merge overlapping coaxial faces; never join separated collinear segments."""
    if min(axis_angle_tolerance_deg, axis_offset_tolerance_mm,
           axial_overlap_tolerance_mm, radius_tolerance_mm) < 0:
        raise ValueError("tolerances must be non-negative")
    prepared = [_prepare(item, index) for index, item in enumerate(records, 1)]
    parents = list(range(len(prepared)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]; index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        left, right = find(first), find(second)
        if left != right:
            parents[right] = left

    comparison_count = 0
    for index, first in enumerate(prepared):
        for other_index in range(index + 1, len(prepared)):
            second = prepared[other_index]
            if first["component"] and second["component"] and first["component"] != second["component"]:
                continue
            comparison_count += 1
            alignment = min(1.0, abs(sum(first["axis"][i] * second["axis"][i] for i in range(3))))
            angle = math.degrees(math.acos(alignment))
            overlap = min(first["end"], second["end"]) - max(first["start"], second["start"])
            if (angle <= axis_angle_tolerance_deg and
                    _axis_offset(first, second) <= axis_offset_tolerance_mm and
                    overlap >= -axial_overlap_tolerance_mm):
                union(index, other_index)
    groups: dict[int, list[dict[str, Any]]] = {}
    for index, item in enumerate(prepared):
        groups.setdefault(find(index), []).append(item)
    merged = []
    for group_index, members in enumerate(groups.values(), 1):
        radii = []
        for value in sorted(item["radius"] for item in members):
            if not radii or abs(value - radii[-1]) > radius_tolerance_mm:
                radii.append(value)
        component = next((str(item["component"]) for item in members if item["component"]), None)
        review_codes = []
        if len(radii) == 1:
            review_codes.append("INNER_RADIUS_NOT_OBSERVED")
        elif len(radii) > 2:
            review_codes.append("MULTIPLE_CONCENTRIC_RADII")
        locators = [item["raw"].get("source_locator") for item in members
                    if isinstance(item["raw"].get("source_locator"), dict)]
        locator_bodies = {(item.get("source_body_index"), item.get("source_body_name"))
                          for item in locators}
        source_locator = locators[0] if len(locator_bodies) == 1 and locators else None
        merged.append({"nozzle_id": component or f"COAXIAL-NOZZLE-{group_index:04d}",
                       "component_id": component,
                       "source_surface_ids": sorted(item["id"] for item in members),
                       "axis_point_mm": list(members[0]["point"]),
                       "axis_direction": list(members[0]["axis"]),
                       "outer_radius_mm": max(radii),
                       "inner_radius_mm": min(radii) if len(radii) >= 2 else None,
                       "axis_start_mm": max(item["start"] for item in members),
                       "axis_end_mm": min(item["end"] for item in members),
                       "review_codes": review_codes,
                       "source_locator": source_locator,
                       "source_face_locators": locators,
                       "exact_brep": all(item["raw"].get("exact_brep") is True for item in members)})
    return {"schema_version": "coaxial-cylinder-merge.v1.0",
            "input_surface_count": len(prepared), "comparison_count": comparison_count,
            "nozzle_count": len(merged), "nozzles": merged, "mesh_used": False}
