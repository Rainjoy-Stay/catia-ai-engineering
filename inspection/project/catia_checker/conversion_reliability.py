"""Conservative STEP conversion-reliability signals."""

from __future__ import annotations

from typing import Any, Mapping


def conversion_signal(record: Mapping[str, Any]) -> dict[str, Any]:
    """Flag only evidence-backed hollow-to-solid suspicions; never declare certainty."""
    semantic = str(record.get("semantic_role", "")).upper()
    expected_hollow = bool(record.get("expected_hollow") or record.get("expected_containment"))
    inner_surface = bool(record.get("inner_surface_present", record.get("inner_boundary_present", False)))
    solid = str(record.get("geometry_kind", "")).upper() == "SOLID"
    outer_radius = record.get("outer_radius_mm")
    inner_radius = record.get("inner_radius_mm")
    wall_thickness = record.get("wall_thickness_mm")
    nested_pipe = bool(record.get("contained_pipe") or record.get("contained_component"))
    dimensional_evidence = (
        isinstance(outer_radius, (int, float)) and isinstance(inner_radius, (int, float))
        and float(outer_radius) > float(inner_radius) >= 0
    )
    signal = expected_hollow and solid and not inner_surface
    reasons = []
    if expected_hollow:
        reasons.append("EXPECTED_HOLLOW_OR_CONTAINMENT")
    if solid:
        reasons.append("IMPORTED_AS_SOLID")
    if not inner_surface:
        reasons.append("INNER_BOUNDARY_NOT_EVIDENCED")
    if dimensional_evidence:
        reasons.append("OUTER_INNER_RADIUS_RELATIONSHIP")
    if isinstance(wall_thickness, (int, float)) and float(wall_thickness) > 0:
        reasons.append("WALL_THICKNESS_EVIDENCE")
    if nested_pipe:
        reasons.append("CONTAINED_PIPE_EVIDENCE")
    evidence_count = sum(item in reasons for item in ("OUTER_INNER_RADIUS_RELATIONSHIP",
                                                       "WALL_THICKNESS_EVIDENCE",
                                                       "CONTAINED_PIPE_EVIDENCE"))
    return {
        "source_id": record.get("source_id"),
        "suspected_conversion_error": signal,
        "conversion_issue": "HOLLOW_TO_SOLID" if signal else None,
        "result": "REVIEW" if signal else "PASS",
        "reasons": reasons if signal else [],
        "confidence": "HIGH" if signal and evidence_count >= 2 else "MEDIUM" if signal and evidence_count else "LOW" if signal else "NONE",
        "semantic_role": semantic or None,
    }
