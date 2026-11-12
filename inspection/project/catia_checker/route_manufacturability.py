"""Deterministic hard gates for a filleted tubing centreline."""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, cos, degrees, dist, isfinite, tan
from typing import Sequence

Point = tuple[float, float, float]


@dataclass(frozen=True)
class RouteManufacturabilityResult:
    ok: bool
    errors: tuple[str, ...]
    setbacks_mm: tuple[float, ...]
    segment_margins_mm: tuple[float, ...]
    bends: tuple["BendGeometry", ...] = ()


@dataclass(frozen=True)
class BendGeometry:
    node_index: int
    angle_deg: float
    radius_mm: float
    tangent_start: Point
    tangent_end: Point
    center: Point
    axis: Point


@dataclass(frozen=True)
class RadiusOptimizationResult:
    ok: bool
    radii_mm: tuple[float, ...] = ()
    validation: RouteManufacturabilityResult | None = None
    message: str = ""


def optimize_bend_radii(
    points: Sequence[Sequence[float]], candidate_radii_mm: Sequence[float],
    preferred_radii_mm: Sequence[float] = (), minimum_straight_mm: float = 0.0,
) -> RadiusOptimizationResult:
    """Choose an individual radius at every arbitrary-angle bend by DP."""
    pts = tuple(tuple(map(float, point)) for point in points)
    count = len(pts) - 2
    if count <= 0:
        check = validate_polyline_route(pts, ())
        return RadiusOptimizationResult(check.ok, (), check)
    radii = tuple(sorted(set(float(value) for value in candidate_radii_mm)))
    if not radii or any(value <= 0 for value in radii):
        return RadiusOptimizationResult(False, message="No positive radius candidates")
    preferred = set(map(float, preferred_radii_mm))
    coefficients: list[float] = []
    for i in range(1, len(pts) - 1):
        incoming = _unit(_sub(pts[i], pts[i-1])); outgoing = _unit(_sub(pts[i+1], pts[i]))
        if incoming is None or outgoing is None:
            return RadiusOptimizationResult(False, message=f"Degenerate segment at node {i}")
        theta = acos(max(-1.0, min(1.0, _dot(incoming, outgoing))))
        if theta >= 3.141592653589793 - 1e-6:
            return RadiusOptimizationResult(False, message=f"Route reversal at node {i}")
        coefficients.append(tan(theta / 2.0))
    lengths = [dist(a, b) for a, b in zip(pts, pts[1:])]
    # DP value: (preferred count, total radius, chosen tuple), maximized in
    # that priority order while satisfying every coupled segment constraint.
    states: dict[float, tuple[int, float, tuple[float, ...]]] = {}
    for radius in radii:
        if coefficients[0] * radius <= lengths[0] + 1e-6:
            states[radius] = (int(radius in preferred), radius, (radius,))
    for bend_index in range(1, count):
        next_states: dict[float, tuple[int, float, tuple[float, ...]]] = {}
        available = lengths[bend_index] - minimum_straight_mm
        for radius in radii:
            feasible = [value for previous, value in states.items()
                        if coefficients[bend_index-1] * previous
                        + coefficients[bend_index] * radius <= available + 1e-6]
            if feasible:
                best = max(feasible, key=lambda item: (item[0] + int(radius in preferred),
                                                       item[1] + radius, item[2]))
                next_states[radius] = (
                    best[0] + int(radius in preferred), best[1] + radius,
                    best[2] + (radius,),
                )
        states = next_states
        if not states:
            return RadiusOptimizationResult(False, message=f"No radius combination fits segment {bend_index}")
    feasible_end = [value for radius, value in states.items()
                    if coefficients[-1] * radius <= lengths[-1] + 1e-6]
    if not feasible_end:
        return RadiusOptimizationResult(False, message="No radius fits final segment")
    chosen = max(feasible_end, key=lambda item: (item[0], item[1], item[2]))[2]
    check = validate_polyline_route(pts, chosen, minimum_straight_mm)
    return RadiusOptimizationResult(check.ok, chosen, check,
                                    "" if check.ok else "; ".join(check.errors))


