"""Stable read-only connection-graph queries."""

from __future__ import annotations

from typing import Any, Mapping


class GraphQueries:
    def __init__(self, graph: Mapping[str, Any]):
        self.graph = graph
        self.nodes = {node["object_id"]: node for node in graph.get("nodes", ())}

    def resolve(self, alias: str) -> list[dict[str, Any]]:
        key = str(alias).casefold()
        return [node for node in self.nodes.values()
                if key in {str(value).casefold() for value in node.get("aliases", ())}]

    def neighbors(self, object_id: str, relationship_type: str | None = None) -> list[dict[str, Any]]:
        matches = []
        for edge in self.graph.get("edges", ()):
            if relationship_type and edge.get("relationship_type") != relationship_type:
                continue
            if edge.get("source_object_id") == object_id:
                matches.append({"neighbor": self.nodes.get(edge.get("target_object_id")), "edge": edge})
            elif edge.get("target_object_id") == object_id:
                matches.append({"neighbor": self.nodes.get(edge.get("source_object_id")), "edge": edge})
        return matches
