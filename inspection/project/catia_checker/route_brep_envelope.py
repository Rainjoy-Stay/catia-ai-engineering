"""Exact OCCT envelope for straight and arbitrary-angle filleted routes."""

from __future__ import annotations

from math import atan, cos, degrees, sin
from pathlib import Path
from typing import Sequence

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe, BRepOffsetAPI_ThruSections
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

from .route_manufacturability import BendGeometry, validate_polyline_route

Point = tuple[float, float, float]


def build_route_envelope_step(
    points: Sequence[Sequence[float]], bend_radii_mm: Sequence[float],
    outer_diameter_mm: float, output_step: str | Path,
    minimum_straight_mm: float = 0.0,
    start_interface_diameter_mm: float | None = None,
    goal_interface_diameter_mm: float | None = None,
    start_reducer_length_mm: float = 0.0,
    goal_reducer_length_mm: float = 0.0,
    maximum_reducer_half_angle_deg: float = 15.0,
) -> dict[str, object]:
    if outer_diameter_mm <= 0:
        raise ValueError("outer_diameter_mm must be positive")
    pts: tuple[Point, ...] = tuple(tuple(map(float, p)) for p in points)  # type: ignore[assignment]
    check = validate_polyline_route(pts, bend_radii_mm, minimum_straight_mm)
    if not check.ok:
        raise ValueError("Unmanufacturable route: " + "; ".join(check.errors))
    start_diameter = float(start_interface_diameter_mm or outer_diameter_mm)
    goal_diameter = float(goal_interface_diameter_mm or outer_diameter_mm)
    if start_diameter <= 0 or goal_diameter <= 0:
        raise ValueError("Interface diameters must be positive")
    first_direction = _unit(_sub(check.bends[0].tangent_start, pts[0]) if check.bends
                            else _sub(pts[-1], pts[0]))
    last_direction = _unit(_sub(pts[-1], check.bends[-1].tangent_end) if check.bends
                           else _sub(pts[-1], pts[0]))
    start_length = _validated_reducer_length(
        start_diameter, outer_diameter_mm, start_reducer_length_mm,
        maximum_reducer_half_angle_deg, "start")
    goal_length = _validated_reducer_length(
        goal_diameter, outer_diameter_mm, goal_reducer_length_mm,
        maximum_reducer_half_angle_deg, "goal")
    start_available = _distance(pts[0], check.bends[0].tangent_start) if check.bends else _distance(pts[0], pts[-1])
    goal_available = _distance(check.bends[-1].tangent_end, pts[-1]) if check.bends else _distance(pts[0], pts[-1])
    if start_length > start_available + 1e-7 or goal_length > goal_available + 1e-7:
        raise ValueError("Reducer does not fit before the nearest bend")
    if not check.bends and start_length + goal_length >= _distance(pts[0], pts[-1]) - 1e-7:
        raise ValueError("Start and goal reducers overlap")
    core_start = _add(pts[0], _scale(first_direction, start_length))
    core_end = _add(pts[-1], _scale(last_direction, -goal_length))
    bend_by_node = {bend.node_index: bend for bend in check.bends}
    edges = []
    cursor = core_start
    for node_index in range(1, len(pts) - 1):
        bend = bend_by_node.get(node_index)
        if bend is None:
            continue
        if _distance(cursor, bend.tangent_start) > 1e-7:
            edges.append(BRepBuilderAPI_MakeEdge(_pnt(cursor), _pnt(bend.tangent_start)).Edge())
        midpoint = _arc_midpoint(bend)
        edges.append(GC_MakeArcOfCircle(
            _pnt(bend.tangent_start), _pnt(midpoint), _pnt(bend.tangent_end)).Value())
        edges[-1] = BRepBuilderAPI_MakeEdge(edges[-1]).Edge()
        cursor = bend.tangent_end
    if _distance(cursor, core_end) > 1e-7:
        edges.append(BRepBuilderAPI_MakeEdge(_pnt(cursor), _pnt(core_end)).Edge())
    if not edges:
        raise ValueError("Route produced no sweep edges")
    spine_builder = BRepBuilderAPI_MakeWire()
    for edge in edges:
        spine_builder.Add(edge)
    if not spine_builder.IsDone():
        raise RuntimeError("OCCT could not build a connected route spine")
    tangent = first_direction
    profile_wire = _circle_wire(core_start, tangent, outer_diameter_mm / 2.0)
    profile_face = BRepBuilderAPI_MakeFace(profile_wire).Face()
    pipe = BRepOffsetAPI_MakePipe(spine_builder.Wire(), profile_face)
    shape = pipe.Shape()
    reducer_count = 0
    if start_length > 0:
        shape = _fuse(shape, _reducer_solid(
            pts[0], core_start, first_direction,
            start_diameter / 2.0, outer_diameter_mm / 2.0))
        reducer_count += 1
    if goal_length > 0:
        shape = _fuse(shape, _reducer_solid(
            core_end, pts[-1], last_direction,
            outer_diameter_mm / 2.0, goal_diameter / 2.0))
        reducer_count += 1
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():
        raise RuntimeError("OCCT produced an invalid route envelope")
    output = Path(output_step).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    if writer.Write(str(output)) != IFSelect_RetDone:
        raise RuntimeError("OCCT failed to write route envelope STEP")
    return {
        "status": "OK", "output_step": str(output),
        "outer_diameter_mm": outer_diameter_mm,
        "bend_count": len(check.bends), "edge_count": len(edges),
        "reducer_count": reducer_count,
        "start_interface_diameter_mm": start_diameter,
        "goal_interface_diameter_mm": goal_diameter,
        "valid_brep": True,
    }


