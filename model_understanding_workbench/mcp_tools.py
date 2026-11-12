"""Small typed MCP module, reusable without changing the deployed CATIA server."""
from __future__ import annotations

from .catia_reader import attach_and_read
from .snapshot import build_snapshot, describe, find_objects, transform_point


class UnderstandingTools:
    def __init__(self, capture_reader=attach_and_read):
        self.capture_reader = capture_reader
        self.snapshot = None

    def get_tool_definitions(self):
        def tool(name, description, properties=None, required=None):
            return {"name": name, "description": description,
                    "inputSchema": {"type": "object", "properties": properties or {},
                                    "required": required or [], "additionalProperties": False}}
        return [
            tool("catia_understanding_capture", "Read the active CATPart/CATProduct into a structural snapshot. Attach only; never activate, update, save or modify a model. Does not read native face topology or infer engineering function.",
                 {"max_occurrences": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 20000},
                  "max_items": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 20000},
                  "max_depth": {"type": "integer", "minimum": 1, "maximum": 100, "default": 80}}),
            tool("catia_understanding_query_snapshot", "Find occurrence candidates in an explicit historical snapshot; names can be ambiguous. Recapture for current-model claims.",
                 {"snapshot_id": {"type": "string"}, "text": {"type": "string", "minLength": 1}}, ["snapshot_id", "text"]),
            tool("catia_understanding_describe_snapshot", "Read one snapshot object and its evidence. Does not establish current live state, contact, function or native face adjacency.",
                 {"snapshot_id": {"type": "string"}, "object_id": {"type": "string"}}, ["snapshot_id", "object_id"]),
            tool("catia_understanding_point_snapshot", "Transform one local point to root-product millimetres using the captured occurrence chain. Missing transforms return UNKNOWN.",
                 {"snapshot_id": {"type": "string"}, "object_id": {"type": "string"},
                  "point_mm": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}},
                 ["snapshot_id", "object_id", "point_mm"]),
        ]

    def execute(self, name, arguments):
        definitions = {t["name"]: t for t in self.get_tool_definitions()}
        if name not in definitions:
            raise ValueError("Unknown understanding operation")
        schema = definitions[name]["inputSchema"]
        if set(arguments) - set(schema["properties"]):
            raise ValueError("Unexpected arguments")
        if any(key not in arguments for key in schema["required"]):
            raise ValueError("Required argument missing")
        if name == "catia_understanding_capture":
            # Clear first: a failed recapture must never expose a previous model as
            # the successful result of this capture request.
            self.snapshot = None
            for key, value in arguments.items():
                spec = schema["properties"][key]
                if type(value) is not int or not spec["minimum"] <= value <= spec["maximum"]:
                    raise ValueError("Invalid capture budget")
            self.snapshot = build_snapshot(self.capture_reader(**arguments))
            return {key: self.snapshot[key] for key in ("snapshot_id", "source", "root_id", "coverage",
                    "knowledge_level", "capabilities", "limitations", "source_state")}
        if self.snapshot is None or arguments["snapshot_id"] != self.snapshot["snapshot_id"]:
            raise ValueError("Snapshot is missing or superseded; recapture and use the returned snapshot_id")
        if name == "catia_understanding_query_snapshot":
            if not isinstance(arguments["text"], str) or not arguments["text"].strip():
                raise ValueError("Nonempty query required")
            result = find_objects(self.snapshot, arguments["text"])
        elif name == "catia_understanding_describe_snapshot":
            result = describe(self.snapshot, arguments["object_id"])
        else:
            result = transform_point(self.snapshot, arguments["object_id"], arguments["point_mm"])
        result["temporal_scope"] = "CAPTURED_SNAPSHOT_NOT_LIVE_STATE"
        return result
