"""Strict V0.6 semantic output contracts without external schema dependencies."""

from __future__ import annotations

from typing import Any, Mapping


OBJECT_TYPES = {"PIPE", "FITTING", "FLANGE", "CLAMP", "BRACKET",
                "CASE_STRUCTURE", "OTHER", "UNKNOWN"}
RELATIONSHIP_TYPES = {"CONNECTED", "SUPPORTED", "NEARBY", "INTERFERENCE", "UNKNOWN"}
_REQUIRED = {"classification", "confidence", "evidence_refs", "reason", "uncertainty"}


def _validate(value: Mapping[str, Any], allowed: set[str], available_evidence: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _REQUIRED:
        raise ValueError("semantic judgment must contain exactly the required fields")
    classification = str(value["classification"]).upper()
    if classification not in allowed:
        raise ValueError("unsupported semantic classification")
    confidence = float(value["confidence"])
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("semantic confidence must be between 0 and 1")
    evidence = value["evidence_refs"]
    uncertainty = value["uncertainty"]
    if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
        raise ValueError("evidence_refs must be a string list")
    if not set(evidence).issubset(available_evidence):
        raise ValueError("semantic judgment cites evidence not present in the input")
    if classification != "UNKNOWN" and not evidence:
        raise ValueError("non-UNKNOWN semantic judgment requires cited evidence")
    if not isinstance(uncertainty, list) or not all(isinstance(item, str) for item in uncertainty):
        raise ValueError("uncertainty must be a string list")
    reason = str(value["reason"]).strip()
    if not reason:
        raise ValueError("semantic reason must not be empty")
    return {"classification": classification, "confidence": confidence,
            "evidence_refs": evidence, "reason": reason, "uncertainty": uncertainty}


def validate_object_judgment(value: Mapping[str, Any], available_evidence: set[str]) -> dict[str, Any]:
    return _validate(value, OBJECT_TYPES, available_evidence)


def validate_relationship_judgment(value: Mapping[str, Any], available_evidence: set[str]) -> dict[str, Any]:
    return _validate(value, RELATIONSHIP_TYPES, available_evidence)
