"""Standalone end-to-end orchestration for already extracted exact facts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .analyzer import analyze_interface
from .matching import match_openings_to_nozzles


def analyze_opening_network(openings: Sequence[Mapping[str, Any]],
                            nozzles: Sequence[Mapping[str, Any]], *,
                            matching_options: Mapping[str, Any] | None = None,
                            analysis_options: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Match and assess a complete set without opening or modifying a CAD model."""
    matching = match_openings_to_nozzles(
        openings, nozzles, **dict(matching_options or {}))
    results = [analyze_interface(item["opening"], item["nozzle"],
                                 **dict(analysis_options or {}))
               for item in matching["matches"]]
    ambiguous_openings = {item["object_id"] for item in matching["ambiguities"]
                          if item["object_type"] == "OPENING"}
    ambiguous_nozzles = {item["object_id"] for item in matching["ambiguities"]
                         if item["object_type"] == "NOZZLE"}
    for item in matching["ambiguities"]:
        results.append({"opening_id": item["object_id"] if item["object_type"] == "OPENING" else None,
                        "nozzle_id": item["object_id"] if item["object_type"] == "NOZZLE" else None,
                        "disposition": "REVIEW", "failure_codes": [],
                        "review_codes": [item["reason"]],
                        "candidate_ids": item["candidate_ids"], "mesh_used": False})
    for opening_id in matching["unmatched_opening_ids"]:
        if opening_id not in ambiguous_openings:
            results.append({"opening_id": opening_id, "nozzle_id": None,
                            "disposition": "REVIEW", "failure_codes": [],
                            "review_codes": ["ORPHAN_OPENING_WITHOUT_NOZZLE"],
                            "mesh_used": False})
    for nozzle_id in matching["unmatched_nozzle_ids"]:
        if nozzle_id not in ambiguous_nozzles:
            results.append({"opening_id": None, "nozzle_id": nozzle_id,
                            "disposition": "FAIL",
                            "failure_codes": ["NO_MATCHING_OPENING"],
                            "review_codes": [], "mesh_used": False})
    counts = {status: sum(item["disposition"] == status for item in results)
              for status in ("PASS", "FAIL", "REVIEW")}
    return {"schema_version": "opening-interface-network.v1.0",
            "disposition_counts": counts, "result_count": len(results),
            "results": results, "matching": matching,
            "geometry_authority_required": "CATIA_SPA_OR_EXACT_BREP",
            "source_model_modified": False, "mesh_used": False}
