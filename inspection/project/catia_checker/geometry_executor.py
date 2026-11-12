"""Dispatch broad-phase candidates to exact geometry providers with auditability."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Iterable, Mapping


class PrecisionMethod(str, Enum):
    CATIA_DMU_SOLID_CLASH = "CATIA_DMU_SOLID_CLASH"
    OCCT_BREP_EXACT = "OCCT_BREP_EXACT"
    TESSELLATED_SURFACE_INTERSECTION = "TESSELLATED_SURFACE_INTERSECTION"


def precision_plan(candidate: Mapping[str, Any], entities: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Choose an allowed deterministic calculation; never make a semantic decision."""
    first, second = str(candidate["object_a"]), str(candidate["object_b"])
    entity_a, entity_b = entities.get(first), entities.get(second)
    if entity_a is None or entity_b is None:
        return {"pair_id": candidate["pair_id"], "state": "NOT_EXECUTABLE",
                "reason": "ENTITY_NOT_RESOLVED", "object_a": first, "object_b": second}
    kinds = {str(candidate["entity_kind_a"]), str(candidate["entity_kind_b"])}
    if kinds == {"SOLID"}:
        method = PrecisionMethod.CATIA_DMU_SOLID_CLASH
    elif all("EXACT_BREP" in item.get("capabilities", []) for item in (entity_a, entity_b)):
        method = PrecisionMethod.OCCT_BREP_EXACT
    elif all("TESSELLATED" in item.get("capabilities", []) for item in (entity_a, entity_b)):
        method = PrecisionMethod.TESSELLATED_SURFACE_INTERSECTION
    else:
        return {"pair_id": candidate["pair_id"], "state": "NOT_EXECUTABLE",
                "reason": "NO_COMMON_PRECISE_GEOMETRY_CAPABILITY", "object_a": first, "object_b": second}
    return {"pair_id": candidate["pair_id"], "state": "PLANNED", "object_a": first, "object_b": second,
            "entity_a": dict(entity_a), "entity_b": dict(entity_b), "method": method.value,
            "requires_intersection_points": method is not PrecisionMethod.CATIA_DMU_SOLID_CLASH,
            "requires_closed_volume": method is PrecisionMethod.CATIA_DMU_SOLID_CLASH}


def execute_precision_queue(candidates: Iterable[Mapping[str, Any]],
                            entities: Iterable[Mapping[str, Any]],
                            evaluator: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> dict[str, Any]:
    """Execute plans through an injected CATIA/B-Rep provider and retain every outcome."""
    entity_index = {str(item.get("object_id") or item.get("source_id") or item.get("source_path")): item
                    for item in entities}
    results, execution_log = [], []
    for candidate in candidates:
        plan = precision_plan(candidate, entity_index)
        if plan["state"] != "PLANNED":
            execution_log.append(plan)
            continue
        try:
            fact = dict(evaluator(plan))
            fact.setdefault("object_a", plan["object_a"])
            fact.setdefault("object_b", plan["object_b"])
            fact.setdefault("entity_a", plan["entity_a"])
            fact.setdefault("entity_b", plan["entity_b"])
            fact.setdefault("method", plan["method"])
            results.append(fact)
            execution_log.append({"pair_id": plan["pair_id"], "state": "EXECUTED",
                                  "method": plan["method"]})
        except Exception as exc:
            execution_log.append({"pair_id": plan["pair_id"], "state": "REVIEW",
                                  "method": plan["method"], "reason": type(exc).__name__})
    return {"schema_version": "geometry-execution.v1.0", "facts": results,
            "execution_log": execution_log,
            "executed_count": sum(item["state"] == "EXECUTED" for item in execution_log),
            "review_count": sum(item["state"] == "REVIEW" for item in execution_log),
            "not_executable_count": sum(item["state"] == "NOT_EXECUTABLE" for item in execution_log)}
