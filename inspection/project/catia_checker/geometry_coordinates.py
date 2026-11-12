"""Coordinate-space normalization for inspection geometry.

Local AABBs are transformed by all eight corners.  Transforming only min/max
corners is invalid for rotated or mirrored assembly instances.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


IDENTITY_4X4 = (1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0)


def _matrix(value: Any) -> tuple[float, ...]:
    values = tuple(float(item) for item in value)
    if len(values) != 16 or any(not math.isfinite(item) for item in values):
        raise ValueError("world_transform.matrix must contain 16 finite values")
    if any(abs(values[index] - target) > 1e-9 for index, target in ((12, 0.0), (13, 0.0),
                                                                       (14, 0.0), (15, 1.0))):
        raise ValueError("world_transform must be an affine 4x4 matrix")
    return values


def _bounds(value: Any) -> tuple[float, float, float, float, float, float]:
    values = tuple(float(item) for item in value)
    if len(values) != 6 or any(not math.isfinite(item) for item in values):
        raise ValueError("bounds_mm must contain six finite values")
    if any(values[index] > values[index + 3] for index in range(3)):
        raise ValueError("bounds_mm minimum must not exceed maximum")
    return values


def transform_bounds_to_world(local_bounds_mm: Any, transform: Any) -> list[float]:
    bounds, matrix = _bounds(local_bounds_mm), _matrix(transform)
    points = []
    for x in (bounds[0], bounds[3]):
        for y in (bounds[1], bounds[4]):
            for z in (bounds[2], bounds[5]):
                points.append((matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3],
                               matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7],
                               matrix[8] * x + matrix[9] * y + matrix[10] * z + matrix[11]))
    return [min(point[axis] for point in points) for axis in range(3)] + [
        max(point[axis] for point in points) for axis in range(3)]


def normalize_entity_world_bounds(entity: Mapping[str, Any]) -> dict[str, Any]:
    """Attach a WORLD AABB only when its coordinate provenance is explicit."""
    result = dict(entity)
    space = str(result.get("coordinate_space") or result.get("reference_bounds_coordinate_space") or "").upper()
    bounds = result.get("bounds_mm", result.get("reference_bounds_mm"))
    if bounds is None:
        result["world_bounds_status"] = "UNAVAILABLE"
        result["world_bounds_reason"] = "NO_SOURCE_BOUNDS"
        return result
    if space == "WORLD":
        result["bounds_mm"] = list(_bounds(bounds))
        result["coordinate_space"] = "WORLD"
        result["world_bounds_status"] = "AVAILABLE"
        return result
    transform_data = result.get("world_transform") or result.get("assembly_transform") or {}
    matrix = transform_data.get("matrix") if isinstance(transform_data, Mapping) else None
    if matrix is None:
        result["world_bounds_status"] = "UNAVAILABLE"
        result["world_bounds_reason"] = "NO_WORLD_TRANSFORM"
        return result
    result["bounds_mm"] = [round(value, 6) for value in transform_bounds_to_world(bounds, matrix)]
    result["coordinate_space"] = "WORLD"
    result["world_bounds_status"] = "AVAILABLE"
    result["world_bounds_method"] = "LOCAL_AABB_EIGHT_CORNER_AFFINE_TRANSFORM"
    return result
