"""Merge verified primary and single-Body rescue identities into a check result."""
from __future__ import annotations
from typing import Any, Mapping


def merge_verified_body_mapping(payload: dict[str, Any], replay: Mapping[str, Any],
                                rescue: Mapping[str, Any]) -> dict[str, Any]:
    replay_result = replay.get("result") or replay
    targets = replay_result.get("target_records") or {}
    mapping: dict[str, dict[str, Any]] = {}
    for item in replay_result.get("matches") or []:
        target = targets.get(str(item["target_id"])) or {}
        mapping[str(item["source_id"])] = {
            "source_body_index": int(item["target_id"]),
            "source_body_name": target.get("source_body_name"),
            "mapping_method": item.get("mapping_method"),
        }
    for item in rescue.get("assignments") or []:
        index = int(item["source_body_index"])
        target = targets.get(str(index)) or {}
        mapping[str(item["shape_id"])] = {
            "source_body_index": index,
            "source_body_name": target.get("source_body_name"),
            "mapping_method": item.get("mapping_method"),
        }
    large = payload.get("large_single_part_analysis") or {}
    shapes = (large.get("batch_plan") or {}).get("shapes") or []
    for shape in shapes:
        if str(shape.get("shape_id")) in mapping:
            shape.update(mapping[str(shape["shape_id"])])
    by_id = {str(item.get("shape_id")): item for item in shapes}
    for finding in payload.get("findings") or []:
        metadata = finding.get("metadata") or {}
        for suffix in ("a", "b"):
            shape_id = str(metadata.get(f"geometry_object_{suffix}") or "")
            record = by_id.get(shape_id)
            if record and record.get("source_body_index") is not None:
                metadata[f"source_body_{suffix}"] = {
                    "source_body_index": record["source_body_index"],
                    "source_body_name": record.get("source_body_name"),
                    "mapping_method": record.get("mapping_method"),
                }
    unresolved = [str(item.get("shape_id")) for item in shapes
                  if str(item.get("shape_id")) not in mapping]
    groups: dict[str, list[str]] = {}
    for shape_id, record in mapping.items():
        groups.setdefault(str(record["source_body_index"]), []).append(shape_id)
    audit = {
        "method": "PRIMARY_LABEL_VOLUME_PLUS_SINGLE_BODY_MULTI_FEATURE",
        "mapped_solid_count": len(mapping), "solid_count": len(shapes),
        "coverage_percent": round(100 * len(mapping) / max(1, len(shapes)), 2),
        "unresolved_shape_ids": unresolved,
        "one_to_many_body_groups": {key: value for key, value in groups.items() if len(value) > 1},
        "is_complete": not unresolved, "sequence_fallback_used": False,
    }
    payload.setdefault("audit", {})["body_solid_traceability"] = audit
    budget = payload.setdefault("confidence_budget", {})
    budget.setdefault("degraded", [])
    if unresolved:
        message = f"仍有{len(unresolved)}个Solid无法可靠定位到CATIA Body；已列入audit"
        if message not in budget["degraded"]: budget["degraded"].append(message)
        budget["is_complete"] = False
    from standalone.step_interference_filter import filter_result
    filter_result(payload)
    return audit
