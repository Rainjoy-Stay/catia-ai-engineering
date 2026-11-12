"""Read-only MCP boundary for deterministic phase-one route planning."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from catia_checker.route_planning import (
    OrthogonalRoutePlanner,
    request_from_dict,
    result_to_dict,
)
from catia_checker.route_preflight_tokens import issue_preflight_token


class RoutePlanningTool:
    def __init__(self, connection=None):
        self.connection = connection

    def get_tool_definitions(self):
        point = {
            "type": "array", "items": {"type": "number"},
            "minItems": 3, "maxItems": 3,
        }
        direction = {
            **point,
            "description": "One of the six orthogonal unit vectors",
        }
        port = {
            "type": "object",
            "properties": {
                "point": point,
                "direction": direction,
                "exit_length_mm": {"type": "number", "minimum": 0, "default": 0},
            },
            "required": ["point", "direction"],
            "additionalProperties": False,
        }
        obstacle = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "minimum": point,
                "maximum": point,
            },
            "required": ["minimum", "maximum"],
            "additionalProperties": False,
        }
        number_options = {
            "grid_size_mm": {"type": "number", "exclusiveMinimum": 0, "default": 10},
            "pipe_outer_diameter_mm": {"type": "number", "exclusiveMinimum": 0, "default": 20},
            "clearance_mm": {"type": "number", "minimum": 0, "default": 10},
            "minimum_straight_mm": {"type": "number", "minimum": 0, "default": 20},
            "bend_radius_mm": {"type": "number", "exclusiveMinimum": 0, "default": 30},
            "bend_penalty": {"type": "number", "minimum": 0, "default": 40},
            "vertical_penalty_per_mm": {"type": "number", "minimum": 0, "default": 0},
            "heuristic_weight": {"type": "number", "exclusiveMinimum": 0, "default": 1.15},
            "search_margin_mm": {"type": "number", "exclusiveMinimum": 0, "default": 100},
            "max_expanded_states": {"type": "integer", "minimum": 1, "default": 500000},
            "candidate_count": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
            "candidate_overlap_penalty": {"type": "number", "minimum": 0, "default": 25},
        }
        plan_schema = {
            "type": "object",
            "properties": {
                "start": port,
                "goal": port,
                "obstacles": {"type": "array", "items": obstacle, "default": []},
                **number_options,
            },
            "required": ["start", "goal"],
            "additionalProperties": False,
        }
        active_product_schema = {
            "type": "object",
            "properties": {
                "start": port,
                "goal": port,
                "obstacle_component_names": {
                    "type": "array", "items": {"type": "string"}, "minItems": 1,
                    "description": "Exact top-level component instance names to treat as obstacles",
                },
                **number_options,
            },
            "required": ["start", "goal", "obstacle_component_names"],
            "additionalProperties": False,
        }
        return [{
            "name": "catia_plan_orthogonal_route",
            "description": (
                "Plan read-only phase-one orthogonal pipe centerline candidates with "
                "direction-aware weighted A*. Obstacles are assembly-coordinate AABBs "
                "and are inflated by pipe radius plus clearance. This never changes or "
                "saves the CATIA model; review a candidate before separately creating an "
                "Arrangement Run. Coordinates are millimetres and port exit points must "
                "align with the selected grid size."
            ),
            "inputSchema": plan_schema,
        }, {
            "name": "catia_plan_route_in_active_product",
            "description": (
                "Read tessellated world-space bounding boxes for explicitly named "
                "top-level components in the active CATProduct, then plan orthogonal "
                "pipe centerline candidates. Uses disposable unsaved CATIA documents "
                "for mesh extraction, restores the source product, and never changes "
                "or saves it. This is conservative AABB planning; exact clash validation "
                "is still required before model write-back."
            ),
            "inputSchema": active_product_schema,
        }, {
            "name": "catia_route_issue_preflight_token",
            "description": (
                "Issue a short-lived one-time creation token for one candidate in a "
                "route-development-pipeline.v1.0 result. The candidate must have exact "
                "OCCT B-Rep PASS and a valid swept envelope. The token binds points, "
                "per-bend radii and diameter; this operation does not modify CATIA."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "result_file": {"type": "string"},
                    "candidate_rank": {"type": "integer", "minimum": 1},
                },
                "required": ["result_file", "candidate_rank"],
                "additionalProperties": False,
            },
        }]

    def execute(self, name, arguments):
        if name == "catia_route_issue_preflight_token":
            return json.dumps(issue_preflight_token(
                arguments["result_file"], int(arguments["candidate_rank"])),
                ensure_ascii=False, indent=2)
        if name not in {"catia_plan_orthogonal_route", "catia_plan_route_in_active_product"}:
            raise ValueError(f"Unknown route planning tool: {name}")
        payload = dict(arguments)
        extracted = []
        if name == "catia_plan_route_in_active_product":
            extracted = self._component_obstacles(payload.pop("obstacle_component_names"))
            payload["obstacles"] = extracted
        request = request_from_dict(payload)
        result = result_to_dict(OrthogonalRoutePlanner().plan(request))
        for candidate in result["candidates"]:
            candidate["section_diameter_mm"] = request.pipe_outer_diameter_mm
        result["mutation"] = "NONE"
        if extracted:
            result["obstacles_used"] = extracted
            result["obstacle_representation"] = "TESSELLATED_COMPONENT_WORLD_AABB"
        result["next_operation"] = (
            "Run the full route development pipeline and exact B-Rep validation. "
            "For a PASS candidate call catia_route_issue_preflight_token, then pass "
            "the one-time token to catia_tubing_create_validated_arrangement_run."
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _component_obstacles(self, component_names):
        if self.connection is None:
            raise RuntimeError("CATIA connection is unavailable")
        names = [str(value) for value in component_names]
        if len(names) != len(set(names)):
            raise ValueError("obstacle_component_names must be unique")
        self.connection.ensure_connected()
        document = self.connection.active_document
        if not str(document.Name).lower().endswith(".catproduct"):
            raise RuntimeError("Active document must be a CATProduct")
        available = [
            str(document.Product.Products.Item(i).Name)
            for i in range(1, document.Product.Products.Count + 1)
        ]
        missing = [name for name in names if available.count(name) != 1]
        if missing:
            raise ValueError(f"Expected unique top-level components, unresolved: {missing}")

        # Reuse the proven disposable-document tessellation operation.  Only its
        # bounds are retained; temporary mesh JSON is deleted automatically.
        from catia_mcp.dev_extensions import _export_component_mesh_json

        obstacles = []
        with tempfile.TemporaryDirectory(prefix="catia_route_bounds_") as directory:
            for index, component_name in enumerate(names, 1):
                output = Path(directory) / f"component_{index:04d}.json"
                facts = json.loads(_export_component_mesh_json(self.connection, {
                    "component_name": component_name,
                    "output_path": str(output),
                }))
                bounds = facts.get("bounds_world_mm")
                if not isinstance(bounds, list) or len(bounds) != 6:
                    raise RuntimeError(f"No tessellated bounds returned for {component_name}")
                obstacles.append({
                    "name": component_name,
                    "minimum": [float(v) for v in bounds[:3]],
                    "maximum": [float(v) for v in bounds[3:]],
                    "mesh_vertex_count": int(facts.get("vertex_count", 0)),
                    "mesh_triangle_count": int(facts.get("triangle_count", 0)),
                })
        document.Activate()
        return obstacles
