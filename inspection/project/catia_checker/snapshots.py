"""Deterministic regression snapshots for CATIA checker result bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


SNAPSHOT_SCHEMA_VERSION = "catia-checker.snapshot.v1"
DEFAULT_MEASUREMENT_TOLERANCE = 1e-6

_STATUS_RISK = {
    "PASS": 0,
    "EXEMPTED": 0,
    "NOT_EVALUATED": 1,
    "WARN": 2,
    "FAIL": 3,
    "ERROR": 3,
}


def _canonical_objects(finding: Mapping[str, Any]) -> list[str]:
    return sorted(str(value) for value in
                  (finding.get("object_a"), finding.get("object_b")) if value)


def _stable_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    metadata = finding.get("metadata") or {}
    opening = metadata.get("opening_interface") or {}
    stable = {
        "rule_id": finding.get("rule_id"),
        "status": finding.get("status"),
        "severity": finding.get("severity"),
        "objects": _canonical_objects(finding),
        "measured_value": finding.get("measured_value"),
        "limit_value": finding.get("limit_value"),
        "unit": finding.get("unit"),
    }
    if opening:
        stable["geometry_disposition"] = metadata.get("geometry_disposition")
        stable["opening_interface"] = {
            "opening_id": opening.get("opening_id"),
            "nozzle_id": opening.get("nozzle_id"),
            "measurements": dict(opening.get("measurements") or {}),
            "reason_labels": list(opening.get("reason_labels") or []),
        }
    return stable


def create_snapshot(result: Mapping[str, Any]) -> dict[str, Any]:
    """Remove volatile report data while retaining regression-relevant facts."""
    normalized: dict[str, dict[str, Any]] = {}
    for finding in result.get("findings", ()):
        issue_id = str(finding.get("issue_id", "")).strip()
        if not issue_id:
            raise ValueError("Every snapshot finding requires issue_id")
        if issue_id in normalized:
            raise ValueError(f"Duplicate issue_id in snapshot: {issue_id}")
        normalized[issue_id] = _stable_finding(finding)
    source = result.get("source", {})
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "target": {
            "document": result.get("document"),
            "ruleset_id": result.get("ruleset_id"),
            "method": source.get("method"),
            "computation_type": source.get("computation_type"),
            "clearance_mm": source.get("clearance_mm"),
            "scope_component_count": source.get("scope_component_count"),
        },
        "findings": dict(sorted(normalized.items())),
    }


def write_snapshot(snapshot: Mapping[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def load_snapshot(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if value.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported snapshot schema_version: {value.get('schema_version')}")
    return value


def _number_changed(current: Any, baseline: Any, tolerance: float) -> bool:
    if current is None or baseline is None:
        return current != baseline
    try:
        return abs(float(current) - float(baseline)) > tolerance
    except (TypeError, ValueError):
        return current != baseline


def _finding_changes(current: Mapping[str, Any], baseline: Mapping[str, Any],
                     tolerance: float) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for key in ("rule_id", "status", "severity", "objects", "unit"):
        if current.get(key) != baseline.get(key):
            changes[key] = {"before": baseline.get(key), "after": current.get(key)}
    for key in ("measured_value", "limit_value"):
        if _number_changed(current.get(key), baseline.get(key), tolerance):
            changes[key] = {"before": baseline.get(key), "after": current.get(key)}
    if current.get("geometry_disposition") != baseline.get("geometry_disposition"):
        changes["geometry_disposition"] = {
            "before": baseline.get("geometry_disposition"),
            "after": current.get("geometry_disposition")}
    current_opening = current.get("opening_interface")
    baseline_opening = baseline.get("opening_interface")
    if current_opening is not None or baseline_opening is not None:
        opening_changes: dict[str, Any] = {}
        current_opening = current_opening or {}
        baseline_opening = baseline_opening or {}
        for key in ("opening_id", "nozzle_id", "reason_labels"):
            if current_opening.get(key) != baseline_opening.get(key):
                opening_changes[key] = {"before": baseline_opening.get(key),
                                        "after": current_opening.get(key)}
        current_measurements = current_opening.get("measurements") or {}
        baseline_measurements = baseline_opening.get("measurements") or {}
        for key in sorted(set(current_measurements) | set(baseline_measurements)):
            if _number_changed(current_measurements.get(key), baseline_measurements.get(key),
                               tolerance):
                opening_changes[f"measurements.{key}"] = {
                    "before": baseline_measurements.get(key),
                    "after": current_measurements.get(key)}
        if opening_changes:
            changes["opening_interface"] = opening_changes
    return changes


def _finding_risk(item: Mapping[str, Any]) -> int:
    geometry = item.get("geometry_disposition")
    if geometry is not None:
        return {"PASS": 0, "REVIEW": 2, "FAIL": 3}.get(str(geometry), 3)
    return _STATUS_RISK.get(str(item.get("status")), 3)


def compare_snapshots(current: Mapping[str, Any], baseline: Mapping[str, Any], *,
                      measurement_tolerance: float = DEFAULT_MEASUREMENT_TOLERANCE) -> dict[str, Any]:
    """Compare two normalized snapshots by stable Issue ID."""
    if current.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("Current snapshot schema is unsupported")
    if baseline.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("Baseline snapshot schema is unsupported")
    current_findings = current.get("findings", {})
    baseline_findings = baseline.get("findings", {})
    current_ids, baseline_ids = set(current_findings), set(baseline_findings)
    added = sorted(current_ids - baseline_ids)
    resolved = sorted(baseline_ids - current_ids)
    persistent: list[str] = []
    changed: list[dict[str, Any]] = []
    regressions: list[str] = []
    improvements: list[str] = []

    for issue_id in sorted(current_ids & baseline_ids):
        current_item = current_findings[issue_id]
        baseline_item = baseline_findings[issue_id]
        changes = _finding_changes(current_item, baseline_item, measurement_tolerance)
        if not changes:
            persistent.append(issue_id)
            continue
        changed.append({"issue_id": issue_id, "changes": changes})
        before_risk = _finding_risk(baseline_item)
        after_risk = _finding_risk(current_item)
        if after_risk > before_risk:
            regressions.append(issue_id)
        elif after_risk < before_risk:
            improvements.append(issue_id)

    for issue_id in added:
        if _finding_risk(current_findings[issue_id]) >= 2:
            regressions.append(issue_id)

    target_changes: dict[str, Any] = {}
    current_target = current.get("target", {})
    baseline_target = baseline.get("target", {})
    for key in ("document", "ruleset_id", "method", "computation_type",
                "clearance_mm", "scope_component_count"):
        if current_target.get(key) != baseline_target.get(key):
            target_changes[key] = {
                "before": baseline_target.get(key), "after": current_target.get(key)
            }
    return {
        "schema_version": "catia-checker.comparison.v1",
        "target": current.get("target", {}),
        "baseline_target": baseline.get("target", {}),
        "target_changed": bool(target_changes),
        "target_changes": target_changes,
        "summary": {
            "added": len(added), "resolved": len(resolved),
            "persistent": len(persistent), "changed": len(changed),
            "regressions": len(regressions), "improvements": len(improvements),
        },
        "added": added,
        "resolved": resolved,
        "persistent": persistent,
        "changed": changed,
        "regressions": sorted(set(regressions)),
        "improvements": sorted(set(improvements)),
        "has_regressions": bool(regressions),
    }
