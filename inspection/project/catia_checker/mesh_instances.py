"""Instantiate one CATPart tessellation for every assembly occurrence in WORLD space."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .geometry_coordinates import transform_bounds_to_world


def _apply(matrix: list[float], point: Iterable[float]) -> list[float]:
    x, y, z = (float(value) for value in point)
    return [matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3],
            matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7],
            matrix[8] * x + matrix[9] * y + matrix[10] * z + matrix[11]]


def instantiate_part_mesh(tessellation: Mapping[str, Any], instances: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    mesh = tessellation.get("mesh") or {}
    vertices, triangles, bounds = mesh.get("vertices_mm"), mesh.get("triangles"), mesh.get("bounds_mm")
    if not isinstance(vertices, list) or not isinstance(triangles, list) or bounds is None:
        raise ValueError("tessellation must contain mesh vertices_mm, triangles, and bounds_mm")
    result = []
    for index, instance in enumerate(instances, 1):
        matrix = list((instance.get("world_transform") or {}).get("matrix") or [])
        if len(matrix) != 16:
            raise ValueError("each instance requires world_transform.matrix")
        instance_id = str(instance.get("instance_id") or instance.get("component_path") or f"INSTANCE-{index:04d}")
        result.append({
            "object_id": instance_id, "component_path": instance.get("component_path", instance_id),
            "part_number": instance.get("part_number"), "geometry_kind": instance.get("geometry_kind", "SOLID"),
            "coordinate_space": "WORLD", "bounds_mm": [round(value, 6) for value in transform_bounds_to_world(bounds, matrix)],
            "mesh": {"vertices_mm": [[round(value, 6) for value in _apply(matrix, point)] for point in vertices],
                     "triangles": triangles},
            "capabilities": ["TESSELLATED"], "mesh_source_document": tessellation.get("document"),
            "instance_transform": matrix, "mesh_instance_method": "CATPART_STL_PLUS_PRODUCT_INSTANCE_TRANSFORM",
        })
    return result
