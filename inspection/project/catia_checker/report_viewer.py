"""Data helpers for the non-technical inspection-result viewer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def actionable_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    priority = {"FAIL": 0, "ERROR": 1, "WARN": 2, "REVIEW": 3, "PASS": 4}
    return sorted(
        [x for x in report.get("findings", []) if x.get("issue_id")],
        key=lambda x: (priority.get(str(x.get("status")), 9), str(x.get("issue_id"))),
    )


def finding_row(finding: dict[str, Any]) -> tuple[str, ...]:
    value = finding.get("measured_value")
    measured = "" if value is None else f"{value:g} {finding.get('unit') or ''}".strip()
    objects = " ↔ ".join(x for x in (finding.get("object_a"), finding.get("object_b")) if x)
    return (
        str(finding.get("status") or ""),
        str(finding.get("severity") or ""),
        str(finding.get("issue_id") or ""),
        str(finding.get("title") or ""),
        objects,
        measured,
    )


def find_default_report(root: Path) -> Path | None:
    state = root / "validation" / "last-run.json"
    if state.is_file():
        try:
            candidate = Path(json.loads(state.read_text(encoding="utf-8"))["result"])
            if candidate.is_file():
                return candidate.resolve()
        except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    candidates = list((root / "project" / "output" / "runs").glob("*/check.json"))
    return max(candidates, key=lambda x: x.stat().st_mtime).resolve() if candidates else None
