"""Safety invariants for reports enriched by the model-understanding layer."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


def validate_semantic_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Validate fail-closed behavior without requiring labelled production data."""
    findings = list(report.get("findings") or [])
    dmu_findings = [item for item in findings if any(
        evidence.get("kind") == "CATIA_CLASH" for evidence in (item.get("evidence") or []))]
    violations: list[dict[str, Any]] = []
    dispositions: Counter[str] = Counter()

    for finding in dmu_findings:
        evidence = list(finding.get("evidence") or [])
        data = dict(evidence[0].get("data") or {}) if evidence else {}
        semantic = dict(data.get("inspection_disposition") or {})
        relationship = dict(data.get("relationship_assessment") or {})
        disposition = str(semantic.get("disposition", "MISSING"))
        conflict_type = str(data.get("type", "UNKNOWN")).upper()
        confidence = float(relationship.get("confidence", 0.0))
        status = str(finding.get("status", ""))
        issue_id = finding.get("issue_id")
        dispositions[disposition] += 1

        if conflict_type == "CLASH" and (disposition != "INTERFERENCE_FAIL" or status != "FAIL"):
            violations.append({"issue_id": issue_id, "code": "CLASH_NOT_FAILED"})
        if status == "PASS" and disposition not in {"CONNECTION_CHECK", "SUPPORT_CHECK"}:
            violations.append({"issue_id": issue_id, "code": "PASS_WITHOUT_ENGINEERING_POLICY"})
        if status == "PASS" and confidence < 0.92:
            violations.append({"issue_id": issue_id, "code": "LOW_CONFIDENCE_PASS"})
        if disposition == "CONSERVATIVE_FALLBACK" and status != "NOT_EVALUATED":
            violations.append({"issue_id": issue_id, "code": "FALLBACK_NOT_REVIEWED"})

    declared = dict(report.get("counts") or {})
    declared_total = sum(int(value) for value in declared.values())
    raw_count = int((report.get("source") or {}).get("returned_conflict_count", len(dmu_findings)))
    if declared_total != len(findings):
        violations.append({"code": "COUNT_TOTAL_MISMATCH", "declared": declared_total,
                           "findings": len(findings)})
    if raw_count != len(dmu_findings):
        violations.append({"code": "RAW_FINDING_COUNT_MISMATCH", "raw": raw_count,
                           "dmu_findings": len(dmu_findings)})

    return {
        "schema_version": "semantic-regression-gate.v1",
        "passed": not violations,
        "finding_count": len(findings),
        "dmu_finding_count": len(dmu_findings),
        "disposition_counts": dict(sorted(dispositions.items())),
        "violations": violations,
    }
