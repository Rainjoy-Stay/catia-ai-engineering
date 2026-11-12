"""Deterministic phase-one orthogonal pipe route planner.

The planner deliberately has no CATIA dependency.  CATIA geometry is reduced to
axis-aligned obstacle boxes before planning; returned points can be passed to
the native Arrangement Run creation operation after engineering review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from math import ceil, floor
from typing import Iterable, Sequence

GridPoint = tuple[int, int, int]
Point3D = tuple[float, float, float]
Direction = tuple[int, int, int]

DIRECTIONS: tuple[Direction, ...] = (
    (1, 0, 0), (-1, 0, 0), (0, 1, 0),
    (0, -1, 0), (0, 0, 1), (0, 0, -1),
)


@dataclass(frozen=True)
class AABB:
    minimum: Point3D
    maximum: Point3D
    name: str = "obstacle"

    def __post_init__(self) -> None:
        if any(lo > hi for lo, hi in zip(self.minimum, self.maximum)):
            raise ValueError(f"Invalid AABB {self.name!r}: minimum exceeds maximum")

    def inflated(self, amount: float) -> "AABB":
        return AABB(
            tuple(v - amount for v in self.minimum),
            tuple(v + amount for v in self.maximum),
            self.name,
        )

    def contains(self, point: Point3D) -> bool:
        return all(lo <= value <= hi for value, lo, hi in zip(point, self.minimum, self.maximum))


@dataclass(frozen=True)
class Port:
    point: Point3D
    direction: Direction
    exit_length_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValueError("Port direction must be one of the six orthogonal unit directions")
        if self.exit_length_mm < 0:
            raise ValueError("Port exit length cannot be negative")

    @property
    def exit_point(self) -> Point3D:
        return tuple(
            self.point[i] + self.direction[i] * self.exit_length_mm for i in range(3)
        )


@dataclass(frozen=True)
class PlanningRequest:
    start: Port
    goal: Port
    obstacles: tuple[AABB, ...] = ()
    grid_size_mm: float = 10.0
    pipe_outer_diameter_mm: float = 20.0
    clearance_mm: float = 10.0
    minimum_straight_mm: float = 20.0
    bend_radius_mm: float = 30.0
    bend_penalty: float = 40.0
    vertical_penalty_per_mm: float = 0.0
    heuristic_weight: float = 1.15
    search_margin_mm: float = 100.0
    max_expanded_states: int = 500_000
    candidate_count: int = 3
    candidate_overlap_penalty: float = 25.0

    def __post_init__(self) -> None:
        positive = {
            "grid_size_mm": self.grid_size_mm,
            "pipe_outer_diameter_mm": self.pipe_outer_diameter_mm,
            "bend_radius_mm": self.bend_radius_mm,
            "heuristic_weight": self.heuristic_weight,
            "search_margin_mm": self.search_margin_mm,
            "max_expanded_states": self.max_expanded_states,
            "candidate_count": self.candidate_count,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.clearance_mm < 0 or self.minimum_straight_mm < 0:
            raise ValueError("Clearance and minimum straight length cannot be negative")


@dataclass(frozen=True)
class RouteCandidate:
    points: tuple[Point3D, ...]
    length_mm: float
    bends: int
    cost: float
    expanded_states: int
    bend_radii_mm: tuple[float, ...]


@dataclass(frozen=True)
class PlanningResult:
    status: str
    candidates: tuple[RouteCandidate, ...] = ()
    message: str = ""
    diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _State:
    point: GridPoint
    direction: Direction
    straight_steps: int


class OrthogonalRoutePlanner:
    """Sparse-grid weighted A* with heading and straight-run state."""

    def plan(self, request: PlanningRequest) -> PlanningResult:
        step = request.grid_size_mm
        start_grid = self._snap(request.start.exit_point, step)
        goal_grid = self._snap(request.goal.exit_point, step)
        for label, exact, snapped in (
            ("start", request.start.exit_point, self._world(start_grid, step)),
            ("goal", request.goal.exit_point, self._world(goal_grid, step)),
        ):
            if any(abs(a - b) > 1e-7 for a, b in zip(exact, snapped)):
                raise ValueError(
                    f"{label} port exit point must align with grid_size_mm; "
                    "adjust the grid size or exit length"
                )
        inflation = request.pipe_outer_diameter_mm / 2.0 + request.clearance_mm
        inflated = tuple(box.inflated(inflation) for box in request.obstacles)
        bounds = self._bounds(request, start_grid, goal_grid)

        fixed_segments = (
            (request.start.point, request.start.exit_point),
            (request.goal.point, request.goal.exit_point),
        )
        for segment in fixed_segments:
            if self._segment_hits_any(segment[0], segment[1], inflated):
                return PlanningResult(
                    "NO_ROUTE", message="A mandatory port exit segment intersects an inflated obstacle",
                    diagnostics={"inflation_mm": inflation},
                )
        if self._blocked(start_grid, step, inflated) or self._blocked(goal_grid, step, inflated):
            return PlanningResult(
                "NO_ROUTE", message="A snapped port exit point lies inside an inflated obstacle",
                diagnostics={"inflation_mm": inflation},
            )

        candidates: list[RouteCandidate] = []
        used_edges: set[tuple[GridPoint, GridPoint]] = set()
        attempts = max(request.candidate_count * 3, request.candidate_count)
        total_expanded = 0
        for attempt in range(attempts):
            found, expanded = self._search(
                request, start_grid, goal_grid, bounds, inflated, used_edges, attempt
            )
            total_expanded += expanded
            if found is None:
                if not candidates:
                    return PlanningResult(
                        "NO_ROUTE", message="Search exhausted without a feasible route",
                        diagnostics={"expanded_states": total_expanded, "inflation_mm": inflation},
                    )
                break
            grid_path, cost = found
            for a, b in zip(grid_path, grid_path[1:]):
                used_edges.add(self._edge_key(a, b))
            world = [self._world(p, step) for p in self._compress(grid_path)]
            points = self._attach_ports(world, request.start, request.goal)
            candidate = self._candidate(points, cost, expanded, request.bend_radius_mm)
            if not any(existing.points == candidate.points for existing in candidates):
                candidates.append(candidate)
            if len(candidates) >= request.candidate_count:
                break

        return PlanningResult(
            "OK", tuple(candidates),
            diagnostics={
                "grid_size_mm": step,
                "inflation_mm": inflation,
                "minimum_straight_steps": ceil(
                    max(request.minimum_straight_mm, request.bend_radius_mm) / step
                ),
                "total_expanded_states": total_expanded,
            },
        )

    def _search(
        self,
        request: PlanningRequest,
        start: GridPoint,
        goal: GridPoint,
        bounds: tuple[GridPoint, GridPoint],
        obstacles: Sequence[AABB],
        used_edges: set[tuple[GridPoint, GridPoint]],
        attempt: int,
    ) -> tuple[tuple[list[GridPoint], float] | None, int]:
        step = request.grid_size_mm
        # For a 90-degree circular bend the tangent setback equals its radius.
        # Requiring at least this much between bends prevents geometrically
        # overlapping elbows before the CATIA realization step.
        min_straight_steps = ceil(
            max(request.minimum_straight_mm, request.bend_radius_mm) / step
        )
        initial_direction = request.start.direction
        initial = _State(start, initial_direction, min_straight_steps)
        queue: list[tuple[float, int, _State]] = []
        serial = count()
        heappush(queue, (0.0, next(serial), initial))
        best: dict[_State, float] = {initial: 0.0}
        parent: dict[_State, _State] = {}
        expanded = 0

        while queue and expanded < request.max_expanded_states:
            _, _, state = heappop(queue)
            current_cost = best[state]
            if state.point == goal and state.direction == self._reverse(request.goal.direction):
                return (self._reconstruct(parent, state), current_cost), expanded
            expanded += 1
            for direction in DIRECTIONS:
                if direction == self._reverse(state.direction):
                    continue
                turning = direction != state.direction
                if turning and state.straight_steps < min_straight_steps:
                    continue
                nxt = tuple(state.point[i] + direction[i] for i in range(3))
                if not self._inside(nxt, bounds) or self._blocked(nxt, step, obstacles):
                    continue
                if self._segment_hits_any(
                    self._world(state.point, step), self._world(nxt, step), obstacles
                ):
                    continue
                if nxt == goal and direction != self._reverse(request.goal.direction):
                    continue
                straight = 1 if turning else min(state.straight_steps + 1, min_straight_steps)
                next_state = _State(nxt, direction, straight)
                edge_cost = step
                if turning:
                    edge_cost += request.bend_penalty
                if direction[2]:
                    edge_cost += request.vertical_penalty_per_mm * step
                if self._edge_key(state.point, nxt) in used_edges:
                    edge_cost += request.candidate_overlap_penalty * (attempt + 1)
                new_cost = current_cost + edge_cost
                if new_cost >= best.get(next_state, float("inf")):
                    continue
                best[next_state] = new_cost
                parent[next_state] = state
                heuristic = self._manhattan(nxt, goal) * step
                heappush(
                    queue,
                    (new_cost + request.heuristic_weight * heuristic, next(serial), next_state),
                )
        return None, expanded

    @staticmethod
    def _snap(point: Point3D, step: float) -> GridPoint:
        return tuple(int(round(value / step)) for value in point)  # type: ignore[return-value]

    @staticmethod
    def _world(point: GridPoint, step: float) -> Point3D:
        return tuple(value * step for value in point)  # type: ignore[return-value]

    @staticmethod
    def _reverse(direction: Direction) -> Direction:
        return tuple(-v for v in direction)  # type: ignore[return-value]

    @staticmethod
    def _manhattan(a: GridPoint, b: GridPoint) -> int:
        return sum(abs(x - y) for x, y in zip(a, b))

    @staticmethod
    def _edge_key(a: GridPoint, b: GridPoint) -> tuple[GridPoint, GridPoint]:
        return (a, b) if a <= b else (b, a)

    @staticmethod
    def _inside(point: GridPoint, bounds: tuple[GridPoint, GridPoint]) -> bool:
        return all(lo <= value <= hi for value, lo, hi in zip(point, bounds[0], bounds[1]))

    @classmethod
    def _blocked(cls, point: GridPoint, step: float, obstacles: Sequence[AABB]) -> bool:
        world = cls._world(point, step)
        return any(box.contains(world) for box in obstacles)

    @classmethod
    def _bounds(
        cls, request: PlanningRequest, start: GridPoint, goal: GridPoint
    ) -> tuple[GridPoint, GridPoint]:
        step = request.grid_size_mm
        points: list[Point3D] = [request.start.point, request.goal.point]
        for box in request.obstacles:
            points.extend((box.minimum, box.maximum))
        margin = ceil(request.search_margin_mm / step)
        grid_points = [cls._snap(p, step) for p in points] + [start, goal]
        minimum = tuple(min(p[i] for p in grid_points) - margin for i in range(3))
        maximum = tuple(max(p[i] for p in grid_points) + margin for i in range(3))
        return minimum, maximum  # type: ignore[return-value]

    @staticmethod
    def _compress(path: Sequence[GridPoint]) -> list[GridPoint]:
        if len(path) <= 2:
            return list(path)
        result = [path[0]]
        previous_direction: Direction | None = None
        for a, b in zip(path, path[1:]):
            direction = tuple(b[i] - a[i] for i in range(3))
            if previous_direction is not None and direction != previous_direction:
                result.append(a)
            previous_direction = direction  # type: ignore[assignment]
        result.append(path[-1])
        return result

    @staticmethod
    def _attach_ports(points: list[Point3D], start: Port, goal: Port) -> tuple[Point3D, ...]:
        merged = [start.point]
        for point in [start.exit_point, *points, goal.exit_point, goal.point]:
            if point != merged[-1]:
                merged.append(point)
        if len(merged) <= 2:
            return tuple(merged)
        simplified = [merged[0]]
        for point in merged[1:]:
            simplified.append(point)
            while len(simplified) >= 3:
                a, b, c = simplified[-3:]
                ab = tuple(b[i] - a[i] for i in range(3))
                bc = tuple(c[i] - b[i] for i in range(3))
                axis_ab = next((i for i, value in enumerate(ab) if value), None)
                axis_bc = next((i for i, value in enumerate(bc) if value), None)
                same_direction = (
                    axis_ab is not None and axis_ab == axis_bc
                    and ab[axis_ab] * bc[axis_bc] > 0
                )
                if not same_direction:
                    break
                simplified.pop(-2)
        return tuple(simplified)

    @staticmethod
    def _candidate(
        points: tuple[Point3D, ...], cost: float, expanded: int, bend_radius: float
    ) -> RouteCandidate:
        length = sum(
            sum(abs(a - b) for a, b in zip(left, right))
            for left, right in zip(points, points[1:])
        )
        bends = max(0, len(points) - 2)
        return RouteCandidate(points, length, bends, cost, expanded, (bend_radius,) * bends)

    @staticmethod
    def _segment_hits_any(a: Point3D, b: Point3D, boxes: Iterable[AABB]) -> bool:
        # Mandatory port segments are orthogonal.  Sample their closed interval
        # analytically against each inflated box.
        changed = [i for i in range(3) if a[i] != b[i]]
        if len(changed) > 1:
            raise ValueError("Port exit segment must be orthogonal")
        for box in boxes:
            axis = changed[0] if changed else 0
            if any(
                not (box.minimum[i] <= a[i] <= box.maximum[i])
                for i in range(3) if i != axis
            ):
                continue
            lo, hi = sorted((a[axis], b[axis]))
            if max(lo, box.minimum[axis]) <= min(hi, box.maximum[axis]):
                return True
        return False

    @staticmethod
    def _reconstruct(parent: dict[_State, _State], state: _State) -> list[GridPoint]:
        result = [state.point]
        while state in parent:
            state = parent[state]
            result.append(state.point)
        result.reverse()
        return result


def request_from_dict(data: dict[str, object]) -> PlanningRequest:
    """Parse the stable JSON boundary used by the CLI and future MCP tool."""

    def point(value: object, label: str) -> Point3D:
        if not isinstance(value, list) or len(value) != 3:
            raise ValueError(f"{label} must contain three numbers")
        return tuple(float(v) for v in value)  # type: ignore[return-value]

    def direction(value: object, label: str) -> Direction:
        result = point(value, label)
        integer = tuple(int(v) for v in result)
        if integer not in DIRECTIONS or any(a != b for a, b in zip(result, integer)):
            raise ValueError(f"{label} must be an orthogonal unit direction")
        return integer  # type: ignore[return-value]

    def port(value: object, label: str) -> Port:
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        return Port(
            point(value.get("point"), f"{label}.point"),
            direction(value.get("direction"), f"{label}.direction"),
            float(value.get("exit_length_mm", 0.0)),
        )

    raw_obstacles = data.get("obstacles", [])
    if not isinstance(raw_obstacles, list):
        raise ValueError("obstacles must be a list")
    obstacles = []
    for index, raw in enumerate(raw_obstacles):
        if not isinstance(raw, dict):
            raise ValueError(f"obstacles[{index}] must be an object")
        obstacles.append(AABB(
            point(raw.get("minimum"), f"obstacles[{index}].minimum"),
            point(raw.get("maximum"), f"obstacles[{index}].maximum"),
            str(raw.get("name", f"obstacle-{index + 1}")),
        ))

    kwargs = {
        key: data[key] for key in (
            "grid_size_mm", "pipe_outer_diameter_mm", "clearance_mm",
            "minimum_straight_mm", "bend_radius_mm", "bend_penalty",
            "vertical_penalty_per_mm", "heuristic_weight", "search_margin_mm",
            "max_expanded_states", "candidate_count", "candidate_overlap_penalty",
        ) if key in data
    }
    return PlanningRequest(
        start=port(data.get("start"), "start"),
        goal=port(data.get("goal"), "goal"),
        obstacles=tuple(obstacles),
        **kwargs,  # type: ignore[arg-type]
    )


def result_to_dict(result: PlanningResult) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "status": result.status,
        "message": result.message,
        "diagnostics": result.diagnostics,
        "candidates": [
            {
                "rank": index,
                "points_mm": [list(point) for point in candidate.points],
                "bend_radii_mm": list(candidate.bend_radii_mm),
                "section_diameter_mm": None,
                "length_mm": candidate.length_mm,
                "bend_count": candidate.bends,
                "search_cost": candidate.cost,
                "expanded_states": candidate.expanded_states,
                "catia_target": "native Arrangement Run centerline",
            }
            for index, candidate in enumerate(result.candidates, 1)
        ],
    }
