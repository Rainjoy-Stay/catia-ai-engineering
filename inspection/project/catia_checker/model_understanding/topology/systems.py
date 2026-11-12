"""Aggregate object-level relationships into inspectable engineering systems."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Mapping


def _components(adjacency: Mapping[str, set[str]]) -> list[list[str]]:
    remaining = set(adjacency)
    result = []
    while remaining:
        start = min(remaining)
        queue = deque([start])
        visited = {start}
        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        remaining -= visited
        result.append(sorted(visited))
    return sorted(result, key=lambda item: (-len(item), item))


def derive_system_topology(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Build pipe networks and support chains without inventing missing edges."""
    nodes = {item["object_id"]: item for item in graph.get("nodes", ())}
    connected: dict[str, set[str]] = defaultdict(set)
    supported: dict[str, set[str]] = defaultdict(set)
    connection_edges = []
    support_edges = []
    for edge in graph.get("edges", ()):
        source, target = edge["source_object_id"], edge["target_object_id"]
        relation = edge.get("relationship_type")
        if relation in {"DIRECT_INTERFACE", "CONNECTED"}:
            connected[source].add(target)
            connected[target].add(source)
            connection_edges.append(edge)
        elif relation == "SUPPORTED":
            supported[source].add(target)
            supported[target].add(source)
            support_edges.append(edge)

    networks = []
    for index, members in enumerate(_components(connected), 1):
        member_set = set(members)
        edges = [edge for edge in connection_edges
                 if edge["source_object_id"] in member_set and edge["target_object_id"] in member_set]
        degrees = {member: len(connected[member]) for member in members}
        pipe_ids = [member for member in members
                    if nodes.get(member, {}).get("engineering_object", {}).get("object_type") == "PIPE"]
        interface_ids = [member for member in members if member not in pipe_ids and any(
            neighbor in pipe_ids for neighbor in connected[member])]
        networks.append({
            "network_id": f"PIPE_NETWORK_{index:04d}",
            "member_object_ids": members,
            "pipe_object_ids": pipe_ids,
            "interface_object_ids": interface_ids,
            "branch_object_ids": [member for member, degree in degrees.items() if degree >= 3],
            "terminal_object_ids": [member for member, degree in degrees.items() if degree == 1],
            "edge_count": len(edges),
            "confidence_policy": "ALL_EDGES_EVIDENCE_BACKED",
        })

    chains = []
    for index, members in enumerate(_components(supported), 1):
        member_set = set(members)
        edges = [edge for edge in support_edges
                 if edge["source_object_id"] in member_set and edge["target_object_id"] in member_set]
        chains.append({
            "support_chain_id": f"SUPPORT_CHAIN_{index:04d}",
            "member_object_ids": members,
            "pipe_object_ids": [member for member in members
                                if nodes.get(member, {}).get("engineering_object", {}).get("object_type") == "PIPE"],
            "edge_count": len(edges),
            "minimum_edge_confidence": min((float(edge.get("confidence", 0.95)) for edge in edges), default=0.0),
        })

    return {
        "schema_version": "system-topology.v1.1",
        "pipe_networks": networks,
        "support_chains": chains,
        "summary": {
            "pipe_network_count": len(networks),
            "support_chain_count": len(chains),
            "branch_count": sum(len(item["branch_object_ids"]) for item in networks),
            "interface_object_count": len({member for item in networks for member in item["interface_object_ids"]}),
        },
        "limitations": [
            "Only evidence-backed graph edges are aggregated; geometric gaps are not bridged",
            "An interface object is a non-pipe object adjacent to a recognized pipe, not a claimed equipment type",
        ],
    }
