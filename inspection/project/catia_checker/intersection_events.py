"""Aggregate exact Face-pair intersections into traceable engineering events."""

from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable, Mapping


def _objects(fact: Mapping[str, Any]) -> set[str]:
    return {str(fact["object_a"]), str(fact["object_b"])}


def _near(first: Mapping[str, Any], second: Mapping[str, Any], tolerance_mm: float) -> bool:
    a, b = first.get("section_center_mm"), second.get("section_center_mm")
    if not (isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 3):
        return False
    return math.dist([float(v) for v in a], [float(v) for v in b]) <= tolerance_mm


def _union_bounds(facts: list[Mapping[str, Any]]) -> dict[str, list[float]] | None:
    bounds = [item.get("section_bounds_mm") for item in facts
              if isinstance(item.get("section_bounds_mm"), dict)]
    if not bounds:
        return None
    return {
        "min": [min(float(item["min"][axis]) for item in bounds) for axis in range(3)],
        "max": [max(float(item["max"][axis]) for item in bounds) for axis in range(3)],
    }


def aggregate_intersection_events(facts: Iterable[Mapping[str, Any]], *,
                                  merge_tolerance_mm: float = 25.0) -> dict[str, Any]:
    """Cluster interior intersections that share a Face and a local region.

    Face-level facts remain referenced by index. Spatial proximity alone never
    merges records, preventing two remote nozzles on one vessel from collapsing
    into a single issue.
    """
    tolerance = max(0.0, float(merge_tolerance_mm))
    selected = [dict(item) for item in facts
                if item.get("intersection_type") == "SURFACE_INTERSECTION"
                or item.get("surface_intersection") is True]
    parent = list(range(len(selected)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        a, b = find(first), find(second)
        if a != b:
            parent[b] = a

    for index, first in enumerate(selected):
        first_objects = _objects(first)
        for other_index in range(index + 1, len(selected)):
            second = selected[other_index]
            if first_objects.intersection(_objects(second)) and _near(first, second, tolerance):
                union(index, other_index)

    groups: dict[int, list[int]] = {}
    for index in range(len(selected)):
        groups.setdefault(find(index), []).append(index)
    events = []
    for member_indexes in groups.values():
        members = [selected[index] for index in member_indexes]
        object_ids = sorted(set().union(*(_objects(item) for item in members)))
        bounds = _union_bounds(members)
        center = None if bounds is None else [
            (bounds["min"][axis] + bounds["max"][axis]) / 2.0 for axis in range(3)]
        digest = hashlib.sha256("|".join(object_ids).encode()).hexdigest()[:10].upper()
        events.append({
            "event_id": f"INT-{digest}",
            "event_type": "SURFACE_INTERSECTION_EVENT",
            "status": "FAIL",
            "object_ids": object_ids,
            "face_pair_count": len(members),
            "section_edge_count": sum(int(item.get("section_edge_count") or 0) for item in members),
            "section_bounds_mm": bounds,
            "location_xyz_mm": center,
            "face_pairs": [{"object_a": item["object_a"], "object_b": item["object_b"]}
                           for item in members],
            "merge_basis": "SHARED_FACE_AND_LOCAL_SECTION_REGION",
            "merge_tolerance_mm": tolerance,
        })
    events.sort(key=lambda item: item["event_id"])
    return {"schema_version": "intersection-events.v1.0",
            "input_face_pair_count": len(selected), "event_count": len(events),
            "events": events, "face_facts_preserved": True}
