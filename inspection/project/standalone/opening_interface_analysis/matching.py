"""Broad-phase and deterministic one-to-one opening/nozzle matching."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _vec(value: Sequence[float], field: str) -> tuple[float, float, float]:
    if len(value) != 3:
        raise ValueError(f"{field} must contain X, Y and Z")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{field} must contain finite values")
    return result  # type: ignore[return-value]


def _unit(value: Sequence[float], field: str) -> tuple[float, float, float]:
    vector = _vec(value, field)
    length = math.sqrt(sum(item * item for item in vector))
    if length <= 1e-12:
        raise ValueError(f"{field} must not be a zero vector")
    return tuple(item / length for item in vector)  # type: ignore[return-value]


def _nozzle_record(raw: Mapping[str, Any], margin_mm: float) -> dict[str, Any]:
    point = _vec(raw["axis_point_mm"], "nozzle.axis_point_mm")
    axis = _unit(raw["axis_direction"], "nozzle.axis_direction")
    start, end = sorted((float(raw.get("axis_start_mm", 0.0)), float(raw["axis_end_mm"])))
    radius = float(raw["outer_radius_mm"])
    if radius <= 0:
        raise ValueError("nozzle.outer_radius_mm must be positive")
    first = tuple(point[i] + start * axis[i] for i in range(3))
    second = tuple(point[i] + end * axis[i] for i in range(3))
    pad = radius + margin_mm
    return {"raw": dict(raw), "id": str(raw.get("nozzle_id") or "UNKNOWN_NOZZLE"),
            "point": point, "axis": axis, "start": start, "end": end, "radius": radius,
            "bounds": {"min": [min(first[i], second[i]) - pad for i in range(3)],
                       "max": [max(first[i], second[i]) + pad for i in range(3)]}}


def _candidate(opening: Mapping[str, Any], nozzle: Mapping[str, Any], *,
               angle_limit_deg: float, offset_limit_mm: float,
               radius_limit_mm: float, axial_margin_mm: float) -> dict[str, Any] | None:
    center = _vec(opening["center_mm"], "opening.center_mm")
    normal = _unit(opening["normal"], "opening.normal")
    opening_radius = float(opening["radius_mm"])
    if opening_radius <= 0:
        raise ValueError("opening.radius_mm must be positive")
    delta = tuple(center[i] - nozzle["point"][i] for i in range(3))
    axial = sum(delta[i] * nozzle["axis"][i] for i in range(3))
    closest = tuple(nozzle["point"][i] + axial * nozzle["axis"][i] for i in range(3))
    offset = math.dist(center, closest)
    alignment = min(1.0, max(0.0, abs(sum(normal[i] * nozzle["axis"][i] for i in range(3)))))
    angle = math.degrees(math.acos(alignment))
    radius_delta = abs(opening_radius - nozzle["radius"])
    axial_ok = nozzle["start"] - axial_margin_mm <= axial <= nozzle["end"] + axial_margin_mm
    if (angle > angle_limit_deg or offset > offset_limit_mm or
            radius_delta > radius_limit_mm or not axial_ok):
        return None
    score = (angle / max(angle_limit_deg, 1e-12) +
             offset / max(offset_limit_mm, 1e-12) +
             radius_delta / max(radius_limit_mm, 1e-12)) / 3.0
    return {"opening_id": str(opening.get("opening_id") or "UNKNOWN_OPENING"),
            "nozzle_id": nozzle["id"], "score": score,
            "axis_angle_deg": angle, "axis_offset_mm": offset,
            "radius_delta_mm": radius_delta, "axis_parameter_mm": axial,
            "opening": dict(opening), "nozzle": nozzle["raw"]}


def match_openings_to_nozzles(openings: Sequence[Mapping[str, Any]],
                              nozzles: Sequence[Mapping[str, Any]], *,
                              search_margin_mm: float = 5.0,
                              angle_candidate_limit_deg: float = 5.0,
                              offset_candidate_limit_mm: float = 5.0,
                              radius_candidate_limit_mm: float = 5.0,
                              axial_margin_mm: float = 5.0,
                              ambiguity_score_delta: float = 0.05) -> dict[str, Any]:
    """Match openings and nozzles after a sweep-and-prune point/AABB broad phase."""
    values = (search_margin_mm, angle_candidate_limit_deg, offset_candidate_limit_mm,
              radius_candidate_limit_mm, axial_margin_mm, ambiguity_score_delta)
    if min(values) < 0:
        raise ValueError("matching tolerances must be non-negative")
    opening_records = sorted(
        [dict(item) for item in openings], key=lambda item: float(item["center_mm"][0]))
    nozzle_records = sorted(
        [_nozzle_record(item, search_margin_mm) for item in nozzles],
        key=lambda item: item["bounds"]["min"][0])
    active: list[dict[str, Any]] = []
    cursor = 0
    spatial_pairs = 0
    candidates = []
    for opening in opening_records:
        center = _vec(opening["center_mm"], "opening.center_mm")
        while (cursor < len(nozzle_records) and
               nozzle_records[cursor]["bounds"]["min"][0] <= center[0]):
            active.append(nozzle_records[cursor]); cursor += 1
        active = [item for item in active if item["bounds"]["max"][0] >= center[0]]
        for nozzle in active:
            bounds = nozzle["bounds"]
            if not all(bounds["min"][i] <= center[i] <= bounds["max"][i] for i in (1, 2)):
                continue
            spatial_pairs += 1
            item = _candidate(opening, nozzle,
                              angle_limit_deg=angle_candidate_limit_deg,
                              offset_limit_mm=offset_candidate_limit_mm,
                              radius_limit_mm=radius_candidate_limit_mm,
                              axial_margin_mm=axial_margin_mm)
            if item:
                candidates.append(item)

    by_opening: dict[str, list[dict[str, Any]]] = {}
    by_nozzle: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        by_opening.setdefault(item["opening_id"], []).append(item)
        by_nozzle.setdefault(item["nozzle_id"], []).append(item)
    ambiguous_openings = {key for key, items in by_opening.items()
                          if len(items) > 1 and
                          sorted(x["score"] for x in items)[1] -
                          sorted(x["score"] for x in items)[0] <= ambiguity_score_delta}
    ambiguous_nozzles = {key for key, items in by_nozzle.items()
                         if len(items) > 1 and
                         sorted(x["score"] for x in items)[1] -
                         sorted(x["score"] for x in items)[0] <= ambiguity_score_delta}
    assigned_openings: set[str] = set()
    assigned_nozzles: set[str] = set()
    matches = []
    for item in sorted(candidates, key=lambda value: (value["score"], value["opening_id"], value["nozzle_id"])):
        if item["opening_id"] in ambiguous_openings or item["nozzle_id"] in ambiguous_nozzles:
            continue
        if item["opening_id"] in assigned_openings or item["nozzle_id"] in assigned_nozzles:
            continue
        assigned_openings.add(item["opening_id"]); assigned_nozzles.add(item["nozzle_id"])
        matches.append(item)
    opening_ids = {str(item.get("opening_id") or "UNKNOWN_OPENING") for item in openings}
    nozzle_ids = {str(item.get("nozzle_id") or "UNKNOWN_NOZZLE") for item in nozzles}
    ambiguities = [{"object_type": "OPENING", "object_id": key,
                    "candidate_ids": [item["nozzle_id"] for item in by_opening[key]],
                    "disposition": "REVIEW", "reason": "MULTIPLE_SIMILAR_CANDIDATES"}
                   for key in sorted(ambiguous_openings)]
    ambiguities += [{"object_type": "NOZZLE", "object_id": key,
                     "candidate_ids": [item["opening_id"] for item in by_nozzle[key]],
                     "disposition": "REVIEW", "reason": "MULTIPLE_SIMILAR_CANDIDATES"}
                    for key in sorted(ambiguous_nozzles)]
    return {"schema_version": "opening-nozzle-matching.v1.0",
            "matches": matches, "match_count": len(matches),
            "ambiguities": ambiguities,
            "unmatched_opening_ids": sorted(opening_ids - assigned_openings),
            "unmatched_nozzle_ids": sorted(nozzle_ids - assigned_nozzles),
            "broad_phase": {"method": "X_SWEEP_POINT_TO_NOZZLE_AABB",
                            "total_possible_pairs": len(openings) * len(nozzles),
                            "spatial_candidate_pairs": spatial_pairs,
                            "geometry_candidate_pairs": len(candidates)},
            "mesh_used": False}
