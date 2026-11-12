"""Normalize per-Body dimensions and mass properties into millimetres."""

from __future__ import annotations

import math
from typing import Any, Mapping


def _finite(value: Any, name: str, *, non_negative: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or (non_negative and result < 0):
        raise ValueError(f"{name} must be finite" + (" and non-negative" if non_negative else ""))
    return result


def _point(value: Any, name: str) -> list[float]:
    if isinstance(value, Mapping):
        value = [value.get(axis) for axis in ("x", "y", "z")]
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must contain x, y and z")
    return [_finite(item, name) for item in value]


def normalize_basic_features(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic derived features without claiming missing measurements."""
    measurement_scope = str(raw.get("measurement_scope", "BODY")).upper()
    if measurement_scope != "BODY":
        raise ValueError("Per-Body features require measurement_scope=BODY")
    result: dict[str, Any] = {}
    if raw.get("volume_mm3") is not None:
        result["volume_mm3"] = _finite(raw["volume_mm3"], "volume_mm3", non_negative=True)
    area = raw.get("surface_area_mm2", raw.get("area_mm2"))
    if area is not None:
        result["surface_area_mm2"] = _finite(area, "surface_area_mm2", non_negative=True)
    centroid = raw.get("centroid_mm", raw.get("center_of_gravity_mm"))
    if centroid is not None:
        result["centroid_mm"] = _point(centroid, "centroid_mm")

    bounds = raw.get("bounding_box_mm")
    if bounds is not None:
        if isinstance(bounds, Mapping):
            minimum, maximum = _point(bounds.get("min"), "bounding_box_mm.min"), _point(
                bounds.get("max"), "bounding_box_mm.max")
        elif isinstance(bounds, (list, tuple)) and len(bounds) == 6:
            values = [_finite(item, "bounding_box_mm") for item in bounds]
            minimum, maximum = values[:3], values[3:]
        else:
            raise ValueError("bounding_box_mm must contain min/max or six coordinates")
        dimensions = [maximum[i] - minimum[i] for i in range(3)]
        if any(value < 0 for value in dimensions):
            raise ValueError("bounding_box_mm maximum must not be below minimum")
        ordered = sorted(dimensions, reverse=True)
        result.update({
            "bounding_box_mm": {"min": minimum, "max": maximum},
            "bbox_dimensions_mm": dimensions,
            "max_dimension_mm": ordered[0],
            "second_dimension_mm": ordered[1],
            "min_dimension_mm": ordered[2],
            "aspect_ratio_max_second": ordered[0] / ordered[1] if ordered[1] > 0 else None,
            "aspect_ratio_max_min": ordered[0] / ordered[2] if ordered[2] > 0 else None,
        })
    if raw.get("principal_axis") is not None:
        axis = _point(raw["principal_axis"], "principal_axis")
        magnitude = math.sqrt(sum(item * item for item in axis))
        if magnitude == 0:
            raise ValueError("principal_axis must not be zero")
        result["principal_axis"] = [item / magnitude for item in axis]

    result["measurement"] = {
        "method": str(raw.get("measurement_method", "UNKNOWN")),
        "quality": str(raw.get("measurement_quality", "UNKNOWN")),
        "tolerance_mm": (_finite(raw["tolerance_mm"], "tolerance_mm", non_negative=True)
                         if raw.get("tolerance_mm") is not None else None),
        "scope": measurement_scope,
    }
    return result
