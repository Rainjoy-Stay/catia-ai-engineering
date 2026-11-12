"""Analytic circular interface evidence derived from STEP face boundaries."""

from __future__ import annotations

import math
from typing import Any, Mapping


def _transform(matrix, vector, homogeneous):
    value = list(vector) + [homogeneous]
    return [sum(matrix[row][column] * value[column] for column in range(4)) for row in range(3)]


def circular_interface_candidates(step_body: Mapping[str, Any]) -> list[dict[str, Any]]:
    matrix = (step_body.get("assembly_transform") or {}).get("matrix")
    if not matrix:
        return []
    candidates = []
    for face in step_body.get("faces", ()):
        for curve in face.get("boundary_curves", ()):
            placement = curve.get("placement", {})
            center, normal, radius = (placement.get("origin_mm"),
                                      placement.get("axis_direction"), curve.get("radius_mm"))
            if not center or not normal or not radius:
                continue
            world_center = _transform(matrix, center, 1.0)
            world_normal = _transform(matrix, normal, 0.0)
            duplicate = next((item for item in candidates
                              if math.dist(item["center_mm"], world_center) <= 0.01 and
                              abs(item["radius_mm"] - radius) <= 0.01), None)
            if duplicate:
                duplicate["source_curve_ids"].append(curve["curve_id"])
            else:
                candidates.append({"center_mm": world_center, "normal": world_normal,
                                   "radius_mm": radius, "coordinate_space": "WORLD",
                                   "source_curve_ids": [curve["curve_id"]]})
    return candidates


def match_terminal_to_interfaces(terminal: Mapping[str, Any], interfaces: list[Mapping[str, Any]], *,
                                 position_tolerance_mm: float = 0.5,
                                 normal_tolerance_deg: float = 3.0) -> list[dict[str, Any]]:
    if terminal.get("coordinate_space") != "WORLD":
        return []
    direction = terminal.get("direction")
    cosine_limit = math.cos(math.radians(normal_tolerance_deg))
    matches = []
    for interface in interfaces:
        distance = math.dist(terminal["position_mm"], interface["center_mm"])
        alignment = abs(sum(a * b for a, b in zip(direction, interface["normal"]))) if direction else 0.0
        if distance <= position_tolerance_mm and alignment >= cosine_limit:
            matches.append({**dict(interface), "center_distance_mm": distance,
                            "normal_alignment_abs_cosine": alignment,
                            "evidence_state": "COINCIDENT_CIRCULAR_INTERFACE"})
    return sorted(matches, key=lambda item: (item["center_distance_mm"], -item["radius_mm"]))
