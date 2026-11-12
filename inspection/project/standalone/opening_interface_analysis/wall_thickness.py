"""Infer local wall thickness from exact through-hole boundary pairs."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _unit(value: Sequence[float]) -> tuple[float, float, float]:
    vector = tuple(float(item) for item in value)
    if len(vector) != 3:
        raise ValueError("normal must contain X, Y and Z")
    length = math.sqrt(sum(item * item for item in vector))
    if length <= 1e-12:
        raise ValueError("normal must not be zero")
    return tuple(item / length for item in vector)  # type: ignore[return-value]


def infer_wall_thickness_from_opening_pairs(
        opening_face_records: Sequence[Mapping[str, Any]], *,
        angle_tolerance_deg: float = 1.0,
        centerline_tolerance_mm: float = 0.2,
        radius_tolerance_mm: float = 0.1,
        minimum_wall_thickness_mm: float = 0.01) -> dict[str, Any]:
    """Pair equal, coaxial circular boundaries on opposite wall faces."""
    faces = [{**dict(item), "circular_inner_boundaries": [dict(value) for value in
              item.get("circular_inner_boundaries", [])]} for item in opening_face_records]
    boundaries = []
    for face_index, face in enumerate(faces):
        for boundary_index, boundary in enumerate(face["circular_inner_boundaries"]):
            if not (boundary.get("closed") is True and boundary.get("exact_brep") is True):
                continue
            center = tuple(float(value) for value in boundary["center_mm"])
            normal = _unit(boundary.get("normal") or face.get("normal"))
            boundaries.append({"face_index": face_index, "boundary_index": boundary_index,
                               "id": str(boundary.get("boundary_id")), "center": center,
                               "normal": normal, "radius": float(boundary["radius_mm"])})
    candidates = []
    for index, first in enumerate(boundaries):
        for second in boundaries[index + 1:]:
            if first["face_index"] == second["face_index"]:
                continue
            alignment = min(1.0, abs(sum(first["normal"][i] * second["normal"][i]
                                         for i in range(3))))
            angle = math.degrees(math.acos(alignment))
            delta = tuple(second["center"][i] - first["center"][i] for i in range(3))
            axial = abs(sum(delta[i] * first["normal"][i] for i in range(3)))
            lateral = math.sqrt(max(0.0, sum(value * value for value in delta) - axial * axial))
            radius_delta = abs(first["radius"] - second["radius"])
            if (angle <= angle_tolerance_deg and lateral <= centerline_tolerance_mm and
                    radius_delta <= radius_tolerance_mm and axial >= minimum_wall_thickness_mm):
                candidates.append({"first": first, "second": second,
                                   "wall_thickness_mm": axial, "axis_angle_deg": angle,
                                   "centerline_offset_mm": lateral,
                                   "radius_delta_mm": radius_delta})
    by_boundary: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_boundary.setdefault(candidate["first"]["id"], []).append(candidate)
        by_boundary.setdefault(candidate["second"]["id"], []).append(candidate)
    accepted, ambiguous = [], []
    used: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: (
            item["centerline_offset_mm"], item["radius_delta_mm"], item["wall_thickness_mm"])):
        first_id, second_id = candidate["first"]["id"], candidate["second"]["id"]
        if len(by_boundary[first_id]) != 1 or len(by_boundary[second_id]) != 1:
            continue
        if first_id in used or second_id in used:
            continue
        used.update((first_id, second_id)); accepted.append(candidate)
        for member in (candidate["first"], candidate["second"]):
            face = faces[member["face_index"]]
            boundary = face["circular_inner_boundaries"][member["boundary_index"]]
            face["host_wall_thickness_mm"] = candidate["wall_thickness_mm"]
            face["host_discontinuity_confirmed"] = True
            boundary["opposite_boundary_id"] = second_id if member["id"] == first_id else first_id
            boundary["wall_thickness_method"] = "OPPOSITE_EXACT_CIRCULAR_BOUNDARIES"
    for boundary_id, values in sorted(by_boundary.items()):
        if len(values) > 1:
            ambiguous.append({"boundary_id": boundary_id,
                              "candidate_boundary_ids": sorted({
                                  item["second"]["id"] if item["first"]["id"] == boundary_id
                                  else item["first"]["id"] for item in values}),
                              "reason": "MULTIPLE_OPPOSITE_BOUNDARY_CANDIDATES"})
    logical_openings = []
    for item in accepted:
        first, second = item["first"], item["second"]
        logical_openings.append({
            "face_id": f"THROUGH_OPENING/{first['id']}+{second['id']}",
            "normal": list(first["normal"]),
            "host_wall_thickness_mm": item["wall_thickness_mm"],
            "host_discontinuity_confirmed": True, "exact_brep": True,
            "circular_inner_boundaries": [{
                "boundary_id": f"THROUGH/{first['id']}+{second['id']}",
                "source_boundary_ids": [first["id"], second["id"]],
                "center_mm": [(first["center"][axis] + second["center"][axis]) / 2.0
                              for axis in range(3)],
                "normal": list(first["normal"]),
                "radius_mm": (first["radius"] + second["radius"]) / 2.0,
                "closed": True, "exact_brep": True,
                "wall_thickness_method": "OPPOSITE_EXACT_CIRCULAR_BOUNDARIES"}]})
    paired_ids = {item for pair in accepted for item in (pair["first"]["id"], pair["second"]["id"])}
    analysis_faces = list(logical_openings)
    for face in faces:
        remaining = [item for item in face["circular_inner_boundaries"]
                     if str(item.get("boundary_id")) not in paired_ids]
        if remaining:
            analysis_faces.append({**face, "circular_inner_boundaries": remaining})
    return {"schema_version": "opening-wall-thickness.v1.0",
            "opening_face_records": faces, "candidate_pair_count": len(candidates),
            "analysis_opening_face_records": analysis_faces,
            "accepted_pair_count": len(accepted),
            "accepted_pairs": [{"boundary_a": item["first"]["id"],
                                "boundary_b": item["second"]["id"],
                                "wall_thickness_mm": item["wall_thickness_mm"],
                                "centerline_offset_mm": item["centerline_offset_mm"],
                                "radius_delta_mm": item["radius_delta_mm"]}
                               for item in accepted],
            "ambiguous": ambiguous, "mesh_used": False}
