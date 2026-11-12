"""Precision-first mid-span pipe support candidate recognition."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from .interfaces import circular_interface_candidates


def _projection(point, start, end):
    vector = [b - a for a, b in zip(start, end)]
    length_squared = sum(value * value for value in vector)
    if not length_squared:
        return 0.0, math.dist(point, start)
    t = sum((p - a) * value for p, a, value in zip(point, start, vector)) / length_squared
    closest = [a + t * value for a, value in zip(start, vector)]
    return t, math.dist(point, closest)


def midspan_support_candidates(bodies: Iterable[Mapping[str, Any]],
                               pipe_features: Mapping[str, Mapping[str, Any]], *,
                               center_tolerance_mm: float = 0.5,
                               radius_ratio_range: tuple[float, float] = (0.95, 1.25),
                               terminal_exclusion_fraction: float = 0.05) -> list[dict[str, Any]]:
    """Recognize clamp-like enclosure only from coaxial, radius-matched mid-span circles."""
    bodies = list(bodies)
    interfaces = {body["source_id"]: circular_interface_candidates(body) for body in bodies}
    results = []
    for pipe_id, features in pipe_features.items():
        pipe_radius = features.get("dominant_radius")
        if not pipe_radius:
            continue
        for segment_index, segment in enumerate(features.get("centerline_segments_world", ())):
            if segment.get("primitive_type") != "LINE_AXIS" or not segment.get("start_mm"):
                continue
            direction = segment.get("direction")
            for body_id, body_interfaces in interfaces.items():
                if body_id == pipe_id:
                    continue
                matched = []
                for interface in body_interfaces:
                    ratio = float(interface["radius_mm"]) / float(pipe_radius)
                    t, offset = _projection(interface["center_mm"], segment["start_mm"], segment["end_mm"])
                    alignment = abs(sum(a * b for a, b in zip(direction, interface["normal"])))
                    if (terminal_exclusion_fraction < t < 1.0 - terminal_exclusion_fraction and
                            offset <= center_tolerance_mm and radius_ratio_range[0] <= ratio <= radius_ratio_range[1]
                            and alignment >= math.cos(math.radians(3.0))):
                        matched.append({"interface": interface, "segment_fraction": t,
                                        "axis_offset_mm": offset, "radius_ratio": ratio,
                                        "axis_alignment_abs_cosine": alignment})
                if matched:
                    results.append({
                        "pipe_body_id": pipe_id, "support_body_id": body_id,
                        "relationship_type": "SUPPORTED", "object_type_candidate": "CLAMP",
                        "confidence": 0.9, "decision_source": "DETERMINISTIC_GEOMETRY_V0.5",
                        "evidence": "COAXIAL_RADIUS_MATCHED_MIDSPAN_ENCLOSURE",
                        "segment_index": segment_index, "interface_matches": matched,
                        "uncertainty": ["Support load path and attachment to structure are not yet proven"],
                    })
    return results


def _bounds_distance(first, second):
    squared = 0.0
    for axis in range(3):
        gap = max(0.0, first[axis] - second[axis + 3], second[axis] - first[axis + 3])
        squared += gap * gap
    return math.sqrt(squared)


def bracket_attachment_candidates(bodies: Iterable[Mapping[str, Any]],
                                  clamp_relationships: Iterable[Mapping[str, Any]], *,
                                  contact_tolerance_mm: float = 0.1) -> list[dict[str, Any]]:
    """Find conservative planar bracket candidates attached to a proven clamp candidate."""
    bodies_by_id = {body["source_id"]: body for body in bodies}
    results = []
    for clamp_relation in clamp_relationships:
        clamp_id, pipe_id = clamp_relation["support_body_id"], clamp_relation["pipe_body_id"]
        clamp = bodies_by_id.get(clamp_id)
        if not clamp or not clamp.get("reference_bounds_mm"):
            continue
        pipe_diameter = 2.0 * float(clamp_relation["interface_matches"][0]["interface"]["radius_mm"])
        for body_id, candidate in bodies_by_id.items():
            if body_id in {clamp_id, pipe_id} or not candidate.get("reference_bounds_mm"):
                continue
            statistics = candidate.get("surface_statistics", {})
            counts, face_count = statistics.get("surface_type_counts", {}), statistics.get("face_count", 0)
            plane_ratio = float(counts.get("PLANE", 0)) / face_count if face_count else 0.0
            tubular_ratio = (float(counts.get("CYLINDER", 0)) + float(counts.get("TORUS", 0))) / face_count if face_count else 0.0
            bounds = candidate["reference_bounds_mm"]
            maximum_dimension = max(bounds[axis + 3] - bounds[axis] for axis in range(3))
            distance = _bounds_distance(clamp["reference_bounds_mm"], bounds)
            if (distance <= contact_tolerance_mm and plane_ratio >= 0.5 and tubular_ratio <= 0.2 and
                    maximum_dimension <= 10.0 * pipe_diameter):
                results.append({
                    "clamp_body_id": clamp_id, "support_body_id": body_id,
                    "relationship_type": "SUPPORTED", "object_type_candidate": "BRACKET",
                    "confidence": 0.75, "decision_source": "DETERMINISTIC_GEOMETRY_V0.5",
                    "evidence": "PLANAR_COMPACT_BODY_CONTACTING_PROVEN_CLAMP",
                    "metrics": {"aabb_distance_lower_bound_mm": distance,
                                "plane_face_ratio": plane_ratio,
                                "tubular_face_ratio": tubular_ratio},
                    "uncertainty": ["AABB contact is broad-phase evidence; exact contact area is not yet measured"],
                })
    return results