def validate_polyline_route(
    points: Sequence[Sequence[float]], bend_radii_mm: Sequence[float],
    minimum_straight_mm: float = 0.0, tolerance_mm: float = 1e-6,
) -> RouteManufacturabilityResult:
    """Reject routes whose requested fillets cannot fit their polyline."""
    pts: tuple[Point, ...] = tuple(tuple(map(float, p)) for p in points)  # type: ignore[assignment]
    errors: list[str] = []
    if len(pts) < 2:
        return RouteManufacturabilityResult(False, ("AT_LEAST_TWO_POINTS_REQUIRED",), (), ())
    lengths = [dist(a, b) for a, b in zip(pts, pts[1:])]
    for index, length in enumerate(lengths):
        if not isfinite(length) or length <= tolerance_mm:
            errors.append(f"DEGENERATE_SEGMENT:{index}")
    count = len(pts) - 2
    if count == 0:
        radii: list[float] = []
    elif len(bend_radii_mm) == 1:
        radii = [float(bend_radii_mm[0])] * count
    elif len(bend_radii_mm) == count:
        radii = list(map(float, bend_radii_mm))
    else:
        return RouteManufacturabilityResult(False, ("BEND_RADIUS_COUNT_MISMATCH",), (), ())
    setbacks = [0.0] * len(pts)
    bends: list[BendGeometry] = []
    for i, radius in enumerate(radii, 1):
        if not isfinite(radius) or radius <= 0:
            errors.append(f"INVALID_BEND_RADIUS:{i}")
            continue
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        incoming = _unit(_sub(b, a)); outgoing = _unit(_sub(c, b))
        if incoming is None or outgoing is None:
            continue
        theta = acos(max(-1.0, min(1.0, _dot(incoming, outgoing))))
        if theta >= 3.141592653589793 - 1e-6:
            errors.append(f"REVERSAL_AT_NODE:{i}")
        elif theta > 1e-6:
            setbacks[i] = radius * tan(theta / 2.0)
            tangent_start = _add(b, _scale(incoming, -setbacks[i]))
            tangent_end = _add(b, _scale(outgoing, setbacks[i]))
            bisector = _unit(_sub(outgoing, incoming))
            axis = _unit(_cross(incoming, outgoing))
            if bisector is None or axis is None:
                errors.append(f"DEGENERATE_BEND_PLANE:{i}")
            else:
                center = _add(b, _scale(bisector, radius / cos(theta / 2.0)))
                bends.append(BendGeometry(
                    i, degrees(theta), radius, tangent_start, tangent_end, center, axis,
                ))
    margins: list[float] = []
    for i, length in enumerate(lengths):
        required = setbacks[i] + setbacks[i + 1]
        if setbacks[i] and setbacks[i + 1]:
            required += minimum_straight_mm
        margin = length - required
        margins.append(margin)
        if margin < -tolerance_mm:
            errors.append(
                f"INSUFFICIENT_TANGENT_LENGTH:{i}:available={length:.6g}:required={required:.6g}"
            )
    for i in range(len(pts) - 1):
        for j in range(i + 2, len(pts) - 1):
            if _segment_distance(pts[i], pts[i + 1], pts[j], pts[j + 1]) <= tolerance_mm:
                errors.append(f"CENTERLINE_SELF_INTERSECTION:{i}:{j}")
    return RouteManufacturabilityResult(
        not errors, tuple(errors), tuple(setbacks), tuple(margins), tuple(bends))


def _sub(a: Point, b: Point) -> Point: return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def _dot(a: Point, b: Point) -> float: return sum(x*y for x, y in zip(a, b))
def _add(a: Point, b: Point) -> Point: return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def _scale(a: Point, value: float) -> Point: return (a[0]*value, a[1]*value, a[2]*value)
def _cross(a: Point, b: Point) -> Point:
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _unit(v: Point) -> Point | None:
    n = _dot(v, v) ** .5
    return None if n <= 1e-12 else (v[0]/n, v[1]/n, v[2]/n)


def _segment_distance(p1: Point, q1: Point, p2: Point, q2: Point) -> float:
    # Closest points on two finite 3-D segments (Ericson, RTCD).
    d1, d2, r = _sub(q1, p1), _sub(q2, p2), _sub(p1, p2)
    a, e, f = _dot(d1, d1), _dot(d2, d2), _dot(d2, r)
    if a <= 1e-12 and e <= 1e-12: return dist(p1, p2)
    if a <= 1e-12: s, t = 0.0, max(0.0, min(1.0, f/e))
    else:
        c = _dot(d1, r)
        if e <= 1e-12: s, t = max(0.0, min(1.0, -c/a)), 0.0
        else:
            b, den = _dot(d1, d2), a*e-_dot(d1, d2)**2
            s = max(0.0, min(1.0, (b*f-c*e)/den)) if den else 0.0
            t = (b*s+f)/e
            if t < 0: t, s = 0.0, max(0.0, min(1.0, -c/a))
            elif t > 1: t, s = 1.0, max(0.0, min(1.0, (b-c)/a))
    c1 = (p1[0]+d1[0]*s, p1[1]+d1[1]*s, p1[2]+d1[2]*s)
    c2 = (p2[0]+d2[0]*t, p2[1]+d2[1]*t, p2[2]+d2[2]*t)
    return dist(c1, c2)
