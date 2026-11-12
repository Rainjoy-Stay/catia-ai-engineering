"""Aggregate analytic and freeform face measurements for one Body."""

from __future__ import annotations

from enum import Enum
import math
from typing import Any, Iterable, Mapping


class SurfaceType(str, Enum):
    PLANE = "PLANE"
    CYLINDER = "CYLINDER"
    CONE = "CONE"
    SPHERE = "SPHERE"
    TORUS = "TORUS"
    BSPLINE = "BSPLINE"
    FREEFORM = "FREEFORM"
    OTHER = "OTHER"


def summarize_surfaces(faces: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {item.value: 0 for item in SurfaceType}
    areas = {item.value: 0.0 for item in SurfaceType}
    unmeasured = 0
    for face in faces:
        raw_type = str(face.get("surface_type", "OTHER")).upper()
        try:
            surface_type = SurfaceType(raw_type).value
        except ValueError:
            surface_type = SurfaceType.OTHER.value
        counts[surface_type] += 1
        area = face.get("area_mm2")
        if area is None:
            unmeasured += 1
            continue
        try:
            number = float(area)
        except (TypeError, ValueError) as exc:
            raise ValueError("face area_mm2 must be numeric") from exc
        if not math.isfinite(number) or number < 0:
            raise ValueError("face area_mm2 must be finite and non-negative")
        areas[surface_type] += number
    measured_area = sum(areas.values())
    ratios = {key: (value / measured_area if measured_area > 0 else None)
              for key, value in areas.items()}
    return {
        "face_count": sum(counts.values()),
        "unmeasured_face_count": unmeasured,
        "measured_face_area_mm2": measured_area,
        "surface_type_counts": counts,
        "surface_type_areas_mm2": areas,
        "surface_type_area_ratios": ratios,
    }
