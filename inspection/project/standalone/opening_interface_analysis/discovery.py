"""Discover adapter inputs from existing exact-face inventory records."""

from __future__ import annotations

from itertools import product
from typing import Any, Mapping

from .wall_thickness import infer_wall_thickness_from_opening_pairs


def _axis_limits(bounds: Mapping[str, Any], origin: list[float], axis: list[float]) -> list[float] | None:
    minimum, maximum = bounds.get("min"), bounds.get("max")
    if not (isinstance(minimum, list) and isinstance(maximum, list)
            and len(minimum) == len(maximum) == 3):
        return None
    values = [sum((corner[i] - origin[i]) * axis[i] for i in range(3))
              for corner in product(*[(float(minimum[i]), float(maximum[i])) for i in range(3)])]
    return [min(values), max(values)]


def discover_adapter_payload(inventory: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    """Route analytic cylinders and explicit circular openings without guessing."""
    records = inventory.get("faces") or inventory.get("shapes") or inventory.get("entities") or []
    if not isinstance(records, list):
        raise ValueError("inventory must contain faces, shapes, or entities list")
    opening_faces, cylinders, skipped = [], [], []
    for index, raw in enumerate(records, 1):
        if not isinstance(raw, Mapping):
            skipped.append({"index": index, "reason": "NOT_AN_OBJECT"}); continue
        features = raw.get("surface_features") if isinstance(raw.get("surface_features"), Mapping) else raw
        source_id = str(raw.get("face_id") or raw.get("shape_id") or raw.get("source_id") or f"ITEM-{index}")
        boundaries = features.get("circular_inner_boundaries")
        if isinstance(boundaries, list) and boundaries:
            opening_faces.append({"face_id": source_id,
                                  "normal": features.get("normal"),
                                  "host_wall_thickness_mm": features.get("host_wall_thickness_mm"),
                                  "host_discontinuity_confirmed": features.get("host_discontinuity_confirmed"),
                                  "exact_brep": True,
                                  "circular_inner_boundaries": boundaries,
                                  "source_body_index": raw.get("source_body_index"),
                                  "source_body_name": raw.get("source_body_name"),
                                  "catia_face_reference": raw.get("catia_face_reference"),
                                  "centroid_mm": features.get("centroid_mm") or raw.get("centroid_mm"),
                                  "surface_area_mm2": features.get("surface_area_mm2") or raw.get("surface_area_mm2")})
        if str(features.get("surface_type") or "").upper() != "CYLINDER":
            if not boundaries:
                skipped.append({"source_id": source_id, "reason": "NO_OPENING_OR_CYLINDER"})
            continue
        origin, axis = features.get("axis_origin_mm"), features.get("axis_direction")
        bounds = raw.get("bounds_mm") or raw.get("world_bounds") or {}
        limits = None
        if isinstance(origin, list) and isinstance(axis, list) and len(origin) == len(axis) == 3:
            limits = _axis_limits(bounds, [float(x) for x in origin], [float(x) for x in axis])
        cylinders.append({"surface_id": source_id,
                          "component_id": raw.get("logical_component_id") or raw.get("parent_body_id"),
                          "surface_type": "CYLINDER", "axis_origin_mm": origin,
                          "axis_direction": axis, "radius_mm": features.get("radius_mm"),
                          "axis_limits_mm": limits, "exact_brep": True,
                          "source_body_index": raw.get("source_body_index"),
                          "source_body_name": raw.get("source_body_name"),
                          "catia_face_reference": raw.get("catia_face_reference"),
                          "centroid_mm": features.get("centroid_mm") or raw.get("centroid_mm"),
                          "surface_area_mm2": features.get("surface_area_mm2") or raw.get("surface_area_mm2")})
    thickness = infer_wall_thickness_from_opening_pairs(opening_faces)
    opening_faces = thickness["analysis_opening_face_records"]
    readiness_codes = []
    if not opening_faces:
        readiness_codes.append("NO_RELIABLE_OPENING_EVIDENCE")
    if not cylinders:
        readiness_codes.append("NO_ANALYTIC_CYLINDER_EVIDENCE")
    return {"schema_version": "opening-interface-discovery.v1.0",
            "adapter_payload": {"source": source, "opening_face_records": opening_faces,
                                "cylindrical_surface_records": cylinders},
            "opening_face_count": len(opening_faces), "cylindrical_surface_count": len(cylinders),
            "ready_for_adapter": bool(opening_faces and cylinders),
            "readiness_codes": readiness_codes,
            "wall_thickness_inference": thickness,
            "skipped": skipped, "mesh_used": False}
