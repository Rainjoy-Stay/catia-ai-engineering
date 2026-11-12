"""Deterministic health classification for Shell/Surface geometry records."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def classify_shell_health(record: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(record.get("geometry_kind", record.get("entity_kind", "UNKNOWN"))).upper()
    closure = str(record.get("closure_state", "UNKNOWN")).upper()
    valid = record.get("valid", record.get("geometry_state") not in {"INVALID", "UNAVAILABLE"})
    non_manifold = bool(record.get("non_manifold", False))
    bad_faces = int(record.get("bad_face_count", 0) or 0)
    zero_volume = float(record.get("volume_mm3", 0.0) or 0.0) == 0.0
    issues: list[str] = []
    if not valid:
        issues.append("INVALID_GEOMETRY")
    if non_manifold:
        issues.append("NON_MANIFOLD")
    if bad_faces:
        issues.append("BAD_FACE")
    if kind in {"SURFACE", "FACE", "SHELL"} and closure == "OPEN":
        issues.append("OPEN_SHELL")
    reliability = "HIGH"
    if issues:
        reliability = "LOW" if any(item in issues for item in ("INVALID_GEOMETRY", "NON_MANIFOLD")) else "MEDIUM"
    return {
        "source_id": record.get("source_id", record.get("face_id")),
        "geometry_kind": kind,
        "closure_state": closure,
        "zero_volume": zero_volume,
        "issues": issues,
        "model_reliability": reliability,
        "participates_in_spatial_checks": bool(valid and not record.get("reference_geometry", False)),
        "result": "REVIEW" if issues else "PASS",
    }


def build_shell_health(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    results = [classify_shell_health(item) for item in records]
    review_count = sum(item["result"] == "REVIEW" for item in results)
    return {
        "schema_version": "shell-health.v1.0",
        "record_count": len(results),
        "review_count": review_count,
        "model_reliability": "LOW" if any(item["model_reliability"] == "LOW" for item in results)
        else "MEDIUM" if review_count else "HIGH",
        "records": results,
    }
