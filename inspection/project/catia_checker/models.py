"""Stable, JSON-serializable result models for deterministic CATIA checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


RESULT_SCHEMA_VERSION = "1.1.0"


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"
    EXEMPTED = "EXEMPTED"
    ERROR = "ERROR"


class Severity(str, Enum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"


class EvidenceKind(str, Enum):
    CATIA_MEASUREMENT = "CATIA_MEASUREMENT"
    CATIA_CLASH = "CATIA_CLASH"
    SCREENSHOT = "SCREENSHOT"
    MODEL_LOCATION = "MODEL_LOCATION"
    RULE_TRACE = "RULE_TRACE"
    LOG = "LOG"


@dataclass(frozen=True)
class Evidence:
    """One traceable fact supporting a finding.

    ``data`` holds source-specific structured facts. Examples include
    ``value_mm``, ``clash_type``, camera coordinates, or a rule expression.
    """

    kind: EvidenceKind
    source: str
    description: str = ""
    path: str | None = None
    object_paths: tuple[str, ...] = ()
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("Evidence.source must not be empty")
        object.__setattr__(self, "object_paths", tuple(self.object_paths))
        object.__setattr__(self, "data", dict(self.data))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["kind"] = self.kind.value
        result["object_paths"] = list(self.object_paths)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Evidence":
        return cls(
            kind=EvidenceKind(value["kind"]),
            source=str(value["source"]),
            description=str(value.get("description", "")),
            path=value.get("path"),
            object_paths=tuple(value.get("object_paths", ())),
            data=dict(value.get("data", {})),
        )


@dataclass(frozen=True)
class ConfidenceBudget:
    """Declares the exact scope and limitations of a check run."""

    checked: tuple[str, ...] = ()
    not_checked: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    degraded: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("checked", "not_checked", "assumptions", "degraded"):
            values = tuple(str(item) for item in getattr(self, name))
            if any(not item.strip() for item in values):
                raise ValueError(f"ConfidenceBudget.{name} contains an empty item")
            object.__setattr__(self, name, values)

    @property
    def is_complete(self) -> bool:
        return not self.not_checked and not self.degraded

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked": list(self.checked),
            "not_checked": list(self.not_checked),
            "assumptions": list(self.assumptions),
            "degraded": list(self.degraded),
            "is_complete": self.is_complete,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConfidenceBudget":
        return cls(
            checked=tuple(value.get("checked", ())),
            not_checked=tuple(value.get("not_checked", ())),
            assumptions=tuple(value.get("assumptions", ())),
            degraded=tuple(value.get("degraded", ())),
        )


@dataclass(frozen=True)
class CheckFinding:
    """A rule decision backed by deterministic CATIA or rule evidence."""

    issue_id: str
    rule_id: str
    status: CheckStatus
    severity: Severity
    title: str
    message: str
    object_a: str | None = None
    object_b: str | None = None
    measured_value: float | None = None
    limit_value: float | None = None
    unit: str | None = None
    tolerance: float | None = None
    location_xyz_mm: tuple[float, float, float] | None = None
    standard_reference: str | None = None
    recommendation: str | None = None
    evidence: tuple[Evidence, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("issue_id", "rule_id", "title", "message"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"CheckFinding.{name} must not be empty")
        if self.measured_value is not None and not self.unit:
            raise ValueError("CheckFinding.unit is required when measured_value is set")
        if self.location_xyz_mm is not None and len(self.location_xyz_mm) != 3:
            raise ValueError("CheckFinding.location_xyz_mm must contain X, Y and Z")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "issue_id": self.issue_id,
            "rule_id": self.rule_id,
            "status": self.status.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "object_a": self.object_a,
            "object_b": self.object_b,
            "measured_value": self.measured_value,
            "limit_value": self.limit_value,
            "unit": self.unit,
            "tolerance": self.tolerance,
            "location_xyz_mm": list(self.location_xyz_mm) if self.location_xyz_mm else None,
            "standard_reference": self.standard_reference,
            "recommendation": self.recommendation,
            "evidence": [item.to_dict() for item in self.evidence],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CheckFinding":
        schema_version = value.get("schema_version", RESULT_SCHEMA_VERSION)
        if schema_version != RESULT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported finding schema_version: {schema_version}")
        location = value.get("location_xyz_mm")
        return cls(
            issue_id=str(value["issue_id"]),
            rule_id=str(value["rule_id"]),
            status=CheckStatus(value["status"]),
            severity=Severity(value["severity"]),
            title=str(value["title"]),
            message=str(value["message"]),
            object_a=value.get("object_a"),
            object_b=value.get("object_b"),
            measured_value=value.get("measured_value"),
            limit_value=value.get("limit_value"),
            unit=value.get("unit"),
            tolerance=value.get("tolerance"),
            location_xyz_mm=tuple(location) if location is not None else None,
            standard_reference=value.get("standard_reference"),
            recommendation=value.get("recommendation"),
            evidence=tuple(Evidence.from_dict(item) for item in value.get("evidence", ())),
            metadata=dict(value.get("metadata", {})),
        )


def build_llm_payload(
    document: str,
    findings: Iterable[CheckFinding],
    confidence_budget: ConfidenceBudget,
) -> dict[str, Any]:
    """Build a fact-only payload accepted by the current LLM adapters."""

    finding_list = list(findings)
    counts = {status.value: 0 for status in CheckStatus}
    for finding in finding_list:
        counts[finding.status.value] += 1
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "document": document,
        "counts": counts,
        "findings": [finding.to_dict() for finding in finding_list],
        "confidence_budget": confidence_budget.to_dict(),
    }
