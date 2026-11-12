"""Build and verify closed axisymmetric permitted volumes for route planning."""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import cos, pi, sin
from pathlib import Path
from typing import Sequence

from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer


@dataclass(frozen=True)
class AxialSection:
    start_y_mm: float
    end_y_mm: float
    start_radius_mm: float
    end_radius_mm: float

    def __post_init__(self) -> None:
        if self.end_y_mm <= self.start_y_mm:
            raise ValueError("Axial section end must be after its start")
        if min(self.start_radius_mm, self.end_radius_mm) <= 0:
            raise ValueError("Axial section radii must be positive")


def build_axisymmetric_permitted_volume(
    sections: Sequence[AxialSection], output_step: str | Path,
    output_mesh_json: str | Path, *, angular_segments: int = 96,
) -> dict[str, object]:
    """Create one capped, closed solid plus a matching watertight planning mesh."""
    values = tuple(sections)
    if not values:
        raise ValueError("At least one axial section is required")
    for left, right in zip(values, values[1:]):
        if abs(left.end_y_mm - right.start_y_mm) > 1e-7:
            raise ValueError("Axial sections must be contiguous")
        if abs(left.end_radius_mm - right.start_radius_mm) > 1e-7:
            raise ValueError("Adjacent axial-section radii must match")
    if angular_segments < 16:
        raise ValueError("angular_segments must be at least 16")

    shape = None
    for item in values:
        axis = gp_Ax2(gp_Pnt(0.0, item.start_y_mm, 0.0), gp_Dir(0.0, 1.0, 0.0))
        height = item.end_y_mm - item.start_y_mm
        if abs(item.start_radius_mm - item.end_radius_mm) <= 1e-9:
            segment = BRepPrimAPI_MakeCylinder(axis, item.start_radius_mm, height).Shape()
        else:
            segment = BRepPrimAPI_MakeCone(
                axis, item.start_radius_mm, item.end_radius_mm, height).Shape()
        if shape is None:
            shape = segment
        else:
            fused = BRepAlgoAPI_Fuse(shape, segment)
            fused.Build()
            if not fused.IsDone():
                raise RuntimeError("OCCT failed to fuse permitted-volume sections")
            shape = fused.Shape()
    if shape is None or shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():
        raise RuntimeError("OCCT produced an invalid permitted volume")

    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    volume = float(properties.Mass())
    expected = sum(
        pi * (item.end_y_mm-item.start_y_mm) *
        (item.start_radius_mm**2 + item.start_radius_mm*item.end_radius_mm +
         item.end_radius_mm**2) / 3.0
        for item in values
    )
    if abs(volume-expected) > max(1e-4, expected*1e-9):
        raise RuntimeError("Permitted-volume B-Rep does not match analytic volume")

    step_path = Path(output_step).resolve()
    mesh_path = Path(output_mesh_json).resolve()
    step_path.parent.mkdir(parents=True, exist_ok=True)
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    if writer.Write(str(step_path)) != IFSelect_RetDone:
        raise RuntimeError("OCCT failed to write permitted-volume STEP")

    stations = [(values[0].start_y_mm, values[0].start_radius_mm)]
    stations.extend((item.end_y_mm, item.end_radius_mm) for item in values)
    vertices = [
        [radius*cos(2*pi*i/angular_segments), y,
         radius*sin(2*pi*i/angular_segments)]
        for y, radius in stations for i in range(angular_segments)
    ]
    triangles: list[list[int]] = []
    for station in range(len(stations)-1):
        a = station*angular_segments
        b = (station+1)*angular_segments
        for i in range(angular_segments):
            j = (i+1) % angular_segments
            triangles.extend(([a+i, b+i, b+j], [a+i, b+j, a+j]))
    start_center, end_center = len(vertices), len(vertices)+1
    vertices.extend(([0.0, stations[0][0], 0.0], [0.0, stations[-1][0], 0.0]))
    last = (len(stations)-1)*angular_segments
    for i in range(angular_segments):
        j = (i+1) % angular_segments
        triangles.extend(([start_center, i, j], [end_center, last+j, last+i]))
    mesh_path.write_text(json.dumps({
        "schema_version": "closed-permitted-volume-mesh.v1.0",
        "component": "Part2.1::INNER_CAVITY",
        "closed": True,
        "geometry_authority": "ANALYTIC_PROFILE_CROSS_CHECKED_WITH_OCCT_BREP",
        "vertices": vertices,
        "triangles": triangles,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "OK", "closed": True, "valid_brep": True,
        "step_file": str(step_path), "mesh_file": str(mesh_path),
        "volume_mm3": volume, "analytic_volume_mm3": expected,
        "sections": [item.__dict__ for item in values],
        "cap_count": 2, "angular_segments": angular_segments,
    }
