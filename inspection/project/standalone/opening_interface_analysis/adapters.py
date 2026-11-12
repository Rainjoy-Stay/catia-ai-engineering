"""Normalize CATIA SPA or OCCT analytic records without inventing geometry."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

from .cylinders import merge_coaxial_cylinders


def _vector(value: Any) -> list[float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 3:
        return None
    try:
        result = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    return result if all(math.isfinite(item) for item in result) else None


def _number(value: Any, *, positive: bool = False) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or (positive and result <= 0):
        return None
    return result


def _source_locator(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    index, name = raw.get("source_body_index"), raw.get("source_body_name")
    if isinstance(index, int) and index > 0 and isinstance(name, str) and name:
        return {"source_body_index": index, "source_body_name": name,
                "face_id": raw.get("face_id") or raw.get("surface_id"),
                "face_reference": raw.get("catia_face_reference"),
                "face_centroid_mm": raw.get("centroid_mm"),
                "face_area_mm2": raw.get("surface_area_mm2")}
    return None


def _opening_records(records: Iterable[Mapping[str, Any]], source: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted, rejected = [], []
    for parent_index, raw in enumerate(records, 1):
        parent_id = str(raw.get("face_id") or raw.get("surface_id") or f"FACE-{parent_index}")
        boundaries = raw.get("circular_inner_boundaries")
        if not isinstance(boundaries, list) or not boundaries:
            rejected.append({"source_id": parent_id, "object_type": "OPENING",
                             "reason": "NO_CIRCULAR_INNER_BOUNDARIES"})
            continue
        for boundary_index, boundary in enumerate(boundaries, 1):
            if not isinstance(boundary, Mapping):
                rejected.append({"source_id": parent_id, "object_type": "OPENING",
                                 "reason": "INVALID_BOUNDARY_RECORD"})
                continue
            boundary_id = str(boundary.get("boundary_id") or f"{parent_id}/OPENING-{boundary_index}")
            center = _vector(boundary.get("center_mm"))
            normal = _vector(boundary.get("normal") or raw.get("normal"))
            radius = _number(boundary.get("radius_mm"), positive=True)
            missing = [name for name, value in (("CENTER", center), ("NORMAL", normal),
                                                 ("RADIUS", radius)) if value is None]
            if missing:
                rejected.append({"source_id": boundary_id, "object_type": "OPENING",
                                 "reason": "MISSING_" + "_".join(missing)})
                continue
            accepted.append({"opening_id": boundary_id, "host_face_id": parent_id,
                             "center_mm": center, "normal": normal, "radius_mm": radius,
                             "host_wall_thickness_mm": _number(raw.get("host_wall_thickness_mm"), positive=True),
                             "boundary_complete": boundary.get("closed") is True,
                             "host_discontinuity_confirmed": raw.get("host_discontinuity_confirmed") is True,
                             "exact_brep": raw.get("exact_brep") is True and boundary.get("exact_brep", True) is True,
                             "evidence_source": source,
                             "source_locator": _source_locator(raw)})
    return accepted, rejected


def _nozzle_records(records: Iterable[Mapping[str, Any]], source: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted, rejected = [], []
    for index, raw in enumerate(records, 1):
        source_id = str(raw.get("face_id") or raw.get("surface_id") or raw.get("shape_id") or
                        f"CYLINDER-{index}")
        surface_type = str(raw.get("surface_type") or "").upper()
        if surface_type != "CYLINDER":
            rejected.append({"source_id": source_id, "object_type": "NOZZLE",
                             "reason": "NOT_ANALYTIC_CYLINDER"})
            continue
        point = _vector(raw.get("axis_origin_mm") or raw.get("axis_point_mm"))
        direction = _vector(raw.get("axis_direction"))
        radius = _number(raw.get("outer_radius_mm", raw.get("radius_mm")), positive=True)
        limits = raw.get("axis_limits_mm")
        start = end = None
        if isinstance(limits, Sequence) and not isinstance(limits, (str, bytes)) and len(limits) == 2:
            start, end = _number(limits[0]), _number(limits[1])
        else:
            start = _number(raw.get("axis_start_mm", 0.0))
            end = _number(raw.get("axis_end_mm"))
        missing = [name for name, value in (("AXIS_POINT", point), ("AXIS_DIRECTION", direction),
                                             ("RADIUS", radius), ("AXIAL_LIMITS", end))
                   if value is None]
        if missing:
            rejected.append({"source_id": source_id, "object_type": "NOZZLE",
                             "reason": "MISSING_" + "_".join(missing)})
            continue
        accepted.append({"surface_id": source_id, "component_id": raw.get("component_id"),
                         "axis_point_mm": point, "axis_direction": direction,
                         "surface_radius_mm": radius,
                         "axis_start_mm": start, "axis_end_mm": end,
                         "exact_brep": raw.get("exact_brep") is True,
                         "evidence_source": source,
                         "source_locator": _source_locator(raw)})
    return accepted, rejected


def adapt_exact_geometry(*, opening_face_records: Iterable[Mapping[str, Any]],
                         cylindrical_surface_records: Iterable[Mapping[str, Any]],
                         source: str) -> dict[str, Any]:
    """Build analyzer inputs and an explicit rejection log from exact records."""
    if source not in {"CATIA_SPA", "OCCT_BREP"}:
        raise ValueError("source must be CATIA_SPA or OCCT_BREP")
    openings, opening_rejected = _opening_records(opening_face_records, source)
    cylinder_surfaces, nozzle_rejected = _nozzle_records(cylindrical_surface_records, source)
    merge = merge_coaxial_cylinders(cylinder_surfaces)
    nozzles = [{**item, "evidence_source": source} for item in merge["nozzles"]]
    rejected = opening_rejected + nozzle_rejected
    return {"schema_version": "opening-interface-adapter.v1.0",
            "source": source, "openings": openings, "nozzles": nozzles,
            "accepted_opening_count": len(openings), "accepted_nozzle_count": len(nozzles),
            "cylinder_merge": merge,
            "rejected_count": len(rejected), "rejected": rejected,
            "ready_for_analysis": bool(openings and nozzles),
            "mesh_used": False}
