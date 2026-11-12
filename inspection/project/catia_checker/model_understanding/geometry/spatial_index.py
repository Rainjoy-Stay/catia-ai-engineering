"""Small deterministic AABB index used before expensive geometry calculations."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class _Entry:
    object_id: str
    bounds: tuple[float, float, float, float, float, float]
    metadata: Mapping[str, Any]


class AABBSpatialIndex:
    def __init__(self, entries: Iterable[Mapping[str, Any]]) -> None:
        normalized = []
        for item in entries:
            if str(item.get("coordinate_space", "")).upper() != "WORLD":
                raise ValueError("AABB spatial index accepts only WORLD coordinate-space bounds")
            bounds = tuple(float(value) for value in item["bounds_mm"])
            if len(bounds) != 6 or any(bounds[i] > bounds[i + 3] for i in range(3)):
                raise ValueError("bounds_mm must contain valid min/max XYZ values")
            normalized.append(_Entry(str(item["object_id"]), bounds, dict(item.get("metadata", {}))))
        self._entries = tuple(normalized)

    @staticmethod
    def _point_distance(point: tuple[float, float, float], bounds: tuple[float, ...]) -> float:
        squared = 0.0
        for axis, value in enumerate(point):
            nearest = min(max(value, bounds[axis]), bounds[axis + 3])
            squared += (value - nearest) ** 2
        return math.sqrt(squared)

    def query_point(self, position_mm: Iterable[float], radius_mm: float, *,
                    exclude_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
        point = tuple(float(value) for value in position_mm)
        if len(point) != 3 or radius_mm < 0:
            raise ValueError("position must be XYZ and radius must be non-negative")
        excluded = set(exclude_ids)
        matches = []
        for entry in self._entries:
            if entry.object_id in excluded:
                continue
            distance = self._point_distance(point, entry.bounds)
            if distance <= radius_mm:
                matches.append({"object_id": entry.object_id,
                                "aabb_distance_lower_bound_mm": distance,
                                "metadata": dict(entry.metadata)})
        return sorted(matches, key=lambda item: (item["aabb_distance_lower_bound_mm"], item["object_id"]))
