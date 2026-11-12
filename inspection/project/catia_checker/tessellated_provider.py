"""Controlled mesh provider for Surface/Shell precision plans.

The caller is responsible for obtaining meshes from CATIA.  This provider
keeps the mesh tolerance/provenance in the resulting deterministic fact.
"""

from __future__ import annotations

from typing import Any, Mapping

from catia_mcp.arrangement_geometry import mesh_interference


def _mesh(entity: Mapping[str, Any]) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    data = entity.get("mesh") or {}
    vertices = [tuple(float(value) for value in point) for point in data.get("vertices_mm", ())]
    triangles = [tuple(int(value) for value in face) for face in data.get("triangles", ())]
    if not vertices or not triangles or any(len(point) != 3 for point in vertices) or any(len(face) != 3 for face in triangles):
        raise ValueError("TESSELLATED mesh requires non-empty XYZ vertices and triangle indices")
    if any(index < 0 or index >= len(vertices) for face in triangles for index in face):
        raise ValueError("TESSELLATED mesh triangle index is out of range")
    return vertices, triangles


def evaluate_tessellated_plan(plan: Mapping[str, Any], *, contact_tolerance_mm: float = 0.01) -> dict[str, Any]:
    if plan.get("method") != "TESSELLATED_SURFACE_INTERSECTION":
        raise ValueError("plan method is not TESSELLATED_SURFACE_INTERSECTION")
    first, second = plan["entity_a"], plan["entity_b"]
    vertices_a, triangles_a = _mesh(first)
    vertices_b, triangles_b = _mesh(second)
    closed_a = str(first.get("geometry_kind", first.get("entity_kind", ""))).upper() == "SOLID"
    closed_b = str(second.get("geometry_kind", second.get("entity_kind", ""))).upper() == "SOLID"
    measured = mesh_interference(vertices_a, triangles_a, vertices_b, triangles_b,
                                 contact_tolerance_mm, closed1=closed_a, closed2=closed_b)
    return {
        "object_a": plan["object_a"], "object_b": plan["object_b"],
        "entity_a": first, "entity_b": second,
        "intersects": measured["state"] == "INTERFERENCE" and bool(measured["intersection_points_mm"]),
        "contained": measured["contained_component"] is not None,
        "minimum_distance_mm": measured["minimum_surface_distance_mm"],
        "intersection_points_mm": measured["intersection_points_mm"],
        "closest_point_a_mm": measured["closest_point1_mm"],
        "closest_point_b_mm": measured["closest_point2_mm"],
        "mesh_closed": measured["mesh_closed"], "method": "CATIA_TESSELLATED_SURFACE_INTERSECTION",
        "accuracy_note": "Triangle intersection/minimum distance; mesh chord tolerance is recorded by CATIA exporter.",
    }
