"""Pure geometry policy for matching a nozzle to a host-wall opening.

The caller supplies facts extracted by CATIA SPA or an exact B-Rep kernel.
This module does not open CAD files and never substitutes mesh measurements.
"""

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


def _unit(value: Sequence[float], field: str) -> tuple[float, float, float]:
    vector = _vec(value, field)
    length = math.sqrt(sum(item * item for item in vector))
    if length <= 1e-12:
        raise ValueError(f"{field} must not be a zero vector")
    return tuple(item / length for item in vector)  # type: ignore[return-value]


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _sub(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return tuple(x - y for x, y in zip(a, b))  # type: ignore[return-value]


def analyze_interface(opening: Mapping[str, Any], nozzle: Mapping[str, Any], *,
                      coaxial_tolerance_mm: float = 0.5,
                      angle_tolerance_deg: float = 1.0,
                      radial_clearance_min_mm: float = 0.0,
                      radial_clearance_max_mm: float = 2.0,
                      axial_tolerance_mm: float = 0.1) -> dict[str, Any]:
    """Evaluate one opening/nozzle candidate from exact analytic geometry facts."""
    if min(coaxial_tolerance_mm, angle_tolerance_deg, radial_clearance_min_mm,
           radial_clearance_max_mm, axial_tolerance_mm) < 0:
        raise ValueError("tolerances must be non-negative")
    if radial_clearance_max_mm < radial_clearance_min_mm:
        raise ValueError("radial_clearance_max_mm must be >= radial_clearance_min_mm")

    center = _vec(opening["center_mm"], "opening.center_mm")
    normal = _unit(opening["normal"], "opening.normal")
    axis_point = _vec(nozzle["axis_point_mm"], "nozzle.axis_point_mm")
    axis = _unit(nozzle["axis_direction"], "nozzle.axis_direction")
    opening_radius = float(opening["radius_mm"])
    nozzle_radius = float(nozzle["outer_radius_mm"])
    if opening_radius <= 0 or nozzle_radius <= 0:
        raise ValueError("opening and nozzle radii must be positive")

    alignment = min(1.0, max(0.0, abs(_dot(normal, axis))))
    angle_deg = math.degrees(math.acos(alignment))
    point_delta = _sub(center, axis_point)
    projection = _dot(point_delta, axis)
    closest = tuple(axis_point[i] + projection * axis[i] for i in range(3))
    offset_mm = math.dist(center, closest)
    plane_parameter = (_dot(_sub(center, axis_point), normal) /
                       _dot(axis, normal)) if abs(_dot(axis, normal)) > 1e-12 else None
    start_mm = float(nozzle.get("axis_start_mm", 0.0))
    end_mm = float(nozzle["axis_end_mm"])
    low, high = sorted((start_mm, end_mm))
    crosses_plane = (plane_parameter is not None and
                     low - axial_tolerance_mm <= plane_parameter <= high + axial_tolerance_mm)
    wall_thickness = opening.get("host_wall_thickness_mm")
    spans_wall = None
    if wall_thickness is not None and plane_parameter is not None:
        half_span = abs(float(wall_thickness) / (2.0 * _dot(axis, normal)))
        spans_wall = (low - axial_tolerance_mm <= plane_parameter - half_span and
                      high + axial_tolerance_mm >= plane_parameter + half_span)

    clearance_mm = opening_radius - nozzle_radius
    exact = (opening.get("exact_brep") is True and nozzle.get("exact_brep") is True)
    boundary_complete = opening.get("boundary_complete") is True
    host_discontinuity = opening.get("host_discontinuity_confirmed") is True

    failures = []
    reviews = list(nozzle.get("review_codes") or [])
    if angle_deg > angle_tolerance_deg:
        failures.append("AXIS_ANGLE_OUT_OF_TOLERANCE")
    if offset_mm > coaxial_tolerance_mm:
        failures.append("AXIS_OFFSET_OUT_OF_TOLERANCE")
    if clearance_mm < radial_clearance_min_mm:
        failures.append("OPENING_UNDERSIZED")
    elif clearance_mm > radial_clearance_max_mm:
        failures.append("OPENING_CLEARANCE_TOO_LARGE")
    if not crosses_plane:
        failures.append("NOZZLE_DOES_NOT_CROSS_OPENING_PLANE")
    if spans_wall is False:
        failures.append("NOZZLE_DOES_NOT_SPAN_HOST_WALL")
    if not exact:
        reviews.append("EXACT_BREP_EVIDENCE_REQUIRED")
    if not boundary_complete:
        reviews.append("COMPLETE_OPENING_BOUNDARY_REQUIRED")
    if not host_discontinuity:
        reviews.append("HOST_WALL_DISCONTINUITY_REQUIRED")
    if wall_thickness is None:
        reviews.append("HOST_WALL_THICKNESS_REQUIRED")

    disposition = "FAIL" if failures else "REVIEW" if reviews else "PASS"
    return {
        "schema_version": "opening-interface-analysis.v1.0",
        "opening_id": str(opening.get("opening_id") or "UNKNOWN_OPENING"),
        "nozzle_id": str(nozzle.get("nozzle_id") or "UNKNOWN_NOZZLE"),
        "disposition": disposition,
        "failure_codes": failures,
        "review_codes": reviews,
        "measurements": {
            "axis_angle_deg": angle_deg,
            "axis_offset_mm": offset_mm,
            "radial_clearance_mm": clearance_mm,
            "opening_radius_mm": opening_radius,
            "nozzle_outer_radius_mm": nozzle_radius,
            "host_wall_thickness_mm": (float(wall_thickness)
                                       if wall_thickness is not None else None),
            "opening_plane_parameter_mm": plane_parameter,
            "crosses_opening_plane": crosses_plane,
            "spans_host_wall": spans_wall,
        },
        "evidence": {
            "exact_brep": exact,
            "boundary_complete": boundary_complete,
            "host_discontinuity_confirmed": host_discontinuity,
        },
        "source_locators": {
            "opening": opening.get("source_locator"),
            "nozzle": nozzle.get("source_locator"),
        },
        "mesh_used": False,
    }


def analyze_interfaces(candidates: Iterable[Mapping[str, Any]], **tolerances: Any) -> dict[str, Any]:
    """Evaluate pre-matched candidates and summarize dispositions."""
    results = [analyze_interface(item["opening"], item["nozzle"], **tolerances)
               for item in candidates]
    counts = {status: sum(item["disposition"] == status for item in results)
              for status in ("PASS", "FAIL", "REVIEW")}
    return {
        "schema_version": "opening-interface-analysis-batch.v1.0",
        "result_count": len(results),
        "disposition_counts": counts,
        "results": results,
        "candidate_matching_external": True,
        "mesh_used": False,
    }