def _validated_reducer_length(
    interface_diameter: float, core_diameter: float, requested_length: float,
    maximum_half_angle_deg: float, label: str,
) -> float:
    if abs(interface_diameter - core_diameter) <= 1e-9:
        return 0.0
    if requested_length <= 0:
        raise ValueError(f"{label} reducer length is required for unequal diameters")
    half_angle = degrees(atan(abs(interface_diameter-core_diameter)/(2.0*requested_length)))
    if half_angle > maximum_half_angle_deg + 1e-9:
        raise ValueError(
            f"{label} reducer half-angle {half_angle:.6g} exceeds {maximum_half_angle_deg:.6g} deg")
    return requested_length


def _circle_wire(center: Point, direction: Point, radius: float):
    circle = gp_Circ(gp_Ax2(_pnt(center), gp_Dir(*direction)), radius)
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()


def _reducer_solid(
    start: Point, end: Point, direction: Point, start_radius: float, end_radius: float,
):
    loft = BRepOffsetAPI_ThruSections(True, False, 1e-7)
    loft.AddWire(_circle_wire(start, direction, start_radius))
    loft.AddWire(_circle_wire(end, direction, end_radius))
    loft.Build()
    if not loft.IsDone():
        raise RuntimeError("OCCT could not build reducer envelope")
    return loft.Shape()


def _fuse(first, second):
    operation = BRepAlgoAPI_Fuse(first, second)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("OCCT could not fuse reducer to route envelope")
    return operation.Shape()


def _arc_midpoint(bend: BendGeometry) -> Point:
    radial = _sub(bend.tangent_start, bend.center)
    angle = bend.angle_deg * 3.141592653589793 / 360.0
    axis = bend.axis
    rotated = _add(
        _add(_scale(radial, cos(angle)), _scale(_cross(axis, radial), sin(angle))),
        _scale(axis, _dot(axis, radial) * (1.0 - cos(angle))),
    )
    return _add(bend.center, rotated)


def _pnt(value: Point) -> gp_Pnt: return gp_Pnt(*value)
def _sub(a: Point, b: Point) -> Point: return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def _add(a: Point, b: Point) -> Point: return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def _scale(a: Point, v: float) -> Point: return (a[0]*v, a[1]*v, a[2]*v)
def _dot(a: Point, b: Point) -> float: return sum(x*y for x, y in zip(a, b))
def _cross(a: Point, b: Point) -> Point:
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _distance(a: Point, b: Point) -> float: return _dot(_sub(a, b), _sub(a, b)) ** .5
def _unit(a: Point) -> Point:
    length = _dot(a, a) ** .5
    if length <= 1e-12: raise ValueError("Zero route tangent")
    return (a[0]/length, a[1]/length, a[2]/length)
