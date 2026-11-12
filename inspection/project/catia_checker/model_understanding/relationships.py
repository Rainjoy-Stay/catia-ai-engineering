"""Conservative broad-phase relationship candidates in assembly world coordinates."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .geometry.spatial_index import AABBSpatialIndex
from .features.interfaces import circular_interface_candidates, match_terminal_to_interfaces


def terminal_neighborhood_candidates(
        bodies: Iterable[Mapping[str, Any]], pipe_features: Mapping[str, Mapping[str, Any]], *,
        minimum_search_radius_mm: float = 5.0, diameter_radius_factor: float = 0.75
) -> list[dict[str, Any]]:
    bodies = list(bodies)
    bodies_by_id = {body["source_id"]: body for body in bodies}
    interfaces_by_id = {body["source_id"]: circular_interface_candidates(body) for body in bodies}
    index = AABBSpatialIndex({
        "object_id": body["source_id"], "bounds_mm": body["reference_bounds_mm"],
        "coordinate_space": body.get("reference_bounds_coordinate_space"),
        "metadata": {"source_name": body.get("source_name")},
    } for body in bodies if body.get("reference_bounds_mm"))
    result = []
    for body_id, features in pipe_features.items():
        diameter = features.get("dominant_diameter") or 0.0
        radius = max(minimum_search_radius_mm, float(diameter) * diameter_radius_factor)
        for terminal_index, terminal in enumerate(features.get("terminal_candidates", ())):
            if terminal.get("coordinate_space") != "WORLD":
                continue
            matches = index.query_point(terminal["position_mm"], radius, exclude_ids=[body_id])
            for match in matches:
                interface_matches = match_terminal_to_interfaces(
                    terminal, interfaces_by_id.get(match["object_id"], []))
                match["coincident_interface_matches"] = interface_matches
                match["direct_interface_evidence"] = bool(interface_matches)
            proven = [match for match in matches if match["direct_interface_evidence"]]
            result.append({
                "pipe_body_id": body_id, "terminal_index": terminal_index,
                "terminal_position_mm": terminal["position_mm"], "search_radius_mm": radius,
                "nearby_body_candidates": matches,
                "relationship_state": ("PROBABLE_DIRECT_INTERFACE" if len(proven) == 1 else
                                       "AMBIGUOUS_DIRECT_INTERFACE" if len(proven) > 1 else
                                       "CANDIDATE_ONLY"),
                "direct_interface_body_ids": [match["object_id"] for match in proven],
                "limitations": ["AABB proximity does not prove physical contact or connectivity"],
            })
    return result


def build_connection_graph(bodies: Iterable[Mapping[str, Any]],
                           terminal_relationships: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Create evidence-backed graph edges; ambiguous and proximity-only records remain unresolved."""
    nodes = [{"object_id": body["source_id"], "source_name": body.get("source_name"),
              "product_id": body.get("product_id"), "product_name": body.get("product_name"),
              "aliases": ([value for value in (body["source_id"], body.get("product_name")) if value] +
                          list(body.get("occurrence_names", ())))}
             for body in bodies]
    edges, unresolved = [], []
    seen = set()
    for relationship in terminal_relationships:
        targets = relationship.get("direct_interface_body_ids", ())
        if relationship.get("relationship_state") != "PROBABLE_DIRECT_INTERFACE" or len(targets) != 1:
            unresolved.append(dict(relationship))
            continue
        source, target = relationship["pipe_body_id"], targets[0]
        key = tuple(sorted((source, target))) + (int(relationship["terminal_index"]),)
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "source_object_id": source, "target_object_id": target,
            "source_terminal_index": relationship["terminal_index"],
            "relationship_type": "DIRECT_INTERFACE",
            "evidence": "COINCIDENT_CIRCULAR_INTERFACE",
            "confidence_class": "GEOMETRY_PROBABLE",
        })
    exemption_pairs = sorted({tuple(sorted((edge["source_object_id"], edge["target_object_id"])))
                              for edge in edges})
    return {
        "schema_version": "connection-graph.v0.4",
        "nodes": nodes, "edges": edges, "unresolved_terminals": unresolved,
        "spacing_exemption_pairs": [list(pair) for pair in exemption_pairs],
        "limitations": [
            "Spacing exemptions apply only to pairs backed by a unique coincident circular interface",
            "This graph does not yet prove fluid continuity through the connected object",
        ],
    }


def connection_relation_for_pair(graph: Mapping[str, Any], first: str, second: str
                                 ) -> dict[str, Any] | None:
    """Resolve a DMU component pair to one unique evidence-backed graph edge."""
    aliases = {}
    for node in graph.get("nodes", ()):
        for alias in node.get("aliases", ()):
            aliases.setdefault(str(alias).casefold(), set()).add(node["object_id"])
    first_ids, second_ids = aliases.get(str(first).casefold(), set()), aliases.get(str(second).casefold(), set())
    matches = [edge for edge in graph.get("edges", ())
               if ((edge["source_object_id"] in first_ids and edge["target_object_id"] in second_ids) or
                   (edge["source_object_id"] in second_ids and edge["target_object_id"] in first_ids))]
    if len(matches) != 1:
        return None
    edge = matches[0]
    if edge["relationship_type"] == "DIRECT_INTERFACE":
        endpoint_types = [edge.get("source_object_type"), edge.get("target_object_type")]
        profile = ("FLANGE_INTERFACE" if "FLANGE" in endpoint_types else
                   "FITTING_INTERFACE" if "FITTING" in endpoint_types else
                   "GENERIC_DIRECT_INTERFACE")
        return {"relationship_type": "DIRECT_INTERFACE",
                "evidence": edge["evidence"], "unique_interface_match": True,
                "confidence": 0.95, "inspection_profile": profile,
                "endpoint_object_types": endpoint_types, "graph_edge": edge}
    return {"relationship_type": edge["relationship_type"], "evidence": edge["evidence"],
            "unique_interface_match": False, "confidence": edge.get("confidence", 0.0),
            "graph_edge": edge}
