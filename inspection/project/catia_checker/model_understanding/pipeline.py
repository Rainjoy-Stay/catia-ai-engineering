"""End-to-end deterministic STEP dumb-model understanding pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters.step_brep import inspect_step_brep
from .features.centerline import derive_step_pipe_features
from .features.pipe_candidate import score_pipe_candidate
from .features.support import bracket_attachment_candidates, midspan_support_candidates
from .relationships import build_connection_graph, terminal_neighborhood_candidates
from .objects import classify_engineering_objects
from .geometry.signatures import body_geometry_signature, stable_body_id
from .cache import GeometryFeatureCache
from .visualization import build_overlay_spec
from .topology import derive_system_topology
from catia_checker.geometry_integrity import build_model_precheck


_IDENTITY_4X4 = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                 [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def normalize_standalone_coordinate_space(model: dict[str, Any]) -> bool:
    """Treat a single root B-Rep representation as world coordinates by identity."""
    bodies = model.get("bodies") or []
    if len(bodies) != 1 or bodies[0].get("assembly_transform"):
        return False
    body = bodies[0]
    body["assembly_transform"] = {"matrix": _IDENTITY_4X4, "relationship_path": [],
                                  "assumption": "STANDALONE_ROOT_IDENTITY"}
    body["reference_bounds_coordinate_space"] = "WORLD"
    body.setdefault("limitations", []).append(
        "Single root STEP representation uses an explicit identity world transform")
    return True


def analyze_step_connections(path: str | Path, *, cache_path: str | Path | None = None) -> dict[str, Any]:
    model = inspect_step_brep(path)
    normalize_standalone_coordinate_space(model)
    for body in model["bodies"]:
        body["geometry_signature"] = body_geometry_signature(body)
        body["stable_body_id"] = stable_body_id(body)
    features = {body["source_id"]: derive_step_pipe_features(body) for body in model["bodies"]}
    cache = GeometryFeatureCache(cache_path) if cache_path else None
    cache_hits = 0
    scores = {}
    for body in model["bodies"]:
        cached = cache.get(body["geometry_signature"]) if cache else None
        if cached and "pipe_candidate_score" in cached:
            scores[body["source_id"]] = cached["pipe_candidate_score"]
            cache_hits += 1
        else:
            scores[body["source_id"]] = score_pipe_candidate(features[body["source_id"]])
            if cache:
                cache.put(body["geometry_signature"], {"pipe_candidate_score": scores[body["source_id"]]})
    if cache:
        cache.save()
    pipes = {body_id: value for body_id, value in features.items()
             if scores[body_id]["candidate_type"] == "PIPE"}
    relationships = terminal_neighborhood_candidates(model["bodies"], pipes)
    graph = build_connection_graph(model["bodies"], relationships)
    support_relationships = midspan_support_candidates(model["bodies"], pipes)
    bracket_relationships = bracket_attachment_candidates(model["bodies"], support_relationships)
    all_support_relationships = support_relationships + bracket_relationships
    graph["edges"].extend({
        "source_object_id": item.get("pipe_body_id", item.get("clamp_body_id")),
        "target_object_id": item["support_body_id"],
        "relationship_type": "SUPPORTED", "evidence": item["evidence"],
        "confidence": item["confidence"], "decision_source": item["decision_source"],
    } for item in all_support_relationships)
    graph["support_candidates"] = all_support_relationships
    engineering_objects = classify_engineering_objects(
        model["bodies"], scores, all_support_relationships, graph["edges"])
    graph["engineering_objects"] = engineering_objects
    classifications = {item["object_id"]: item for item in engineering_objects}
    bodies_by_id = {body["source_id"]: body for body in model["bodies"]}
    for node in graph["nodes"]:
        node["engineering_object"] = classifications[node["object_id"]]
        body = bodies_by_id[node["object_id"]]
        node["stable_object_id"] = body["stable_body_id"]
        node["geometry_signature"] = body["geometry_signature"]
        node["aliases"].append(body["stable_body_id"])
    for edge in graph["edges"]:
        edge["stable_source_object_id"] = bodies_by_id[edge["source_object_id"]]["stable_body_id"]
        edge["stable_target_object_id"] = bodies_by_id[edge["target_object_id"]]["stable_body_id"]
        edge["source_object_type"] = classifications[edge["source_object_id"]]["object_type"]
        edge["target_object_type"] = classifications[edge["target_object_id"]]["object_type"]
    object_cases = []
    for item in engineering_objects:
        if item["object_type"] != "UNKNOWN":
            continue
        body = bodies_by_id[item["object_id"]]
        statistics = body.get("surface_statistics", {})
        bounds = body.get("reference_bounds_mm")
        facts = {
            "product_name_weak": body.get("product_name"),
            "face_count": statistics.get("face_count"),
            "surface_type_counts": statistics.get("surface_type_counts"),
            "bounds_dimensions_mm": ([bounds[i + 3] - bounds[i] for i in range(3)] if bounds else None),
            "tubular_surface_ratio": body.get("tubular_features", {}).get("tubular_surface_ratio"),
        }
        object_cases.append({"object_id": item["object_id"], "facts": facts,
                             "allowed_role": "ENGINEERING_OBJECT_CLASSIFICATION_ONLY"})
    relationship_cases = [{
        "pair_id": f"{item['pipe_body_id']}|terminal:{item['terminal_index']}",
        "facts": {"terminal_position_mm": item["terminal_position_mm"],
                  "search_radius_mm": item["search_radius_mm"],
                  "nearby_candidate_count": len(item["nearby_body_candidates"])},
        "allowed_role": "ENGINEERING_RELATIONSHIP_CLASSIFICATION_ONLY",
    } for item in graph["unresolved_terminals"] if item["nearby_body_candidates"]]
    relationship_cases.extend({
        "pair_id": f"{item.get('clamp_body_id')}|{item['support_body_id']}",
        "facts": dict(item.get("metrics", {})),
        "allowed_role": "ENGINEERING_RELATIONSHIP_CLASSIFICATION_ONLY",
    } for item in bracket_relationships if item["confidence"] < 0.85)
    graph["semantic_reasoning_queue"] = {
        "object_cases": object_cases, "relationship_cases": relationship_cases,
        "policy": "ONLY_UNRESOLVED_CASES; OUTPUT_CANNOT_SET_INSPECTION_DISPOSITION",
    }
    overlay_features = {}
    for body_id, value in pipes.items():
        overlay_features[body_id] = dict(value)
        overlay_features[body_id]["classification_confidence"] = scores[body_id]["confidence"]
    graph["visualization_spec"] = build_overlay_spec(overlay_features, all_support_relationships)
    graph["schema_version"] = "connection-graph.v0.7"
    graph["pipe_candidate_scores"] = scores
    graph["source_file"] = model["source_file"]
    graph["summary"] = {
        "body_count": model["body_count"], "pipe_count": len(pipes),
        "terminal_count": len(relationships),
        "direct_interface_count": sum(edge["relationship_type"] == "DIRECT_INTERFACE" for edge in graph["edges"]),
        "unresolved_terminal_count": len(graph["unresolved_terminals"]),
        "supported_count": len(all_support_relationships),
        "geometry_cache_hits": cache_hits,
    }
    graph["system_topology"] = derive_system_topology(graph)
    graph["model_precheck"] = build_model_precheck(
        model["bodies"], source_format=Path(path).suffix.lstrip(".").upper())
    graph["schema_version"] = "connection-graph.v1.1"
    return graph
