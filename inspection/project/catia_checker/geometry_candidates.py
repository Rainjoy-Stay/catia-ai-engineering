"""Broad-phase candidate pairing for all admissible engineering geometry."""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any, Iterable, Mapping

from .geometry_integrity import admission_decision
from .geometry_coordinates import normalize_entity_world_bounds


def _bounds(value: Any) -> tuple[float, float, float, float, float, float]:
    result = tuple(float(item) for item in value)
    if len(result) != 6 or any(not math.isfinite(item) for item in result):
        raise ValueError("bounds_mm must contain six finite values")
    if any(result[index] > result[index + 3] for index in range(3)):
        raise ValueError("bounds_mm minimum must not exceed maximum")
    return result


def _separation(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    return math.sqrt(sum(max(first[axis] - second[axis + 3],
                             second[axis] - first[axis + 3], 0.0) ** 2
                         for axis in range(3)))


def build_geometry_candidates(entities: Iterable[Mapping[str, Any]], *,
                              search_margin_mm: float) -> dict[str, Any]:
    """Return only world-space candidate pairs, retaining a reason for every skip.

    AABB overlap is a broad-phase fact, not an interference conclusion.
    """
    if not math.isfinite(search_margin_mm) or search_margin_mm < 0:
        raise ValueError("search_margin_mm must be finite and non-negative")
    admitted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, raw in enumerate(entities, 1):
        entity = normalize_entity_world_bounds(raw)
        identifier = str(entity.get("object_id") or entity.get("source_id") or
                         entity.get("source_path") or f"ENTITY-{index:04d}")
        decision = admission_decision(entity)
        if not decision["included"]:
            skipped.append({"object_id": identifier, "why_skipped": decision["why_skipped"]})
            continue
        if str(entity.get("coordinate_space", "")).upper() != "WORLD":
            skipped.append({"object_id": identifier, "why_skipped": "NO_WORLD_BOUNDS"})
            continue
        try:
            bounds = _bounds(entity["bounds_mm"])
        except (KeyError, TypeError, ValueError):
            skipped.append({"object_id": identifier, "why_skipped": "INVALID_WORLD_BOUNDS"})
            continue
        admitted.append({"object_id": identifier, "bounds_mm": bounds,
                         "entity_kind": decision["entity_kind"],
                         "logical_component_id": entity.get("logical_component_id"),
                         "source_path": entity.get("source_path")})
    candidates: list[dict[str, Any]] = []
    for first, second in combinations(admitted, 2):
        if (first["logical_component_id"] and
                first["logical_component_id"] == second["logical_component_id"]):
            skipped.append({"object_id": f"{first['object_id']}|{second['object_id']}",
                            "why_skipped": "SAME_LOGICAL_COMPONENT"})
            continue
        lower_bound = _separation(first["bounds_mm"], second["bounds_mm"])
        if lower_bound <= search_margin_mm:
            candidates.append({
                "pair_id": "|".join(sorted((first["object_id"], second["object_id"]))),
                "object_a": first["object_id"], "object_b": second["object_id"],
                "entity_kind_a": first["entity_kind"], "entity_kind_b": second["entity_kind"],
                "aabb_distance_lower_bound_mm": round(lower_bound, 6),
                "broad_phase": "WORLD_AABB", "requires_precise_geometry": True,
            })
    return {
        "schema_version": "geometry-candidates.v1.0", "search_margin_mm": search_margin_mm,
        "admitted_entity_count": len(admitted), "candidate_pair_count": len(candidates),
        "candidates": sorted(candidates, key=lambda item: (item["aabb_distance_lower_bound_mm"], item["pair_id"])),
        "skip_log": skipped,
    }
