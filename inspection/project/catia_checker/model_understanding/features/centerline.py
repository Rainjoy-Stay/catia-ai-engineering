"""Build untrimmed centerline primitives from analytic STEP surfaces."""

from __future__ import annotations

import math
from typing import Any, Mapping


def _parallel(a: list[float], b: list[float], angle_tolerance_deg: float) -> bool:
    cosine = abs(sum(x * y for x, y in zip(a, b)))
    return cosine >= math.cos(math.radians(angle_tolerance_deg))


def _axis_offset(a_origin: list[float], b_origin: list[float], direction: list[float]) -> float:
    delta = [b - a for a, b in zip(a_origin, b_origin)]
    projection = sum(value * axis for value, axis in zip(delta, direction))
    perpendicular = [value - projection * axis for value, axis in zip(delta, direction)]
    return math.sqrt(sum(value * value for value in perpendicular))


def _trimmed_axis(face: Mapping[str, Any], radius: float, origin: list[float],
                  direction: list[float], radius_tolerance: float) -> dict[str, Any]:
    centers = []
    for curve in face.get("boundary_curves", ()):
        curve_radius = curve.get("radius_mm")
        placement = curve.get("placement", {})
        center, normal = placement.get("origin_mm"), placement.get("axis_direction")
        if (curve.get("curve_type") == "CIRCLE" and curve_radius and center and normal and
                abs(curve_radius - radius) <= radius_tolerance * max(curve_radius, radius) and
                _parallel(direction, normal, 1.0) and
                _axis_offset(origin, center, direction) <= 0.1):
            centers.append(center)
    if len(centers) < 2:
        return {"boundary_centers_mm": centers, "trim_state": "UNTRIMMED"}
    ordered = sorted(centers, key=lambda point: sum((p - o) * d for p, o, d in zip(point, origin, direction)))
    start, end = ordered[0], ordered[-1]
    length = math.sqrt(sum((b - a) ** 2 for a, b in zip(start, end)))
    return {"boundary_centers_mm": centers, "start_mm": start, "end_mm": end,
            "length_mm": length, "trim_state": "TRIMMED"}


def analytic_centerline_primitives(step_body: Mapping[str, Any], *,
                                   angle_tolerance_deg: float = 1.0,
                                   coaxial_tolerance_mm: float = 0.1,
                                   radius_relative_tolerance: float = 0.01) -> dict[str, Any]:
    primitives: list[dict[str, Any]] = []
    for face in step_body.get("faces", ()):
        placement = face.get("placement", {})
        origin, axis = placement.get("origin_mm"), placement.get("axis_direction")
        parameters = face.get("parameters", {})
        if not origin or not axis:
            continue
        if face.get("surface_type") == "CYLINDER" and parameters.get("radius", 0) > 0:
            candidate = {"primitive_type": "LINE_AXIS", "origin_mm": origin,
                         "direction": axis, "surface_radius_mm": parameters["radius"],
                         "surface_radii_mm": [parameters["radius"]],
                         "source_face_ids": [face["face_id"]], "trim_state": "UNTRIMMED"}
            candidate.update(_trimmed_axis(face, parameters["radius"], origin, axis,
                                           radius_relative_tolerance))
            duplicate = next((item for item in primitives if item["primitive_type"] == "LINE_AXIS" and
                              _parallel(item["direction"], axis, angle_tolerance_deg) and
                              _axis_offset(item["origin_mm"], origin, item["direction"]) <= coaxial_tolerance_mm), None)
            if duplicate:
                duplicate["source_face_ids"].append(face["face_id"])
                if parameters["radius"] not in duplicate["surface_radii_mm"]:
                    duplicate["surface_radii_mm"].append(parameters["radius"])
                duplicate["surface_radius_mm"] = max(duplicate["surface_radii_mm"])
                centers = duplicate.get("boundary_centers_mm", []) + candidate.get("boundary_centers_mm", [])
                if len(centers) >= 2:
                    ordered = sorted(centers, key=lambda point: sum(
                        (p - o) * d for p, o, d in zip(point, duplicate["origin_mm"], duplicate["direction"])))
                    duplicate.update({"boundary_centers_mm": centers, "start_mm": ordered[0],
                                      "end_mm": ordered[-1], "length_mm": math.dist(ordered[0], ordered[-1]),
                                      "trim_state": "TRIMMED"})
            else:
                primitives.append(candidate)
        elif face.get("surface_type") == "TORUS" and parameters.get("major_radius", 0) > 0:
            primitives.append({
                "primitive_type": "CIRCLE", "center_mm": origin, "normal": axis,
                "centerline_radius_mm": parameters["major_radius"],
                "tube_surface_radius_mm": parameters.get("minor_radius"),
                "source_face_ids": [face["face_id"]], "trim_state": "UNTRIMMED",
            })
    return {
        "representation": "ANALYTIC_UNTRIMMED_PRIMITIVES",
        "primitives": primitives,
        "line_axis_count": sum(item["primitive_type"] == "LINE_AXIS" for item in primitives),
        "circle_count": sum(item["primitive_type"] == "CIRCLE" for item in primitives),
        "limitations": [
            "Analytic surface axes and torus center circles are infinite/untrimmed",
            "Segment endpoints, lengths, turn angles and connectivity require boundary topology",
        ],
    }


