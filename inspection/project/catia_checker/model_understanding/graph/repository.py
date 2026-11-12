"""Persistent graph storage with separate, append-only-style human decisions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

SUPPORTED_GRAPH_SCHEMAS = {
    "connection-graph.v0.4", "connection-graph.v0.7", "connection-graph.v1.1",
}


class ConnectionGraphRepository:
    def __init__(self, graph_path: str | Path, verification_path: str | Path | None = None):
        self.graph_path = Path(graph_path)
        self.verification_path = Path(verification_path) if verification_path else self.graph_path.with_name(
            self.graph_path.stem + ".verifications.json")

    def save_graph(self, graph: Mapping[str, Any]) -> None:
        if graph.get("schema_version") not in SUPPORTED_GRAPH_SCHEMAS:
            raise ValueError("unsupported connection graph schema")
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_graph(self) -> dict[str, Any]:
        value = json.loads(self.graph_path.read_text(encoding="utf-8"))
        if value.get("schema_version") not in SUPPORTED_GRAPH_SCHEMAS:
            raise ValueError("unsupported connection graph schema")
        return value

    def record_verification(self, *, target_type: str, target_id: str, decision: str,
                            reviewer: str, note: str = "") -> dict[str, Any]:
        if target_type not in {"OBJECT", "RELATIONSHIP"} or decision not in {"CONFIRMED", "REJECTED"}:
            raise ValueError("invalid verification target or decision")
        records = []
        if self.verification_path.exists():
            records = json.loads(self.verification_path.read_text(encoding="utf-8")).get("records", [])
        record = {"target_type": target_type, "target_id": target_id, "decision": decision,
                  "reviewer": reviewer, "note": note,
                  "recorded_at": datetime.now(timezone.utc).isoformat()}
        records.append(record)
        self.verification_path.parent.mkdir(parents=True, exist_ok=True)
        self.verification_path.write_text(json.dumps({"schema_version": "human-verification.v0.7",
                                                      "records": records}, indent=2,
                                                     ensure_ascii=False), encoding="utf-8")
        return record
