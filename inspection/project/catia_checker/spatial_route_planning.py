"""Mesh-driven free-space routing for CATIA tubing centerlines.

Unlike the phase-one AABB planner, this module classifies grid cells directly
from tessellated triangles.  It does not depend on sketches or feature
parameters.  Exact port normals are retained as mandatory terminal leads.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from math import ceil, floor, sqrt
from typing import Iterable, Sequence

from .route_manufacturability import validate_polyline_route

Point = tuple[float, float, float]
Cell = tuple[int, int, int]
Triangle = tuple[int, int, int]


@dataclass(frozen=True)
class TriangleMesh:
    name: str
    vertices: tuple[Point, ...]
    triangles: tuple[Triangle, ...]

    @property
    def bounds(self) -> tuple[Point, Point]:
        return (
            tuple(min(p[i] for p in self.vertices) for i in range(3)),
            tuple(max(p[i] for p in self.vertices) for i in range(3)),
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class SurfacePort:
    point: Point
    normal: Point
    lead_length_mm: float

    def __post_init__(self) -> None:
        length = _norm(self.normal)
        if length <= 1e-9:
            raise ValueError("Port normal must be non-zero")
        if self.lead_length_mm <= 0:
            raise ValueError("Port lead length must be positive")

    def lead(self, sign: int) -> Point:
        unit = _scale(self.normal, 1.0 / _norm(self.normal))
        return _add(self.point, _scale(unit, sign * self.lead_length_mm))


@dataclass(frozen=True)
class SpatialRouteRequest:
    boundary_mesh: TriangleMesh
    obstacle_meshes: tuple[TriangleMesh, ...]
    start: SurfacePort
    goal: SurfacePort
    grid_size_mm: float = 8.0
    pipe_outer_diameter_mm: float = 10.0
    clearance_mm: float = 3.0
    bend_penalty_mm: float = 20.0
    bend_radius_mm: float | None = None
    minimum_straight_mm: float = 0.0
    candidate_count: int = 4
    max_expanded_cells: int = 400_000
    boundary_is_closed_permitted_volume: bool = False


@dataclass(frozen=True)
class SpatialRouteResult:
    status: str
    points: tuple[Point, ...] = ()
    start_normal_sign: int = 0
    goal_normal_sign: int = 0
    expanded_cells: int = 0
    blocked_cells: int = 0
    message: str = ""
    objective_score: float | None = None
    candidate_count: int = 0
    alternatives: tuple[tuple[Point, ...], ...] = ()
    candidate_scores: tuple[float, ...] = ()


class MeshFreeSpacePlanner:
    """A* over free cells classified from triangle-to-cell distance."""

    _moves: tuple[Cell, ...] = (
        (1, 0, 0), (-1, 0, 0), (0, 1, 0),
        (0, -1, 0), (0, 0, 1), (0, 0, -1),
    )

    def plan(self, request: SpatialRouteRequest) -> SpatialRouteResult:
        if request.grid_size_mm <= 0:
            raise ValueError("grid_size_mm must be positive")
        if request.bend_radius_mm is not None and request.bend_radius_mm <= 0:
            raise ValueError("bend_radius_mm must be positive when supplied")
        if request.minimum_straight_mm < 0:
            raise ValueError("minimum_straight_mm cannot be negative")
        if request.candidate_count <= 0:
            raise ValueError("candidate_count must be positive")
        inflation = request.pipe_outer_diameter_mm / 2.0 + request.clearance_mm
        origin, upper = request.boundary_mesh.bounds
        shape = tuple(
            int(floor((upper[i] - origin[i]) / request.grid_size_mm)) + 1
            for i in range(3)
        )
        blocked = self._surface_cells(
            request.boundary_mesh, origin, shape, request.grid_size_mm, inflation)
        if request.boundary_is_closed_permitted_volume:
            raw_surface = self._surface_cells(
                request.boundary_mesh, origin, shape, request.grid_size_mm, 1e-7)
            interior = self._closed_mesh_interior(
                request.boundary_mesh, raw_surface, origin, shape, request.grid_size_mm)
            if not interior:
                raise ValueError(
                    "Closed permitted-volume boundary has no classifiable interior cells")
            blocked.update(
                (x, y, z)
                for x in range(shape[0])
                for y in range(shape[1])
                for z in range(shape[2])
                if (x, y, z) not in interior
            )
        for mesh in request.obstacle_meshes:
            surface = self._surface_cells(mesh, origin, shape, request.grid_size_mm, inflation)
            blocked.update(surface)
            blocked.update(self._closed_mesh_interior(
                mesh, surface, origin, shape, request.grid_size_mm))

        total_expanded = 0
        rejected: list[str] = []
        candidates: list[tuple[float, tuple[Point, ...], int, int]] = []
        for start_sign in (1, -1):
            start_lead = request.start.lead(start_sign)
            start_cell = self._cell(start_lead, origin, request.grid_size_mm)
            for goal_sign in (1, -1):
                goal_lead = request.goal.lead(goal_sign)
                goal_cell = self._cell(goal_lead, origin, request.grid_size_mm)
                opened = set(blocked)
                # The terminal surfaces belong to the equipment mesh.  Open
                # only a narrow capsule around each mandatory normal lead.
                self._open_terminal(opened, request.start.point, start_lead,
                                    origin, shape, request.grid_size_mm, inflation)
                self._open_terminal(opened, request.goal.point, goal_lead,
                                    origin, shape, request.grid_size_mm, inflation)
                if not self._inside(start_cell, shape) or not self._inside(goal_cell, shape):
                    continue
                opened.discard(start_cell)
                opened.discard(goal_cell)
                used_edges: set[tuple[Cell, Cell]] = set()
                for _ in range(2):
                    remaining = request.max_expanded_cells - total_expanded
                    if remaining <= 0 or len(candidates) >= request.candidate_count:
                        break
                    path, expanded = self._search(
                        start_cell, goal_cell, opened, shape,
                        request.bend_penalty_mm / request.grid_size_mm,
                        (0 if request.bend_radius_mm is None else ceil(
                            (2.0 * request.bend_radius_mm + request.minimum_straight_mm)
                            / request.grid_size_mm
                        )),
                        remaining, used_edges,
                    )
                    total_expanded += expanded
                    if not path:
                        break
                    used_edges.update(self._edge_key(a, b) for a, b in zip(path, path[1:]))
                    grid_points = [self._world(c, origin, request.grid_size_mm)
                                   for c in self._compress(path)]
                    points = self._dedupe((request.start.point, start_lead,
                                           *grid_points, goal_lead, request.goal.point))
                    points = self._shortcut_free_space(
                        points, opened, origin, shape, request.grid_size_mm)
                    if request.bend_radius_mm is not None:
                        check = validate_polyline_route(
                            points, (request.bend_radius_mm,), request.minimum_straight_mm)
                        if not check.ok:
                            rejected.extend(check.errors)
                            continue
                    score = self._objective_score(points, opened, origin, shape, request)
                    if not any(existing[1] == points for existing in candidates):
                        candidates.append((score, points, start_sign, goal_sign))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]))
            score, points, start_sign, goal_sign = candidates[0]
            return SpatialRouteResult(
                "OK", points, start_sign, goal_sign, total_expanded, len(blocked),
                objective_score=score, candidate_count=len(candidates),
                alternatives=tuple(item[1] for item in candidates[1:]),
                candidate_scores=tuple(item[0] for item in candidates),
            )
        status = "UNMANUFACTURABLE" if rejected else "NO_ROUTE"
        return SpatialRouteResult(
            status, expanded_cells=total_expanded,
            blocked_cells=len(blocked),
            message=("; ".join(dict.fromkeys(rejected)) if rejected else
                     "No connected mesh-classified free-space route was found"),
            candidate_count=0,
        )

    @classmethod
    def _objective_score(
        cls, points: tuple[Point, ...], blocked: set[Cell], origin: Point,
        shape: Cell, request: SpatialRouteRequest,
    ) -> float:
        length = sum(_norm(_sub(b, a)) for a, b in zip(points, points[1:]))
        bends = max(0, len(points) - 2)
        near_obstacle = 0
        for point in points[1:-1]:
            cell = cls._cell(point, origin, request.grid_size_mm)
            if any(
                tuple(cell[k] + move[k] for k in range(3)) in blocked
                for move in cls._moves
            ):
                near_obstacle += 1
        return length + bends * request.bend_penalty_mm + near_obstacle * request.grid_size_mm

    @classmethod
    def _shortcut_free_space(
        cls, points: tuple[Point, ...], blocked: set[Cell], origin: Point,
        shape: Cell, step: float,
    ) -> tuple[Point, ...]:
        """Remove voxel artefacts without changing the two normal port leads."""
        values = list(points)
        changed = True
        while changed and len(values) > 4:
            changed = False
            # Endpoints and the two mandatory normal-lead endpoints are fixed.
            for index in range(2, len(values) - 2):
                if cls._segment_is_free(
                    values[index - 1], values[index + 1], blocked, origin, shape, step
                ):
                    del values[index]
                    changed = True
                    break
        return tuple(values)

    @classmethod
    def _segment_is_free(
        cls, a: Point, b: Point, blocked: set[Cell], origin: Point,
        shape: Cell, step: float,
    ) -> bool:
        length = _norm(_sub(b, a))
        samples = max(1, int(ceil(length / (step * 0.4))))
        for i in range(samples + 1):
            ratio = i / samples
            point = tuple(a[k] + (b[k] - a[k]) * ratio for k in range(3))
            cell = cls._cell(point, origin, step)
            if not cls._inside(cell, shape) or cell in blocked:
                return False
        return True

    def _surface_cells(
        self, mesh: TriangleMesh, origin: Point, shape: Cell,
        step: float, inflation: float,
    ) -> set[Cell]:
        blocked: set[Cell] = set()
        for ia, ib, ic in mesh.triangles:
            a, b, c = mesh.vertices[ia], mesh.vertices[ib], mesh.vertices[ic]
            lo = tuple(min(a[i], b[i], c[i]) - inflation for i in range(3))
            hi = tuple(max(a[i], b[i], c[i]) + inflation for i in range(3))
            ranges = []
            for axis in range(3):
                first = max(0, int(floor((lo[axis] - origin[axis]) / step)))
                last = min(shape[axis] - 1, int(ceil((hi[axis] - origin[axis]) / step)))
                ranges.append(range(first, last + 1))
            for x in ranges[0]:
                for y in ranges[1]:
                    for z in ranges[2]:
                        cell = (x, y, z)
                        if cell in blocked:
                            continue
                        p = self._world(cell, origin, step)
                        if _distance_point_triangle(p, a, b, c) <= inflation:
                            blocked.add(cell)
        return blocked

    def _closed_mesh_interior(self, mesh: TriangleMesh, surface: set[Cell],
                              origin: Point, shape: Cell, step: float) -> set[Cell]:
        """Classify closed-solid interiors by indexed +X ray parity."""
        lo, hi = mesh.bounds
        low = tuple(max(0, floor((lo[i] - origin[i]) / step) - 1) for i in range(3))
        high = tuple(min(shape[i] - 1, ceil((hi[i] - origin[i]) / step) + 1) for i in range(3))
        yz_bins: dict[tuple[int, int], list[tuple[Point, Point, Point]]] = {}
        for ia, ib, ic in mesh.triangles:
            a, b, c = mesh.vertices[ia], mesh.vertices[ib], mesh.vertices[ic]
            y0 = max(low[1], floor((min(a[1], b[1], c[1]) - origin[1]) / step))
            y1 = min(high[1], ceil((max(a[1], b[1], c[1]) - origin[1]) / step))
            z0 = max(low[2], floor((min(a[2], b[2], c[2]) - origin[2]) / step))
            z1 = min(high[2], ceil((max(a[2], b[2], c[2]) - origin[2]) / step))
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    yz_bins.setdefault((y, z), []).append((a, b, c))
        interior: set[Cell] = set()
        for y in range(low[1], high[1] + 1):
            for z in range(low[2], high[2] + 1):
                triangles = yz_bins.get((y, z), ())
                if not triangles:
                    continue
                for x in range(low[0], high[0] + 1):
                    cell = (x, y, z)
                    if cell in surface:
                        continue
                    p = self._world(cell, origin, step)
                    hits = sorted(
                        value for tri in triangles
                        if (value := _ray_x_triangle(p, *tri)) is not None
                    )
                    unique = []
                    for value in hits:
                        if not unique or abs(value - unique[-1]) > 1e-6:
                            unique.append(value)
                    if len(unique) % 2 == 1:
                        interior.add(cell)
        return interior

    def _search(
        self, start: Cell, goal: Cell, blocked: set[Cell], shape: Cell,
        bend_penalty: float, minimum_turn_spacing_steps: int, limit: int,
        penalized_edges: set[tuple[Cell, Cell]] | None = None,
    ) -> tuple[list[Cell] | None, int]:
        serial = count()
        queue: list[tuple[float, int, Cell, Cell | None, int]] = []
        initial_run = minimum_turn_spacing_steps
        heappush(queue, (0.0, next(serial), start, None, initial_run))
        State = tuple[Cell, Cell | None, int]
        best: dict[State, float] = {(start, None, initial_run): 0.0}
        parent: dict[State, State] = {}
        expanded = 0
        final = None
        while queue and expanded < limit:
            _, _, cell, heading, straight_run = heappop(queue)
            state = (cell, heading, straight_run)
            cost = best[state]
            if cell == goal:
                final = state
                break
            expanded += 1
            for move in self._moves:
                if heading is not None and move == tuple(-v for v in heading):
                    continue
                turning = heading is not None and move != heading
                if turning and straight_run < minimum_turn_spacing_steps:
                    continue
                nxt = tuple(cell[i] + move[i] for i in range(3))
                if not self._inside(nxt, shape) or nxt in blocked:
                    continue
                new_cost = cost + 1.0 + (bend_penalty if heading not in (None, move) else 0.0)
                if penalized_edges and self._edge_key(cell, nxt) in penalized_edges:
                    new_cost += 4.0 * bend_penalty
                next_run = (1 if turning else min(
                    straight_run + 1, minimum_turn_spacing_steps
                ))
                next_state = (nxt, move, next_run)
                if new_cost >= best.get(next_state, float("inf")):
                    continue
                best[next_state] = new_cost
                parent[next_state] = state
                h = sum(abs(nxt[i] - goal[i]) for i in range(3))
                heappush(queue, (new_cost + h, next(serial), nxt, move, next_run))
        if final is None:
            return None, expanded
        result = [final[0]]
        while final in parent:
            final = parent[final]
            result.append(final[0])
        result.reverse()
        return result, expanded

    @staticmethod
    def _edge_key(a: Cell, b: Cell) -> tuple[Cell, Cell]:
        return (a, b) if a <= b else (b, a)

    @staticmethod
    def _open_terminal(blocked: set[Cell], a: Point, b: Point, origin: Point,
                       shape: Cell, step: float, radius: float) -> None:
        lo = tuple(min(a[i], b[i]) - radius for i in range(3))
        hi = tuple(max(a[i], b[i]) + radius for i in range(3))
        for x in range(max(0, floor((lo[0] - origin[0]) / step)),
                       min(shape[0] - 1, ceil((hi[0] - origin[0]) / step)) + 1):
            for y in range(max(0, floor((lo[1] - origin[1]) / step)),
                           min(shape[1] - 1, ceil((hi[1] - origin[1]) / step)) + 1):
                for z in range(max(0, floor((lo[2] - origin[2]) / step)),
                               min(shape[2] - 1, ceil((hi[2] - origin[2]) / step)) + 1):
                    cell = (x, y, z)
                    if _distance_point_segment(MeshFreeSpacePlanner._world(cell, origin, step), a, b) <= radius:
                        blocked.discard(cell)

    @staticmethod
    def _cell(point: Point, origin: Point, step: float) -> Cell:
        return tuple(int(round((point[i] - origin[i]) / step)) for i in range(3))  # type: ignore[return-value]

    @staticmethod
    def _world(cell: Cell, origin: Point, step: float) -> Point:
        return tuple(origin[i] + cell[i] * step for i in range(3))  # type: ignore[return-value]

    @staticmethod
    def _inside(cell: Cell, shape: Cell) -> bool:
        return all(0 <= cell[i] < shape[i] for i in range(3))

    @staticmethod
    def _compress(path: Sequence[Cell]) -> list[Cell]:
        if len(path) < 3:
            return list(path)
        result = [path[0]]
        previous = None
        for a, b in zip(path, path[1:]):
            move = tuple(b[i] - a[i] for i in range(3))
            if previous is not None and move != previous:
                result.append(a)
            previous = move
        result.append(path[-1])
        return result

    @staticmethod
    def _dedupe(points: Sequence[Point]) -> tuple[Point, ...]:
        result = []
        for point in points:
            if not result or _norm(_sub(point, result[-1])) > 1e-7:
                result.append(point)
        return tuple(result)


def _add(a: Point, b: Point) -> Point:
    return tuple(a[i] + b[i] for i in range(3))  # type: ignore[return-value]


def _sub(a: Point, b: Point) -> Point:
    return tuple(a[i] - b[i] for i in range(3))  # type: ignore[return-value]


def _scale(a: Point, value: float) -> Point:
    return tuple(v * value for v in a)  # type: ignore[return-value]


def _dot(a: Point, b: Point) -> float:
    return sum(a[i] * b[i] for i in range(3))


def _norm(a: Point) -> float:
    return sqrt(_dot(a, a))


def _distance_point_segment(p: Point, a: Point, b: Point) -> float:
    ab = _sub(b, a)
    denom = _dot(ab, ab)
    t = 0.0 if denom <= 1e-12 else max(0.0, min(1.0, _dot(_sub(p, a), ab) / denom))
    return _norm(_sub(p, _add(a, _scale(ab, t))))


def _distance_point_triangle(p: Point, a: Point, b: Point, c: Point) -> float:
    """Distance using the closest-point regions from Real-Time Collision Detection."""
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return _norm(ap)
    bp = _sub(p, b); d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return _norm(bp)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return _norm(_sub(p, _add(a, _scale(ab, d1 / (d1 - d3)))))
    cp = _sub(p, c); d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return _norm(cp)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return _norm(_sub(p, _add(a, _scale(ac, d2 / (d2 - d6)))))
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        edge = _sub(c, b)
        return _norm(_sub(p, _add(b, _scale(edge, (d4 - d3) / ((d4 - d3) + (d5 - d6))))))
    denom = 1.0 / (va + vb + vc)
    closest = _add(a, _add(_scale(ab, vb * denom), _scale(ac, vc * denom)))
    return _norm(_sub(p, closest))


def _ray_x_triangle(p: Point, a: Point, b: Point, c: Point) -> float | None:
    """Return non-negative distance for a +X ray hit, otherwise None."""
    direction = (1.0, 0.0, 0.0)
    edge1, edge2 = _sub(b, a), _sub(c, a)
    h = (0.0, -edge2[2], edge2[1])  # cross(direction, edge2)
    det = _dot(edge1, h)
    if abs(det) < 1e-10:
        return None
    inv = 1.0 / det
    s = _sub(p, a)
    u = inv * _dot(s, h)
    if u < -1e-9 or u > 1.0 + 1e-9:
        return None
    q = (s[1] * edge1[2] - s[2] * edge1[1],
         s[2] * edge1[0] - s[0] * edge1[2],
         s[0] * edge1[1] - s[1] * edge1[0])
    v = inv * q[0]
    if v < -1e-9 or u + v > 1.0 + 1e-9:
        return None
    distance = inv * _dot(edge2, q)
    return distance if distance >= -1e-9 else None
