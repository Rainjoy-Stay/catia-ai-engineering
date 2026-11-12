"""Bounded engineering interaction regions; never blanket-pair exemptions."""

from __future__ import annotations

from typing import Any, Mapping


def evaluate_allowed_region(fact: Mapping[str, Any], *, max_depth_mm: float = 5.0) -> dict[str, Any]:
    depth = fact.get("interface_depth_mm", fact.get("insertion_depth_mm"))
    declared = bool(fact.get("connection_relationship") or fact.get("allowed_region"))
    if not declared:
        return {"allowed": False, "reason": "NO_CONNECTION_EVIDENCE", "result": "NORMAL_CHECK"}
    if depth is None:
        return {"allowed": False, "reason": "INTERFACE_DEPTH_UNRESOLVED", "result": "REVIEW"}
    try:
        depth_value = float(depth)
    except (TypeError, ValueError):
        return {"allowed": False, "reason": "INTERFACE_DEPTH_INVALID", "result": "REVIEW"}
    allowed = 0 <= depth_value <= max_depth_mm
    return {"allowed": allowed, "interface_depth_mm": depth_value,
            "max_depth_mm": max_depth_mm,
            "reason": "WITHIN_ALLOWED_REGION" if allowed else "BEYOND_ALLOWED_REGION",
            "result": "EXPECTED_CONTACT" if allowed else "NORMAL_CHECK"}
