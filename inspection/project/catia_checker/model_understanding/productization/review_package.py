"""Compose audit, topology, verification, and incremental state for the UI."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping


def _edge_key(edge: Mapping[str, Any]) -> str:
    endpoints = sorted((str(edge.get("stable_source_object_id") or edge.get("source_object_id")),
                        str(edge.get("stable_target_object_id") or edge.get("target_object_id"))))
    return "|".join((*endpoints, str(edge.get("relationship_type", "UNKNOWN"))))


def _graph_state(graph: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    objects = {str(node.get("stable_object_id") or node.get("object_id"))
               for node in graph.get("nodes", ())}
    edges = {_edge_key(edge) for edge in graph.get("edges", ())}
    return objects, edges


def build_review_package(report: Mapping[str, Any], *,
                         previous_report: Mapping[str, Any] | None = None,
                         verifications: Mapping[str, Any] | None = None) -> dict[str, Any]:
    graph = report.get("model_understanding_connection_graph") or {}
    topology = graph.get("system_topology") or {}
    records = list((verifications or {}).get("records") or [])
    verified_targets = {str(item.get("target_id")): item for item in records}
    review_items = []
    for finding in report.get("findings", ()):
        if finding.get("status") != "NOT_EVALUATED":
            continue
        target = str(finding.get("issue_id"))
        review_items.append({
            "review_id": target,
            "object_a": finding.get("object_a"),
            "object_b": finding.get("object_b"),
            "title": finding.get("title"),
            "reason": finding.get("message"),
            "verification": verified_targets.get(target),
        })

    current_objects, current_edges = _graph_state(graph)
    if previous_report:
        previous_graph = previous_report.get("model_understanding_connection_graph") or {}
        previous_objects, previous_edges = _graph_state(previous_graph)
        incremental = {
            "mode": "DELTA",
            "added_object_ids": sorted(current_objects - previous_objects),
            "removed_object_ids": sorted(previous_objects - current_objects),
            "added_relationship_keys": sorted(current_edges - previous_edges),
            "removed_relationship_keys": sorted(previous_edges - current_edges),
        }
    else:
        incremental = {"mode": "FULL_BASELINE", "added_object_ids": sorted(current_objects),
                       "removed_object_ids": [], "added_relationship_keys": sorted(current_edges),
                       "removed_relationship_keys": []}
    incremental["changed"] = any(incremental[key] for key in (
        "added_object_ids", "removed_object_ids", "added_relationship_keys", "removed_relationship_keys"))

    counts = dict(report.get("counts") or {})
    payload = {
        "schema_version": "model-understanding-review-package.v2.0",
        "run_id": report.get("run_id"),
        "document": report.get("document"),
        "overview": {
            "inspection_counts": counts,
            "engineering_object_count": len(graph.get("nodes", ())),
            "relationship_count": len(graph.get("edges", ())),
            **dict(topology.get("summary") or {}),
        },
        "system_topology": topology,
        "review_queue": {
            "pending_count": sum(item["verification"] is None for item in review_items),
            "verified_count": sum(item["verification"] is not None for item in review_items),
            "items": review_items,
        },
        "incremental_reinspection": incremental,
        "safety": {
            "semantic_regression_gate": (report.get("audit") or {}).get("semantic_regression_gate"),
            "fallback_available": True,
            "fallback_policy": "SEMANTIC_FAILURE_RETURNS_TRADITIONAL_INSPECTION_RESULT",
            "source_model_modified": bool((report.get("audit") or {}).get("source_model_modified", False)),
        },
    }
    payload["package_fingerprint"] = sha256(repr(payload).encode("utf-8")).hexdigest()
    return payload