def derive_step_pipe_features(step_body: Mapping[str, Any]) -> dict[str, Any]:
    """Combine STEP analytic topology into conservative pipe-scoring facts."""
    result = dict(step_body.get("tubular_features", {}))
    centerline = build_composite_centerline(step_body)
    result["centerline_candidate"] = centerline
    dominant_radius = result.get("dominant_radius")
    if dominant_radius and centerline["complete"]:
        diameter = 2.0 * dominant_radius
        length = sum(float(item.get("length_mm", 0.0)) for item in centerline["segments"])
        terminals = centerline["terminal_candidates"]
        transform = (step_body.get("assembly_transform") or {}).get("matrix")
        if transform:
            terminals = [{**terminal,
                          "position_mm": _apply_transform(transform, terminal["position_mm"], 1.0),
                          "direction": _apply_transform(transform, terminal["direction"], 0.0),
                          "coordinate_space": "WORLD"} for terminal in terminals]
            world_segments = []
            for segment in centerline["segments"]:
                converted = dict(segment)
                for key in ("start_mm", "end_mm", "center_mm", "origin_mm"):
                    if converted.get(key):
                        converted[key] = _apply_transform(transform, converted[key], 1.0)
                for key in ("direction", "normal"):
                    if converted.get(key):
                        converted[key] = _apply_transform(transform, converted[key], 0.0)
                converted["coordinate_space"] = "WORLD"
                world_segments.append(converted)
            result["centerline_segments_world"] = world_segments
        result.update({
            "centerline_continuity": centerline["centerline_continuity"],
            "centerline_length_mm": length,
            "terminal_count": centerline["terminal_count"],
            "terminal_candidates": terminals,
            "aspect_ratio_max_second": length / diameter if diameter > 0 else None,
            "aspect_ratio_basis": "CENTERLINE_LENGTH_OVER_DOMINANT_DIAMETER",
        })
    else:
        result.update({"centerline_continuity": None, "terminal_count": None,
                       "terminal_candidates": []})
    return result


def _apply_transform(matrix: list[list[float]], vector: list[float], homogeneous: float) -> list[float]:
    value = vector + [homogeneous]
    return [sum(matrix[row][column] * value[column] for column in range(4)) for row in range(3)]


def _point_circle_distance(point: list[float], center: list[float], normal: list[float],
                           radius: float) -> tuple[float, list[float]]:
    delta = [value - origin for value, origin in zip(point, center)]
    plane_offset = sum(value * axis for value, axis in zip(delta, normal))
    planar = [value - plane_offset * axis for value, axis in zip(delta, normal)]
    radial = math.sqrt(sum(value * value for value in planar))
    return math.sqrt(plane_offset ** 2 + (radial - radius) ** 2), planar


