"""Conservative pipe-candidate review for dumb STEP/CATIA Body geometry.

The review deliberately excludes straight cylindrical exteriors by default because
bolts, pins and shafts are common false positives.  It never turns appearance into
confirmed engineering semantics or a bend-radius PASS/FAIL decision.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


_CURVED_KINDS = {
    "BSPLINE_CIRCULAR_SWEEP_EXTERIOR_CANDIDATE",
    "CURVED_CYLINDRICAL_EXTERIOR_CANDIDATE",
    "TOROIDAL_BEND_EXTERIOR_CANDIDATE",
}
_COMPOSITE_REASONS = {
    "COMPOSITE_EXTERIOR_REQUIRES_ROUTE_REVIEW",
    "LOCAL_ROUNDING_OR_COMPOSITE_NOT_SUPPORTED_BEND",
}


def _dimensions(bounds: Mapping[str, Any] | None) -> list[float]:
    if not bounds:
        return []
    low, high = bounds.get("min"), bounds.get("max")
    if not low or not high or len(low) != 3 or len(high) != 3:
        return []
    return sorted((max(0.0, float(high[i]) - float(low[i])) for i in range(3)), reverse=True)


def _aspect_ratio(record: Mapping[str, Any]) -> float | None:
    candidate = record.get("candidate") or {}
    value = candidate.get("aspect_ratio") or record.get("aspect_ratio")
    if value is not None:
        return float(value)
    solid = record.get("solid") or {}
    dims = _dimensions(record.get("bounds_mm") or solid.get("bounds_mm"))
    volume = record.get("volume_mm3", solid.get("volume_mm3"))
    area = record.get("surface_area_mm2", solid.get("surface_area_mm2"))
    if dims and volume is not None and area is not None and float(area) > 0:
        effective_diameter = 4.0 * float(volume) / float(area)
        if effective_diameter > 0:
            return dims[0] / effective_diameter
    return dims[0] / dims[1] if len(dims) == 3 and dims[1] > 0 else None


def review_pipe_candidates(
    records: Iterable[Mapping[str, Any]], *,
    minimum_composite_aspect_ratio: float = 3.0,
    minimum_composite_length_mm: float = 20.0,
    include_straight: bool = False,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    rejected_straight: list[dict[str, Any]] = []
    for record in records:
        candidate = dict(record.get("candidate") or {})
        kind = str(candidate.get("geometry_kind", "UNDETERMINED")).upper()
        reason = str(candidate.get("reason", ""))
        aspect = _aspect_ratio(record)
        dimensions = _dimensions(record.get("bounds_mm") or (record.get("solid") or {}).get("bounds_mm"))
        maximum_extent = dimensions[0] if dimensions else None
        body_index = record.get("source_body_index", record.get("body_index"))
        name = record.get("source_body_name", record.get("name"))

        if "STRAIGHT_CYLINDRICAL" in kind and not include_straight:
            rejected_straight.append({
                "body_index": body_index, "name": name, "geometry_kind": kind,
                "reason": "STRAIGHT_CYLINDER_FASTENER_RISK",
            })
            continue

        tier = None
        basis = None
        if kind in _CURVED_KINDS:
            tier = "CURVED_EXTERIOR_GEOMETRY"
            basis = reason or kind
        elif (reason in _COMPOSITE_REASONS or candidate.get("curved_reason") in _COMPOSITE_REASONS):
            if (aspect is not None and aspect >= minimum_composite_aspect_ratio and
                    maximum_extent is not None and maximum_extent >= minimum_composite_length_mm):
                tier = "COMPOSITE_ROUTE_REVIEW"
                basis = "SLENDER_COMPOSITE_CURVED_EXTERIOR"
        elif str(record.get("candidate_type", candidate.get("candidate_type", ""))).upper() == "PIPE":
            tier = "MULTI_FEATURE_PIPE_CANDIDATE"
            basis = "DETERMINISTIC_MULTI_FEATURE_SCORE"

        if not tier:
            continue
        candidates.append({
            "body_index": body_index,
            "name": name,
            "status": "NOT_EVALUATED",
            "evidence_tier": tier,
            "geometry_kind": kind,
            "basis": basis,
            "aspect_ratio": aspect,
            "outer_diameter_mm": candidate.get("outer_diameter_mm"),
            "centerline_bend_radius_mm": candidate.get("centerline_bend_radius_mm"),
            "radius_ratio_r_over_d": candidate.get("minimum_radius_ratio_r_over_d"),
            "engineering_pipe_confirmed": False,
            "design_cavity_confirmed": False,
            "bend_radius_compliance": "NOT_EVALUATED",
            "context_image": record.get("context_image"),
            "detail_image": record.get("detail_image"),
        })

    candidates.sort(key=lambda item: (
        {"CURVED_EXTERIOR_GEOMETRY": 0, "COMPOSITE_ROUTE_REVIEW": 1,
         "MULTI_FEATURE_PIPE_CANDIDATE": 2}.get(item["evidence_tier"], 9),
        item["body_index"] is None,
        item["body_index"] if item["body_index"] is not None else 0,
    ))
    return {
        "schema_version": "pipe-candidate-review.v1",
        "status": "NOT_EVALUATED" if candidates else "NO_CANDIDATE",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "excluded_straight_cylinder_count": len(rejected_straight),
        "excluded_straight_cylinders": rejected_straight,
        "policy": {
            "straight_cylinders_are_pipes": False,
            "appearance_confirms_engineering_pipe": False,
            "missing_cavity_implies_failure": False,
            "uncertain_bend_radius_status": "NOT_EVALUATED",
        },
    }
