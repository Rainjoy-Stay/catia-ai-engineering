"""Measurement and analysis tools for CATIA V5.

Distance, angle, inertia, bounding box, and part property queries.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import struct
import tempfile
from typing import Any

import pythoncom

from catia_mcp.connection import CATIAConnection
from catia_mcp.arrangement_geometry import (
    arrangement_product,
    component_mesh,
    mesh_bounds,
    _parse_stl,
    polyline_distance,
    polyline_mesh_distance,
    resolve_run,
    run_polyline,
)


class MeasurementTools:
    """Tools for measurement and analysis in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_measure_distance",
                "description": (
                    "Measure the minimum distance between two geometry elements. "
                    "Returns distance in mm."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "element1": {
                            "type": "string",
                            "description": "Name of first element (feature, face, edge, point)",
                        },
                        "element2": {
                            "type": "string",
                            "description": "Name of second element",
                        },
                    },
                    "required": ["element1", "element2"],
                },
            },
            {
                "name": "catia_measure_face_distance",
                "description": "Measure exact SPA minimum distance between two CATIA Face/Surface references without modifying the model.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "face1": {"type": "string"},
                        "face2": {"type": "string"},
                    },
                    "required": ["face1", "face2"],
                },
            },
            {
                "name": "catia_measure_surface_id_distance",
                "description": "Measure exact CATIA SPA distance between two unique surface IDs returned by catia_get_part_geometry_inventory.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "surface_id1": {"type": "string"},
                        "surface_id2": {"type": "string"},
                    },
                    "required": ["surface_id1", "surface_id2"],
                },
            },
            {
                "name": "catia_dev_dispatch",
                "description": "Run a hot-reloadable CATIA development operation without restarting the MCP server.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string"},
                        "arguments": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["operation"],
                },
            },
            {
                "name": "catia_measure_product_distance",
                "description": (
                    "Measure signed surface clearance between two exact native Arrangement Runs "
                    "in the active CATProduct. Positive is clearance; negative is interference."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "element1": {"type": "string", "description": "Exact first route name"},
                        "element2": {"type": "string", "description": "Exact second route name"},
                        "chord_tolerance": {"type": "number", "default": 0.05},
                        "contact_tolerance": {"type": "number", "default": 0.10},
                    },
                    "required": ["element1", "element2"],
                },
            },
            {
                "name": "catia_measure_route_to_component",
                "description": (
                    "Measure signed clearance/interference between one native Arrangement Run "
                    "and one exact top-level CATPart component without modifying the source model."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "route_name": {"type": "string"},
                        "component_name": {"type": "string"},
                        "chord_tolerance": {"type": "number", "default": 0.05},
                        "contact_tolerance": {"type": "number", "default": 0.10},
                    },
                    "required": ["route_name", "component_name"],
                },
            },
            {
                "name": "catia_measure_component_interference",
                "description": (
                    "Use CATIA DMU Space Analysis to classify interference, contact, or clearance "
                    "between two exact top-level components. Temporary Clash data is removed."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component1": {"type": "string"},
                        "component2": {"type": "string"},
                        "contact_tolerance": {"type": "number", "default": 0.10},
                        "max_reported_intersection_points": {"type": "integer", "default": 20, "minimum": 1},
                    },
                    "required": ["component1", "component2"],
                },
            },
            {
                "name": "catia_scan_product_clashes",
                "description": (
                    "Scan the active CATProduct in one native CATIA DMU Clash computation on "
                    "a disposable product, leaving no Clash analysis in the source. This is the "
                    "scalable full-assembly alternative to pairwise COM calls."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "clearance": {
                            "type": "number",
                            "default": 0.10,
                            "description": "Report clearance violations below this positive value in mm",
                        },
                        "scope_component_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional exact top-level component names; omitted means Between All",
                        },
                        "exclude_pairs": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "description": "Exact unordered component-name pairs to mark EXEMPTED",
                        },
                        "max_conflicts": {"type": "integer", "default": 10000, "minimum": 1},
                    },
                },
            },
            {
                "name": "catia_get_inertia",
                "description": (
                    "Get inertia properties of the active part: volume, surface area, "
                    "center of gravity, mass (if density is defined), moments of inertia."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "density": {
                            "type": "number",
                            "description": "Material density in kg/m3 (optional, for mass calculation)",
                        },
                    },
                },
            },
            {
                "name": "catia_get_bounding_box",
                "description": (
                    "Get the bounding box of the active part. "
                    "Returns min/max coordinates in mm."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_get_body_geometry_batch",
                "description": (
                    "Read exact SPA volume, area and centroid for every Body in the active "
                    "CATPart without modifying or saving the source. Per-Body bounding boxes "
                    "remain disabled because CATIA Body clipboard isolation dirties the source."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "body_names": {
                            "type": "array", "items": {"type": "string"},
                            "description": "Optional exact Body names; omitted means every Body",
                        },
                        "include_bounding_box": {"type": "boolean", "default": False,
                            "description": "Reserved; currently reports a read-only limitation"},
                    },
                },
            },
            {
                "name": "catia_get_part_geometry_inventory",
                "description": (
                    "Read a CATPart geometry inventory including Bodies and HybridBody "
                    "surface elements. Zero-volume surfaces are retained as physical-boundary "
                    "candidates; curves and points are explicitly logged as reference geometry. "
                    "The source document is neither updated nor saved."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_reference_geometry": {
                            "type": "boolean", "default": True,
                            "description": "Include curves and points with an explicit WHY_SKIPPED reason",
                        },
                    },
                },
            },
            {
                "name": "catia_export_active_part_tessellation",
                "description": (
                    "Export the active CATPart as a temporary STL, read its complete tessellated "
                    "geometry into a bounded JSON payload, then remove the temporary file. This "
                    "does not create clipboard copies, update, or save the source document."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "max_triangles": {"type": "integer", "default": 200000, "minimum": 1},
                    },
                },
            },
            {
                "name": "catia_get_product_component_instances",
                "description": (
                    "Read exact top-level CATProduct instance names, part numbers and local-to-product "
                    "affine transforms. No source geometry is modified or saved."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "catia_get_parameters",
                "description": (
                    "List all user-defined and computed parameters of the active part. "
                    "Includes dimensions, formulas, and design tables."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": "Optional name filter (partial match)",
                        },
                    },
                },
            },
            {
                "name": "catia_set_parameter",
                "description": (
                    "Set the value of a named parameter in the active part. "
                    "Useful for parametric design modifications."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Full parameter name (e.g., 'Part1\\\\Pad.1\\\\FirstLimit\\\\Length')",
                        },
                        "value": {
                            "type": "number",
                            "description": "New value for the parameter",
                        },
                    },
                    "required": ["name", "value"],
                },
            },
            {
                "name": "catia_update_part",
                "description": "Force update/rebuild of the active part. Recalculates all features.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        match tool_name:
            case "catia_measure_distance":
                return self._measure_distance(arguments["element1"], arguments["element2"])
            case "catia_measure_face_distance":
                return self._measure_face_distance(arguments["face1"], arguments["face2"])
            case "catia_measure_surface_id_distance":
                return self._measure_surface_id_distance(arguments["surface_id1"], arguments["surface_id2"])
            case "catia_dev_dispatch":
                from catia_mcp import dev_extensions
                importlib.reload(dev_extensions)
                return dev_extensions.dispatch(self.conn, arguments["operation"], arguments.get("arguments", {}))
            case "catia_measure_product_distance":
                return self._measure_product_distance(
                    arguments["element1"], arguments["element2"],
                    float(arguments.get("chord_tolerance", 0.05)),
                    float(arguments.get("contact_tolerance", 0.10)),
                )
            case "catia_measure_route_to_component":
                return self._measure_route_to_component(
                    arguments["route_name"], arguments["component_name"],
                    float(arguments.get("chord_tolerance", 0.05)),
                    float(arguments.get("contact_tolerance", 0.10)),
                )
            case "catia_measure_component_interference":
                return self._measure_component_interference(
                    arguments["component1"], arguments["component2"],
                    float(arguments.get("contact_tolerance", 0.10)),
                    int(arguments.get("max_reported_intersection_points", 20)),
                )
            case "catia_scan_product_clashes":
                return self._scan_product_clashes(
                    float(arguments.get("clearance", 0.10)),
                    arguments.get("scope_component_names"),
                    arguments.get("exclude_pairs", []),
                    int(arguments.get("max_conflicts", 10000)),
                )
            case "catia_get_inertia":
                return self._get_inertia(arguments.get("density"))
            case "catia_get_bounding_box":
                return self._get_bounding_box()
            case "catia_get_body_geometry_batch":
                return self._get_body_geometry_batch(
                    arguments.get("body_names"),
                    bool(arguments.get("include_bounding_box", False)),
                )
            case "catia_get_part_geometry_inventory":
                return self._get_part_geometry_inventory(
                    bool(arguments.get("include_reference_geometry", True)),
                )
            case "catia_export_active_part_tessellation":
                return self._export_active_part_tessellation(int(arguments.get("max_triangles", 200000)))
            case "catia_get_product_component_instances":
                return self._get_product_component_instances()
            case "catia_get_parameters":
                return self._get_parameters(arguments.get("filter"))
            case "catia_set_parameter":
                return self._set_parameter(arguments["name"], arguments["value"])
            case "catia_update_part":
                return self._update_part()
            case _:
                raise ValueError(f"Unknown measurement tool: {tool_name}")

    def _measure_distance(self, elem1_name: str, elem2_name: str) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        spa = self.conn.spa_workbench

        # Create references from names
        sel = self.conn.hso
        sel.Clear()

        # Search for the elements
        sel.Search(f"Name={elem1_name},all")
        if sel.Count == 0:
            raise RuntimeError(f"Element '{elem1_name}' not found")
        ref1 = part.CreateReferenceFromObject(sel.Item(1).Value)

        sel.Clear()
        sel.Search(f"Name={elem2_name},all")
        if sel.Count == 0:
            raise RuntimeError(f"Element '{elem2_name}' not found")
        ref2 = part.CreateReferenceFromObject(sel.Item(1).Value)
        sel.Clear()

        # Measure
        measurable = spa.GetMeasurable(ref1)
        distance = measurable.GetMinimumDistance(ref2)

        return f"Minimum distance between '{elem1_name}' and '{elem2_name}': {distance:.4f} mm"

    def _measure_face_distance(self, face1_name: str, face2_name: str) -> str:
        self.conn.ensure_connected()
        if face1_name == face2_name:
            raise ValueError("face1 and face2 must be different")
        doc = self.conn.active_document
        selection = doc.Selection
        selection.Clear()
        try:
            selection.Search(f"Name={face1_name},all")
            if selection.Count2 < 1:
                raise RuntimeError(f"Face '{face1_name}' not found")
            first = selection.Item2(1).Value
            selection.Clear()
            selection.Search(f"Name={face2_name},all")
            if selection.Count2 < 1:
                raise RuntimeError(f"Face '{face2_name}' not found")
            second = selection.Item2(1).Value
            part = self.conn.get_active_part()
            spa = self.conn.spa_workbench
            distance = float(spa.GetMeasurable(part.CreateReferenceFromObject(first)).GetMinimumDistance(
                part.CreateReferenceFromObject(second)))
            return json.dumps({"document": doc.Name, "face1": face1_name, "face2": face2_name,
                               "minimum_distance_mm": distance, "state": "CONTACT" if distance <= 1e-6 else "CLEARANCE",
                               "method": "CATIA_SPA_FACE_MINIMUM_DISTANCE", "measurement_quality": "EXACT",
                               "source_document_saved_by_tool": False}, ensure_ascii=False, indent=2)
        finally:
            selection.Clear()

    def _resolve_surface_id(self, surface_id: str) -> Any:
        part = self.conn.get_active_part()
        prefix = "GeometricalSets/"
        if not surface_id.startswith(prefix):
            raise ValueError("surface_id must start with GeometricalSets/")
        segments = surface_id[len(prefix):].split("/")
        collections = part.HybridBodies
        container = None
        for segment in segments[:-1]:
            name, _, ordinal = segment.rpartition("#")
            index = int(ordinal) if ordinal.isdigit() else 1
            matches = [collections.Item(i) for i in range(1, collections.Count + 1)
                       if str(collections.Item(i).Name) == (name or segment)]
            if index < 1 or index > len(matches):
                raise RuntimeError(f"Surface container not found: {segment}")
            container = matches[index - 1]
            collections = container.HybridBodies
        if container is None:
            raise RuntimeError("Surface ID contains no geometrical-set container")
        leaf, _, ordinal = segments[-1].rpartition("#")
        shape_index = int(ordinal) if ordinal.isdigit() else 0
        if shape_index < 1 or shape_index > container.HybridShapes.Count:
            raise RuntimeError(f"Surface index out of range: {segments[-1]}")
        shape = container.HybridShapes.Item(shape_index)
        if leaf and str(shape.Name) != leaf:
            raise RuntimeError("Surface ID no longer matches the current model")
        return shape

    def _measure_surface_id_distance(self, surface_id1: str, surface_id2: str) -> str:
        self.conn.ensure_connected()
        if surface_id1 == surface_id2:
            raise ValueError("surface IDs must be different")
        part = self.conn.get_active_part()
        first, second = self._resolve_surface_id(surface_id1), self._resolve_surface_id(surface_id2)
        distance = float(self.conn.spa_workbench.GetMeasurable(
            part.CreateReferenceFromObject(first)).GetMinimumDistance(part.CreateReferenceFromObject(second)))
        return json.dumps({"document": self.conn.active_document.Name, "surface_id1": surface_id1,
                           "surface_id2": surface_id2, "minimum_distance_mm": distance,
                           "state": "CONTACT" if distance <= 1e-6 else "CLEARANCE",
                           "method": "CATIA_SPA_UNIQUE_SURFACE_ID_DISTANCE",
                           "measurement_quality": "EXACT", "source_saved_by_tool": False},
                          ensure_ascii=False, indent=2)
    def _measure_product_distance(
        self, elem1_name: str, elem2_name: str,
        chord_tolerance: float, contact_tolerance: float,
    ) -> str:
        self.conn.ensure_connected()
        if elem1_name == elem2_name:
            raise ValueError("element1 and element2 must be different")
        if not math.isfinite(contact_tolerance) or contact_tolerance < 0:
            raise ValueError("contact_tolerance must be non-negative")
        doc = self.conn.active_document
        if not doc.Name.lower().endswith(".catproduct"):
            raise RuntimeError("Active document is not a CATProduct")
        root = doc.Product
        arrangement = arrangement_product(root)
        run1, run2 = resolve_run(arrangement, elem1_name), resolve_run(arrangement, elem2_name)
        line1, diameter1, arc_count1 = run_polyline(run1, root, chord_tolerance)
        line2, diameter2, arc_count2 = run_polyline(run2, root, chord_tolerance)
        center_distance, point1, point2 = polyline_distance(line1, line2)
        clearance = center_distance - (diameter1 + diameter2) / 2.0
        state = (
            "INTERFERENCE" if clearance < -contact_tolerance else
            "CLEARANCE" if clearance > contact_tolerance else "CONTACT"
        )
        return json.dumps({
            "document": doc.Name,
            "method": "ARRANGEMENT_CENTERLINE_WITH_BEND_ARC_CHORDING",
            "element1": elem1_name,
            "element2": elem2_name,
            "diameter1_mm": round(diameter1, 6),
            "diameter2_mm": round(diameter2, 6),
            "centerline_distance_mm": round(center_distance, 6),
            "signed_surface_clearance_mm": round(clearance, 6),
            "interference_depth_mm": round(max(0.0, -clearance), 6),
            "state": state,
            "closest_centerline_point1_mm": [round(value, 6) for value in point1],
            "closest_centerline_point2_mm": [round(value, 6) for value in point2],
            "chord_tolerance_mm": chord_tolerance,
            "contact_tolerance_mm": contact_tolerance,
            "polyline_segments": [len(line1) - 1, len(line2) - 1],
            "bend_arc_segments": [arc_count1, arc_count2],
            "accuracy_note": "Straight segments are analytic; bend arcs use bounded-sagitta chording.",
        }, indent=2, ensure_ascii=False)

    def _measure_route_to_component(
        self, route_name: str, component_name: str,
        chord_tolerance: float, contact_tolerance: float,
    ) -> str:
        self.conn.ensure_connected()
        if not math.isfinite(contact_tolerance) or contact_tolerance < 0:
            raise ValueError("contact_tolerance must be non-negative")
        doc = self.conn.active_document
        if not doc.Name.lower().endswith(".catproduct"):
            raise RuntimeError("Active document is not a CATProduct")
        root = doc.Product
        route = resolve_run(arrangement_product(root), route_name)
        polyline, diameter, arc_count = run_polyline(route, root, chord_tolerance)
        vertices, triangles, matrix = component_mesh(self.conn.app, doc, root, component_name)
        axis_distance, axis_point, solid_point = polyline_mesh_distance(polyline, vertices, triangles)
        clearance = axis_distance - diameter / 2.0
        state = (
            "INTERFERENCE" if clearance < -contact_tolerance else
            "CLEARANCE" if clearance > contact_tolerance else "CONTACT"
        )
        bounds = [
            min(point[axis] for point in vertices) for axis in range(3)
        ] + [
            max(point[axis] for point in vertices) for axis in range(3)
        ]
        return json.dumps({
            "document": doc.Name,
            "route": route_name,
            "component": component_name,
            "route_diameter_mm": round(diameter, 6),
            "axis_to_solid_distance_mm": round(axis_distance, 6),
            "signed_surface_clearance_mm": round(clearance, 6),
            "interference_depth_mm": round(max(0.0, -clearance), 6),
            "state": state,
            "closest_axis_point_mm": [round(value, 6) for value in axis_point],
            "closest_solid_point_mm": [round(value, 6) for value in solid_point],
            "component_bounding_box_mm": [round(value, 6) for value in bounds],
            "component_position_matrix": [round(value, 9) for value in matrix],
            "mesh_vertices": len(vertices),
            "mesh_triangles": len(triangles),
            "route_polyline_segments": len(polyline) - 1,
            "bend_arc_segments": arc_count,
            "chord_tolerance_mm": chord_tolerance,
            "contact_tolerance_mm": contact_tolerance,
            "method": "ARRANGEMENT_CENTERLINE_TO_TRANSIENT_CATPART_STL",
            "accuracy_note": "Run bends use bounded-sagitta chording; solid uses CATIA STL tessellation.",
        }, indent=2, ensure_ascii=False)

    def _measure_component_interference(
        self, component1: str, component2: str,
        contact_tolerance: float, max_reported_points: int,
    ) -> str:
        self.conn.ensure_connected()
        if component1 == component2:
            raise ValueError("component1 and component2 must be different")
        if max_reported_points < 1:
            raise ValueError("max_reported_intersection_points must be at least 1")
        doc = self.conn.active_document
        if not doc.Name.lower().endswith(".catproduct"):
            raise RuntimeError("Active document is not a CATProduct")
        root = doc.Product
        products = root.Products
        resolved = []
        for exact_name in (component1, component2):
            matches = [products.Item(i) for i in range(1, products.Count + 1) if products.Item(i).Name == exact_name]
            if not matches:
                raise ValueError(f"No top-level component named '{exact_name}'")
            if len(matches) > 1:
                raise ValueError(f"Component name '{exact_name}' is ambiguous")
            resolved.append(matches[0])

        selection = doc.Selection
        previous_selection = []
        for index in range(1, selection.Count2 + 1):
            try:
                previous_selection.append(selection.Item2(index).Value)
            except Exception:
                continue
        clashes = root.GetTechnologicalObject("Clashes")
        clash_count = clashes.Count
        conflict_data = []
        try:
            selection.Clear()
            selection.Add(resolved[0])
            selection.Add(resolved[1])
            clash = clashes.AddFromSel()
            clash.ComputationType = 1  # catClashComputationTypeInsideOne
            clash.InterferenceType = 1  # catClashInterferenceTypeClearance
            clash.Clearance = max(contact_tolerance, 1e-6)
            clash.Compute()
            conflicts = clash.Conflicts
            for index in range(1, conflicts.Count + 1):
                conflict = conflicts.Item(index)
                conflict_data.append({
                    "name": str(conflict.Name),
                    "type_code": int(conflict.Type),
                    "value_mm": float(conflict.Value),
                    "first_product": str(conflict.FirstProduct.Name),
                    "second_product": str(conflict.SecondProduct.Name),
                })
        finally:
            while clashes.Count > clash_count:
                clashes.Remove(clashes.Count)
            selection.Clear()
            for item in previous_selection:
                try:
                    selection.Add(item)
                except Exception:
                    continue

        clash_conflicts = [item for item in conflict_data if item["type_code"] == 0]
        contact_conflicts = [item for item in conflict_data if item["type_code"] == 1]
        if clash_conflicts:
            state = "INTERFERENCE"
        elif contact_conflicts:
            state = "CONTACT"
        else:
            state = "CLEARANCE"
        controlling = min(conflict_data, key=lambda item: item["value_mm"]) if conflict_data else None
        value = controlling["value_mm"] if controlling else None
        result = {
            "document": doc.Name,
            "component1": component1,
            "component2": component2,
            "state": state,
            "signed_surface_clearance_mm": round(value, 6) if value is not None else None,
            "interference_depth_mm": round(max(0.0, -value), 6) if state == "INTERFERENCE" and value is not None else 0.0,
            "conflict_count": len(conflict_data),
            "conflicts": conflict_data[:max_reported_points],
            "contact_tolerance_mm": contact_tolerance,
            "method": "CATIA_DMU_SPACE_ANALYSIS_CLASH",
            "accuracy_note": (
                "Computed by CATIA's native Clash engine from product geometry; images are not used. "
                "The transient Clash specification is removed after computation."
            ),
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @staticmethod
    def _conflict_record(conflict: Any) -> dict[str, Any]:
        type_code = int(conflict.Type)
        type_name = {0: "CLASH", 1: "CONTACT", 2: "CLEARANCE"}.get(
            type_code, f"UNKNOWN_{type_code}"
        )
        value = float(conflict.Value)
        first = conflict.FirstProduct
        second = conflict.SecondProduct
        return {
            "name": str(conflict.Name),
            "type": type_name,
            "type_code": type_code,
            "value_mm": round(value, 6),
            "interference_depth_mm": round(max(0.0, -value), 6) if type_code == 0 else 0.0,
            "first_product": str(first.Name),
            "first_part_number": str(first.PartNumber),
            "second_product": str(second.Name),
            "second_part_number": str(second.PartNumber),
        }

    def _scan_product_clashes(
        self, clearance: float, scope_names: list[str] | None,
        exclude_pairs: list[list[str]], max_conflicts: int,
    ) -> str:
        self.conn.ensure_connected()
        if not math.isfinite(clearance) or clearance <= 0:
            raise ValueError("clearance must be positive")
        if max_conflicts < 1:
            raise ValueError("max_conflicts must be at least 1")
        doc = self.conn.active_document
        if not doc.Name.lower().endswith(".catproduct"):
            raise RuntimeError("Active document is not a CATProduct")
        root = doc.Product
        products = root.Products
        available = [products.Item(i).Name for i in range(1, products.Count + 1)]
        requested = list(scope_names or [])
        if requested:
            if len(requested) < 2:
                raise ValueError("scope_component_names must contain at least two names")
            if len(set(requested)) != len(requested):
                raise ValueError("scope_component_names contains duplicates")
            missing = [name for name in requested if name not in available]
            if missing:
                raise ValueError(f"Unknown top-level component names: {missing}")

        normalized_exclusions: set[frozenset[str]] = set()
        for pair in exclude_pairs:
            if len(pair) != 2 or pair[0] == pair[1]:
                raise ValueError("Each exclude_pairs item must contain two different names")
            normalized_exclusions.add(frozenset((str(pair[0]), str(pair[1]))))

        selection = doc.Selection
        previous_selection = []
        for index in range(1, selection.Count2 + 1):
            try:
                previous_selection.append(selection.Item2(index).Value)
            except Exception:
                continue
        saved_before = bool(doc.Saved)
        records: list[dict[str, Any]] = []
        raw_count = 0
        truncated = False
        temporary_doc = None
        cleanup_verified = False
        direct_transient_fallback = False
        direct_clashes = None
        try:
            # CATIA stores a Clash analysis under the CATProduct and marks that
            # document dirty even if the analysis is removed afterwards. Copying
            # component references to a disposable product isolates that side
            # effect while retaining CATIA's exact geometry computation.
            selection.Clear()
            names_to_copy = requested or available
            for name in names_to_copy:
                selection.Add(products.Item(name))
            selection.Copy()
            selection.Clear()

            temporary_doc = self.conn.app.Documents.Add("Product")
            target_selection = temporary_doc.Selection
            target_selection.Clear()
            target_selection.Add(temporary_doc.Product)
            try:
                target_selection.Paste()
                target_selection.Clear()
                temporary_doc.Product.Update()
                clashes = temporary_doc.Product.GetTechnologicalObject("Clashes")
            except Exception:
                target_selection.Clear()
                temporary_doc.Close()
                temporary_doc = None
                source_path = str(getattr(doc, "Path", "") or "").strip()
                # A STEP/IGES opened directly by CATIA is a transient CATProduct.
                # Depending on the CATIA release it may report Saved=True even
                # though Path is empty and no CATProduct exists on disk.  Path is
                # therefore the reliable boundary: never run direct DMU against a
                # file-backed supplier document, but permit it for pathless imports
                # whose external references cannot be pasted into a scratch product.
                # The transient Clash is removed in finally.
                if source_path:
                    raise
                direct_transient_fallback = True
                direct_clashes = root.GetTechnologicalObject("Clashes")
                clashes = direct_clashes
            clash = clashes.Add()
            clash.ComputationType = 0  # catClashComputationTypeBetweenAll
            clash.InterferenceType = 1  # catClashInterferenceTypeClearance
            clash.Clearance = clearance
            clash.Compute()
            conflicts = clash.Conflicts
            raw_count = int(conflicts.Count)
            for index in range(1, min(raw_count, max_conflicts) + 1):
                record = self._conflict_record(conflicts.Item(index))
                key = frozenset((record["first_product"], record["second_product"]))
                record["rule_status"] = "EXEMPTED" if key in normalized_exclusions else "UNFILTERED"
                records.append(record)
            truncated = raw_count > max_conflicts
        finally:
            if direct_clashes is not None:
                try:
                    direct_clashes.Remove(direct_clashes.Count)
                    cleanup_verified = True
                except Exception:
                    cleanup_verified = False
            if temporary_doc is not None:
                try:
                    temporary_doc.Close()
                    cleanup_verified = True
                finally:
                    doc.Activate()
            selection.Clear()
            for item in previous_selection:
                try:
                    selection.Add(item)
                except Exception:
                    continue

        counts = {"CLASH": 0, "CONTACT": 0, "CLEARANCE": 0, "EXEMPTED": 0}
        for record in records:
            counts[record["type"]] = counts.get(record["type"], 0) + 1
            if record["rule_status"] == "EXEMPTED":
                counts["EXEMPTED"] += 1
        return json.dumps({
            "document": doc.Name,
            "root_product": str(root.Name),
            "method": "CATIA_DMU_SPACE_ANALYSIS_ISOLATED_SINGLE_COMPUTE",
            "computation_type": "BETWEEN_ALL",
            "interference_type": "CLEARANCE_CONTACT_CLASH",
            "clearance_mm": clearance,
            "top_level_component_count": len(available),
            "scope_component_count": len(requested) if requested else len(available),
            "raw_conflict_count": raw_count,
            "returned_conflict_count": len(records),
            "truncated": truncated,
            "counts": counts,
            "conflicts": records,
            "temporary_product_used": not direct_transient_fallback,
            "direct_transient_step_fallback": direct_transient_fallback,
            "cleanup_verified": cleanup_verified,
            "source_document_saved_before": saved_before,
            "source_document_saved_after": bool(doc.Saved),
            "source_saved_by_tool": False,
            "accuracy_note": (
                "One native CATIA DMU Clash computation. Saved CATProducts use a disposable copy. "
                "An unsaved STEP-import CATProduct may use direct transient analysis when CATIA "
                "cannot paste its references; the Clash is removed immediately. No external "
                "N*(N-1)/2 COM loop is used. rule_status is post-processing only."
            ),
        }, indent=2, ensure_ascii=False)

    def _get_inertia(self, density: float | None = None) -> str:
        self.conn.ensure_connected()
        spa = self.conn.spa_workbench
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        ref = part.CreateReferenceFromObject(body)

        measurable = spa.GetMeasurable(ref)

        result: dict[str, Any] = {}

        try:
            volume_m3 = float(measurable.Volume)
            result["volume_raw_m3"] = volume_m3
            result["volume_mm3"] = round(volume_m3 * 1e9, 4)
            result["volume_cm3"] = round(volume_m3 * 1e6, 4)
        except Exception:
            pass

        try:
            area_m2 = float(measurable.Area)
            result["area_raw_m2"] = area_m2
            result["area_mm2"] = round(area_m2 * 1e6, 4)
            result["area_cm2"] = round(area_m2 * 1e4, 4)
        except Exception:
            pass

        try:
            cog = [0.0, 0.0, 0.0]
            measurable.GetCOG(cog)
            result["center_of_gravity_mm"] = {
                "x": round(cog[0], 4),
                "y": round(cog[1], 4),
                "z": round(cog[2], 4),
            }
        except Exception:
            pass

        if density and "volume_mm3" in result:
            volume_m3 = result["volume_mm3"] * 1e-9  # mm3 to m3
            mass_kg = density * volume_m3
            result["mass_kg"] = round(mass_kg, 6)
            result["mass_g"] = round(mass_kg * 1000, 3)
            result["density_kg_m3"] = density

        try:
            inertia = [0.0] * 9
            measurable.GetInertia(inertia)
            result["inertia_matrix"] = [
                [round(inertia[0], 4), round(inertia[1], 4), round(inertia[2], 4)],
                [round(inertia[3], 4), round(inertia[4], 4), round(inertia[5], 4)],
                [round(inertia[6], 4), round(inertia[7], 4), round(inertia[8], 4)],
            ]
        except Exception:
            pass

        return json.dumps(result, indent=2)

    def _get_bounding_box(self) -> str:
        self.conn.ensure_connected()
        doc = self.conn.active_document
        if not str(doc.Name).lower().endswith(".catpart"):
            raise RuntimeError(
                "Bounding-box STL export requires an active CATPart; "
                "CATProduct export is refused to prevent CATIA modal dialogs"
            )
        points: list[tuple[float, float, float]] = []
        fd, stl_path = tempfile.mkstemp(suffix=".stl", prefix="catia_bbox_")
        os.close(fd)
        try:
            os.unlink(stl_path)
            doc.ExportData(stl_path, "stl")
            with open(stl_path, "rb") as handle:
                data = handle.read()

            binary = False
            if len(data) >= 84:
                triangle_count = struct.unpack_from("<I", data, 80)[0]
                binary = len(data) == 84 + triangle_count * 50

            if binary:
                offset = 84
                for _ in range(triangle_count):
                    offset += 12  # normal
                    for _ in range(3):
                        points.append(struct.unpack_from("<fff", data, offset))
                        offset += 12
                    offset += 2
            else:
                text = data.decode("ascii", errors="ignore")
                for line in text.splitlines():
                    fields = line.strip().split()
                    if len(fields) == 4 and fields[0].lower() == "vertex":
                        points.append((float(fields[1]), float(fields[2]), float(fields[3])))
        finally:
            try:
                os.unlink(stl_path)
            except OSError:
                pass

        if not points:
            raise RuntimeError("CATIA STL export returned no mesh vertices")

        xs, ys, zs = zip(*points)
        bbox = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]

        result = {
            "min": {"x": round(bbox[0], 4), "y": round(bbox[1], 4), "z": round(bbox[2], 4)},
            "max": {"x": round(bbox[3], 4), "y": round(bbox[4], 4), "z": round(bbox[5], 4)},
            "dimensions": {
                "length_x": round(bbox[3] - bbox[0], 4),
                "length_y": round(bbox[4] - bbox[1], 4),
                "length_z": round(bbox[5] - bbox[2], 4),
            },
            "accuracy": "tessellated_stl",
            "sample_count": len(points),
        }
        return json.dumps(result, indent=2)

    @staticmethod
    def _stl_bounds(document: Any) -> dict[str, Any]:
        """Export one disposable document and return tessellated AABB facts."""
        points: list[tuple[float, float, float]] = []
        fd, stl_path = tempfile.mkstemp(suffix=".stl", prefix="catia_body_bbox_")
        os.close(fd)
        try:
            os.unlink(stl_path)
            document.ExportData(stl_path, "stl")
            with open(stl_path, "rb") as handle:
                data = handle.read()
            binary = False
            if len(data) >= 84:
                triangle_count = struct.unpack_from("<I", data, 80)[0]
                binary = len(data) == 84 + triangle_count * 50
            if binary:
                offset = 84
                for _ in range(triangle_count):
                    offset += 12
                    for _ in range(3):
                        points.append(struct.unpack_from("<fff", data, offset))
                        offset += 12
                    offset += 2
            else:
                for line in data.decode("ascii", errors="ignore").splitlines():
                    fields = line.strip().split()
                    if len(fields) == 4 and fields[0].lower() == "vertex":
                        points.append(tuple(float(value) for value in fields[1:4]))
        finally:
            try:
                os.unlink(stl_path)
            except OSError:
                pass
        if not points:
            raise RuntimeError("CATIA STL export returned no mesh vertices")
        xs, ys, zs = zip(*points)
        bounds = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]
        return {
            "bounding_box_mm": [round(value, 6) for value in bounds],
            "bbox_measurement_method": "DISPOSABLE_BODY_CATPART_STL",
            "bbox_measurement_quality": "TESSELLATED",
            "bbox_sample_count": len(points),
        }

    def _get_body_geometry_batch(
        self, body_names: list[str] | None, include_bounding_box: bool,
    ) -> str:
        self.conn.ensure_connected()
        source_doc = self.conn.active_document
        if not source_doc.Name.lower().endswith(".catpart"):
            raise RuntimeError("Active document is not a CATPart")
        part = source_doc.Part
        available = {part.Bodies.Item(index).Name: part.Bodies.Item(index)
                     for index in range(1, part.Bodies.Count + 1)}
        requested = list(body_names or available)
        if len(set(requested)) != len(requested):
            raise ValueError("body_names contains duplicates")
        missing = [name for name in requested if name not in available]
        if missing:
            raise ValueError(f"Bodies not found: {missing}")

        source_selection = source_doc.Selection
        prior_selection = []
        for index in range(1, source_selection.Count2 + 1):
            try:
                prior_selection.append(source_selection.Item2(index).Value)
            except Exception:
                continue
        saved_before = bool(source_doc.Saved)
        spa = self.conn.spa_workbench
        records = []
        try:
            for body_name in requested:
                body = available[body_name]
                record: dict[str, Any] = {
                    "body_name": body_name,
                    "measurement_scope": "BODY",
                    "measurement_method": "CATIA_SPA_BODY_REFERENCE",
                    "measurement_quality": "EXACT",
                    "geometry_state": "UNAVAILABLE",
                    "capabilities": ["EXACT_BREP"],
                    "limitations": [],
                }
                try:
                    measurable = spa.GetMeasurable(part.CreateReferenceFromObject(body))
                    measured = False
                    try:
                        volume_m3 = float(measurable.Volume)
                        record["volume_raw_m3"] = volume_m3
                        record["volume_mm3"] = round(volume_m3 * 1e9, 6)
                        measured = True
                    except Exception:
                        record["limitations"].append("volume unavailable; Body may be open or empty")
                    try:
                        area_m2 = float(measurable.Area)
                        record["surface_area_raw_m2"] = area_m2
                        record["surface_area_mm2"] = round(area_m2 * 1e6, 6)
                        measured = True
                    except Exception:
                        record["limitations"].append("surface area unavailable")
                    try:
                        cog = [0.0, 0.0, 0.0]
                        measurable.GetCOG(cog)
                        centroid = [round(float(value), 6) for value in cog]
                        if any(abs(value) > 1e-12 for value in centroid):
                            record["centroid_mm"] = centroid
                            measured = True
                        else:
                            record["centroid_candidate_mm"] = centroid
                            record["limitations"].append(
                                "Body-reference GetCOG returned a zero vector; centroid is unverified")
                    except Exception:
                        record["limitations"].append("centroid unavailable")
                    record["geometry_state"] = "AVAILABLE" if measured else "UNAVAILABLE"
                    record["source_units"] = {
                        "CATIA_SPA.Volume": "m3", "CATIA_SPA.Area": "m2",
                        "CATIA_SPA.GetCOG": "active CATIA length unit (mm in this project)",
                    }
                except Exception as exc:
                    record["limitations"].append(f"CATIA SPA Body measurement failed: {type(exc).__name__}")

                if include_bounding_box:
                    record["limitations"].append(
                        "independent Body bounding box disabled: CATIA clipboard isolation "
                        "changes the source document Saved state")
                if (record.get("volume_mm3") == 0 and
                        record.get("surface_area_mm2") in (None, 0) and
                        "bounding_box_mm" not in record):
                    record["geometry_state"] = "EMPTY"
                elif record["limitations"] and record["geometry_state"] == "AVAILABLE":
                    record["geometry_state"] = "PARTIAL"
                records.append(record)
        finally:
            source_selection.Clear()
            for item in prior_selection:
                try:
                    source_selection.Add(item)
                except Exception:
                    continue
        return json.dumps({
            "schema_version": "catia.body-geometry.v0.1",
            "document": source_doc.Name,
            "measurement_scope": "BODY",
            "source_document_saved_before": saved_before,
            "source_document_saved_after": bool(source_doc.Saved),
            "source_saved_by_tool": False,
            "body_count": len(records),
            "bodies": records,
        }, indent=2, ensure_ascii=False)

    def _get_part_geometry_inventory(self, include_reference_geometry: bool) -> str:
        """Inventory CATPart bodies and hybrid geometry without creating temporary documents."""
        self.conn.ensure_connected()
        doc = self.conn.active_document
        if not doc.Name.lower().endswith(".catpart"):
            raise RuntimeError("Active document is not a CATPart")
        part, spa = doc.Part, self.conn.spa_workbench
        selection = doc.Selection
        saved_before = bool(doc.Saved)
        prior_selection = []
        for index in range(1, selection.Count2 + 1):
            try:
                prior_selection.append(selection.Item2(index).Value)
            except Exception:
                continue
        records: list[dict[str, Any]] = []

        def add_record(item: Any, path: str, *, entity_kind: str, reference_geometry: bool) -> None:
            record: dict[str, Any] = {
                "source_id": path, "source_name": str(getattr(item, "Name", path)),
                "source_path": path, "entity_kind": entity_kind,
                "geometry_kind": entity_kind if entity_kind in {"SOLID", "SURFACE"} else "UNKNOWN",
                "geometry_state": "AVAILABLE", "reference_geometry": reference_geometry,
                "measurement_method": "CATIA_SPA_OBJECT_REFERENCE",
                "measurement_quality": "EXACT", "capabilities": ["EXACT_BREP"],
                "limitations": [],
            }
            if reference_geometry:
                record["why_skipped"] = "REFERENCE_GEOMETRY"
            else:
                try:
                    measurable = spa.GetMeasurable(part.CreateReferenceFromObject(item))
                    try:
                        area_m2 = float(measurable.Area)
                        record["surface_area_mm2"] = round(area_m2 * 1e6, 6)
                    except Exception:
                        record["limitations"].append("surface area unavailable")
                    try:
                        volume_m3 = float(measurable.Volume)
                        record["volume_mm3"] = round(volume_m3 * 1e9, 6)
                    except Exception:
                        # A surface normally has no volume; this is expected and not an exclusion.
                        record["volume_mm3"] = 0.0 if entity_kind == "SURFACE" else None
                    if entity_kind == "SURFACE" and record.get("surface_area_mm2") in (None, 0):
                        record["geometry_state"] = "PARTIAL"
                except Exception as exc:
                    record["geometry_state"] = "UNAVAILABLE"
                    record["limitations"].append(
                        f"CATIA SPA geometry measurement failed: {type(exc).__name__}")
            records.append(record)

        def walk_hybrid(container: Any, path: str) -> None:
            shapes = getattr(container, "HybridShapes", None)
            if shapes is not None:
                for index in range(1, shapes.Count + 1):
                    shape = shapes.Item(index)
                    name = str(getattr(shape, "Name", f"HybridShape.{index}"))
                    class_name = type(shape).__name__.upper()
                    reference = any(token in class_name for token in ("POINT", "LINE", "CURVE", "AXIS"))
                    if not reference or include_reference_geometry:
                        add_record(shape, f"{path}/{name}#{index:06d}", entity_kind="SURFACE" if not reference else "UNKNOWN",
                                   reference_geometry=reference)
            children = getattr(container, "HybridBodies", None)
            if children is not None:
                for index in range(1, children.Count + 1):
                    child = children.Item(index)
                    child_name = str(getattr(child, "Name", f"GeometricalSet.{index}"))
                    walk_hybrid(child, f"{path}/{child_name}#{index:06d}")

        try:
            for index in range(1, part.Bodies.Count + 1):
                body = part.Bodies.Item(index)
                add_record(body, f"Bodies/{body.Name}", entity_kind="SOLID", reference_geometry=False)
            for index in range(1, part.HybridBodies.Count + 1):
                hybrid = part.HybridBodies.Item(index)
                walk_hybrid(hybrid, f"GeometricalSets/{hybrid.Name}#{index:06d}")
        finally:
            selection.Clear()
            for item in prior_selection:
                try:
                    selection.Add(item)
                except Exception:
                    continue
        return json.dumps({
            "schema_version": "catia.part-geometry-inventory.v1.0",
            "document": doc.Name, "measurement_scope": "CATPART_GEOMETRY_INVENTORY",
            "source_document_saved_before": saved_before,
            "source_document_saved_after": bool(doc.Saved), "source_saved_by_tool": False,
            "entity_count": len(records), "entities": records,
            "limitations": [
                "This inventory records geometry candidates; it does not calculate pair intersections.",
                "HybridShape runtime class names are used only to identify reference curves/points conservatively.",
            ],
        }, indent=2, ensure_ascii=False)

    def _export_active_part_tessellation(self, max_triangles: int) -> str:
        """Return active CATPart mesh while retaining source-document read-only evidence."""
        self.conn.ensure_connected()
        if max_triangles < 1:
            raise ValueError("max_triangles must be at least 1")
        doc = self.conn.active_document
        if not doc.Name.lower().endswith(".catpart"):
            raise RuntimeError("Active document is not a CATPart")
        saved_before = bool(doc.Saved)
        fd, stl_path = tempfile.mkstemp(suffix=".stl", prefix="catia_active_part_mesh_")
        os.close(fd)
        try:
            os.unlink(stl_path)
            doc.ExportData(stl_path, "stl")
            vertices, triangles = _parse_stl(stl_path)
        finally:
            try:
                os.unlink(stl_path)
            except OSError:
                pass
        if len(triangles) > max_triangles:
            raise RuntimeError(
                f"CATIA STL contains {len(triangles)} triangles, exceeding max_triangles={max_triangles}")
        return json.dumps({
            "schema_version": "catia.part-tessellation.v1.0", "document": doc.Name,
            "coordinate_space": "PART_LOCAL", "mesh": {
                "vertices_mm": [[round(value, 6) for value in point] for point in vertices],
                "triangles": [list(face) for face in triangles],
                "bounds_mm": [round(value, 6) for value in mesh_bounds(vertices)],
            },
            "triangle_count": len(triangles), "vertex_count": len(vertices),
            "method": "CATIA_EXPORTDATA_STL_TEMPORARY_FILE",
            "measurement_quality": "TESSELLATED",
            "source_document_saved_before": saved_before,
            "source_document_saved_after": bool(doc.Saved), "source_saved_by_tool": False,
            "limitations": [
                "The mesh represents the active CATPart as a whole; it is not an object-level mesh split.",
                "Tessellation tolerance is controlled by the active CATIA export settings.",
            ],
        }, indent=2, ensure_ascii=False)

    def _get_product_component_instances(self) -> str:
        self.conn.ensure_connected()
        doc = self.conn.active_document
        if not doc.Name.lower().endswith(".catproduct"):
            raise RuntimeError("Active document is not a CATProduct")
        root = doc.Product
        instances = []
        for index in range(1, root.Products.Count + 1):
            component = root.Products.Item(index)
            values = list(component.Position._oleobj_.InvokeTypes(
                1611005953, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
                ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
                tuple(0.0 for _ in range(12))))
            if len(values) != 12:
                raise RuntimeError(f"Component '{component.Name}' returned an invalid position matrix")
            matrix = [float(values[0]), float(values[3]), float(values[6]), float(values[9]),
                      float(values[1]), float(values[4]), float(values[7]), float(values[10]),
                      float(values[2]), float(values[5]), float(values[8]), float(values[11]),
                      0.0, 0.0, 0.0, 1.0]
            instances.append({"instance_id": f"TOP/{component.Name}", "component_path": f"{root.Name}/{component.Name}",
                              "name": str(component.Name), "part_number": str(component.PartNumber),
                              "world_transform": {"matrix": matrix, "method": "CATIA_MOVE_GETCOMPONENTS"}})
        return json.dumps({"schema_version": "catia.product-instances.v1.0", "document": doc.Name,
                           "root_product": str(root.Name), "instance_count": len(instances), "instances": instances,
                           "source_saved_by_tool": False}, indent=2, ensure_ascii=False)

    def _get_parameters(self, name_filter: str | None = None) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        params = part.Parameters

        result = []
        for i in range(1, params.Count + 1):
            param = params.Item(i)
            name = param.Name

            if name_filter and name_filter.lower() not in name.lower():
                continue

            info: dict[str, Any] = {"name": name}
            try:
                info["value"] = param.Value
            except Exception:
                info["value"] = "N/A"
            try:
                info["comment"] = param.Comment
            except Exception:
                pass

            result.append(info)

        if not result:
            return "No parameters found" + (f" matching '{name_filter}'" if name_filter else "")
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _set_parameter(self, name: str, value: float) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        params = part.Parameters

        param = params.Item(name)
        old_value = param.Value
        param.Value = value
        part.Update()

        self.conn.refresh_display()
        return f"Parameter '{name}' changed: {old_value} -> {value}"

    def _update_part(self) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        part.Update()
        self.conn.refresh_display()
        return "Part updated successfully"
