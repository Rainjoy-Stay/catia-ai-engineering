"""Typed, model-independent interface constraints for routed tubes."""

from __future__ import annotations

from dataclasses import dataclass
from math import dist, sqrt
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class RoutePortConstraint:
    port_id: str
    host_component: str
    point_mm: tuple[float, float, float]
    normal: tuple[float, float, float]
    contact_mode: str = "REQUIRED_CONTACT"
    diameter_candidates_mm: tuple[float, ...] = ()
    source_interface_id: str | None = None


@dataclass(frozen=True)
class ReducerPolicy:
    enabled: bool = False
    start_length_mm: float = 0.0
    goal_length_mm: float = 0.0
    maximum_half_angle_deg: float = 15.0

    def __post_init__(self) -> None:
        if self.start_length_mm < 0 or self.goal_length_mm < 0:
            raise ValueError("Reducer lengths cannot be negative")
        if not 0 < self.maximum_half_angle_deg < 90:
            raise ValueError("maximum_half_angle_deg must be between 0 and 90")


def resolve_unique_route_port(
    port_id: str, host_component: str, requested_point_mm: Sequence[float],
    requested_normal: Sequence[float], interface_candidates: Iterable[Mapping[str, object]],
    position_tolerance_mm: float = 0.5, normal_tolerance_abs_cosine: float = 0.9986,
) -> RoutePortConstraint:
    """Resolve one requested port only from unique coincident interface evidence."""
    point = tuple(map(float, requested_point_mm)); normal = _unit(requested_normal)
    matches = []
    for item in interface_candidates:
        center = tuple(map(float, item["center_mm"]))
        candidate_normal = _unit(item["normal"])
        alignment = abs(sum(a*b for a, b in zip(normal, candidate_normal)))
        if dist(point, center) <= position_tolerance_mm and alignment >= normal_tolerance_abs_cosine:
            matches.append((item, center, candidate_normal))
    if not matches:
        raise ValueError(f"Port {port_id!r} has no coincident interface geometry")
    if len(matches) > 1:
        raise ValueError(f"Port {port_id!r} is ambiguous ({len(matches)} interfaces match)")
    item, center, candidate_normal = matches[0]
    radius = item.get("radius_mm")
    diameters = () if radius is None else (2.0 * float(radius),)
    if sum(a*b for a, b in zip(normal, candidate_normal)) < 0:
        candidate_normal = tuple(-value for value in candidate_normal)
    return RoutePortConstraint(
        port_id, host_component, center, candidate_normal,
        diameter_candidates_mm=diameters,
        source_interface_id=str(item.get("interface_id") or item.get("boundary_id") or "") or None,
    )


def _unit(values: Sequence[float]) -> tuple[float, float, float]:
    vector = tuple(map(float, values))
    length = sqrt(sum(value*value for value in vector))
    if len(vector) != 3 or length <= 1e-12:
        raise ValueError("Interface normal must be a non-zero 3-D vector")
    return tuple(value/length for value in vector)  # type: ignore[return-value]