def build_composite_centerline(step_body: Mapping[str, Any], *,
                               connection_tolerance_mm: float = 0.2,
                               tangent_angle_tolerance_deg: float = 2.0) -> dict[str, Any]:
    """Connect trimmed lines and torus circles only with explicit positional/tangent evidence."""
    analytic = analytic_centerline_primitives(step_body)
    lines = [dict(item) for item in analytic["primitives"]
             if item["primitive_type"] == "LINE_AXIS" and item.get("trim_state") == "TRIMMED"]
    circles = [dict(item) for item in analytic["primitives"] if item["primitive_type"] == "CIRCLE"]
    endpoints = []
    for line_index, line in enumerate(lines):
        endpoints.extend([
            {"line_index": line_index, "end": "start", "position_mm": line["start_mm"]},
            {"line_index": line_index, "end": "end", "position_mm": line["end_mm"]},
        ])
    used: set[tuple[int, str]] = set()
    connections = []
    arcs = []

    for first_index, first in enumerate(endpoints):
        if (first["line_index"], first["end"]) in used:
            continue
        for second in endpoints[first_index + 1:]:
            if first["line_index"] == second["line_index"]:
                continue
            if math.dist(first["position_mm"], second["position_mm"]) <= connection_tolerance_mm:
                connections.append({"type": "LINE_LINE", "first": first, "second": second})
                used.update({(first["line_index"], first["end"]),
                             (second["line_index"], second["end"])})
                break

    tangent_cosine = math.sin(math.radians(tangent_angle_tolerance_deg))
    for circle_index, circle in enumerate(circles):
        matches = []
        for endpoint in endpoints:
            key = (endpoint["line_index"], endpoint["end"])
            if key in used:
                continue
            distance, radial = _point_circle_distance(
                endpoint["position_mm"], circle["center_mm"], circle["normal"],
                circle["centerline_radius_mm"])
            radial_length = math.sqrt(sum(value * value for value in radial))
            direction = lines[endpoint["line_index"]]["direction"]
            tangent = (radial_length > 0 and
                       abs(sum(a * b for a, b in zip(direction, radial))) / radial_length <= tangent_cosine and
                       abs(sum(a * b for a, b in zip(direction, circle["normal"]))) <= tangent_cosine)
            if distance <= connection_tolerance_mm and tangent:
                matches.append((distance, endpoint, radial))
        matches.sort(key=lambda item: item[0])
        distinct = []
        for match in matches:
            if all(match[1]["line_index"] != item[1]["line_index"] for item in distinct):
                distinct.append(match)
            if len(distinct) == 2:
                break
        if len(distinct) != 2:
            continue
        (_, first, first_radial), (_, second, second_radial) = distinct
        radius = circle["centerline_radius_mm"]
        cosine = max(-1.0, min(1.0, sum(a * b for a, b in zip(first_radial, second_radial)) /
                                (radius * radius)))
        angle_deg = math.degrees(math.acos(cosine))
        arc = {"primitive_type": "ARC", "center_mm": circle["center_mm"],
               "normal": circle["normal"], "radius_mm": radius,
               "start_mm": first["position_mm"], "end_mm": second["position_mm"],
               "turn_angle_deg": angle_deg, "length_mm": math.radians(angle_deg) * radius,
               "source_face_ids": circle["source_face_ids"], "trim_state": "TRIMMED"}
        arcs.append(arc)
        connections.append({"type": "LINE_ARC", "first": first, "second": second,
                            "arc_index": len(arcs) - 1})
        used.update({(first["line_index"], first["end"]), (second["line_index"], second["end"])})

    terminals = []
    for endpoint in endpoints:
        if (endpoint["line_index"], endpoint["end"]) in used:
            continue
        direction = lines[endpoint["line_index"]]["direction"]
        terminals.append({**endpoint, "direction": ([-value for value in direction]
                                                      if endpoint["end"] == "start" else list(direction))})
    segment_count = len(lines) + len(arcs)
    connected = sum(2 if item["type"] == "LINE_ARC" else 1 for item in connections)
    continuity = (1.0 if segment_count == 1 and len(terminals) == 2 else
                  min(1.0, connected / max(1, segment_count - 1)))
    return {
        "representation": "COMPOSITE_CENTERLINE_V0.3",
        "segments": lines + arcs,
        "connections": connections,
        "terminal_candidates": terminals,
        "terminal_count": len(terminals),
        "centerline_continuity": continuity,
        "complete": bool(segment_count and len(terminals) == 2 and continuity >= 0.999),
        "limitations": (["unresolved analytic circle candidates remain"] if len(arcs) < len(circles) else []),
    }
