"""Invoke semantic inference only for unresolved cases and fail closed."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .schemas import validate_object_judgment, validate_relationship_judgment


def _fallback(kind: str, reason: str) -> dict[str, Any]:
    return {"classification": "UNKNOWN", "confidence": 0.0, "evidence_refs": [],
            "reason": reason, "uncertainty": [f"{kind} semantic inference unavailable or invalid"],
            "decision_source": "CONSERVATIVE_FALLBACK"}


class SemanticReasoner:
    def __init__(self, judge: Callable[[list[dict[str, Any]]], list[Mapping[str, Any]]] | None):
        self.judge = judge

    def _run(self, cases: list[dict[str, Any]], validator, kind: str) -> list[dict[str, Any]]:
        if not cases or self.judge is None:
            return [_fallback(kind, "No semantic judge configured") for _ in cases]
        try:
            raw = self.judge(cases)
            if not isinstance(raw, list) or len(raw) != len(cases):
                raise ValueError("semantic judge returned an invalid result count")
            results = []
            for case, value in zip(cases, raw):
                validated = validator(value, set(case.get("facts", {})))
                validated["decision_source"] = "AI_VALIDATED"
                results.append(validated)
            return results
        except Exception as exc:
            return [_fallback(kind, f"Validation fallback: {type(exc).__name__}") for _ in cases]

    def judge_objects(self, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._run(cases, validate_object_judgment, "object")

    def judge_relationships(self, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._run(cases, validate_relationship_judgment, "relationship")
