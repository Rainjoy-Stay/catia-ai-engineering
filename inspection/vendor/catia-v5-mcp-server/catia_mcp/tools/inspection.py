"""General CATIA model inspection and lifecycle-management tools."""

from __future__ import annotations

import json
import math
import os
import struct
import tempfile
from typing import Any

from catia_mcp.connection import CATIAConnection


def _type_name(obj: Any) -> str:
    for attr in ("Type", "TypeName"):
        try:
            value = getattr(obj, attr)
            if value:
                return str(value)
        except Exception:
            pass
    return obj.__class__.__name__


def _safe_attr(obj: Any, attr: str) -> Any | None:
    try:
        value = getattr(obj, attr)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
    except Exception:
        pass
    return None


def _mesh_from_active_document(conn: CATIAConnection) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    fd, path = tempfile.mkstemp(suffix=".stl", prefix="catia_topology_")
    os.close(fd)
    raw_triangles: list[list[tuple[float, float, float]]] = []
    try:
        os.unlink(path)
        conn.active_document.ExportData(path, "stl")
        with open(path, "rb") as handle:
            data = handle.read()
        binary = False
        if len(data) >= 84:
            count = struct.unpack_from("<I", data, 80)[0]
            binary = len(data) == 84 + count * 50
        if binary:
            offset = 84
            for _ in range(count):
                offset += 12
                triangle = []
                for _ in range(3):
                    triangle.append(struct.unpack_from("<fff", data, offset))
                    offset += 12
                raw_triangles.append(triangle)
                offset += 2
        else:
            current = []
            for line in data.decode("ascii", errors="ignore").splitlines():
                fields = line.strip().split()
                if len(fields) == 4 and fields[0].lower() == "vertex":
                    current.append((float(fields[1]), float(fields[2]), float(fields[3])))
                    if len(current) == 3:
                        raw_triangles.append(current)
                        current = []
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    vertices: list[tuple[float, float, float]] = []
    indices: dict[tuple[float, float, float], int] = {}
    triangles: list[tuple[int, int, int]] = []
    for triangle in raw_triangles:
        tri_indices = []
        for point in triangle:
            key = tuple(round(float(value), 6) for value in point)
            if key not in indices:
                indices[key] = len(vertices)
                vertices.append(key)
            tri_indices.append(indices[key])
        triangles.append(tuple(tri_indices))
    return vertices, triangles


class InspectionTools:
    """Read and manage model structure beyond basic feature creation."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        empty = {"type": "object", "properties": {}}
        names_schema = {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Exact object names",
                }
            },
            "required": ["names"],
        }
        return [
            {
                "name": "catia_list_bodies_detailed",
                "description": "List every Body with main/in-work flags, sketches, and ordered features.",
                "inputSchema": empty,
            },
            {
                "name": "catia_create_body",
                "description": "Create a new Body and optionally make it the in-work object.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "set_in_work": {"type": "boolean", "default": True},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "catia_set_in_work_body",
                "description": "Set the active Part in-work Body by exact name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
            {
                "name": "catia_list_sketches",
                "description": "List sketches in all bodies, including support and geometry counts.",
                "inputSchema": empty,
            },
            {
                "name": "catia_get_sketch_details",
                "description": "Read geometry and constraints from a named sketch.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
            {
                "name": "catia_get_feature_details",
                "description": "Read type, parent body, parameters, and update state for a named feature.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
            {
                "name": "catia_delete_features",
                "description": "Delete named Part Design features from the active CATPart.",
                "inputSchema": names_schema,
            },
            {
                "name": "catia_delete_sketches",
                "description": "Delete named sketches from the active CATPart.",
                "inputSchema": names_schema,
            },
            {
                "name": "catia_delete_hybrid_shapes",
                "description": "Delete exact named HybridShape elements from geometrical sets in the active CATPart.",
                "inputSchema": names_schema,
            },
            {
                "name": "catia_search_elements",
                "description": "Search the active document using a CATIA Selection.Search expression.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "CATIA search expression, e.g. 'Name=Pad.1,all' or 'Topology.Face,all'",
                        },
                        "limit": {"type": "integer", "default": 200},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "catia_select_elements",
                "description": "Select active-document objects by exact names.",
                "inputSchema": names_schema,
            },
            {
                "name": "catia_select_issue_bodies",
                "description": "Select exact CATIA Bodies referenced by an inspection report Issue ID; validates document, Body index, and Body name before selection.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "report_path": {"type": "string"},
                        "issue_id": {"type": "string"},
                    },
                    "required": ["report_path", "issue_id"],
                },
            },
            {
                "name": "catia_select_issue_target",
                "description": "Select a report Issue ID as an exact CATPart Body pair or unique CATProduct component pair; unsupported mappings are rejected.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"report_path": {"type": "string"}, "issue_id": {"type": "string"}},
                    "required": ["report_path", "issue_id"],
                },
            },
            {
                "name": "catia_get_selection",
                "description": "Return the current CATIA selection with names and types.",
                "inputSchema": empty,
            },
            {
                "name": "catia_clear_selection",
                "description": "Clear the current CATIA selection.",
                "inputSchema": empty,
            },
            {
                "name": "catia_set_visibility",
                "description": "Show or hide named active-document objects.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "names": {"type": "array", "items": {"type": "string"}},
                        "visible": {"type": "boolean"},
                    },
                    "required": ["names", "visible"],
                },
            },
            {
                "name": "catia_hide_all_sketches",
                "description": "Hide every sketch in the active CATPart or CATProduct, including nested components.",
                "inputSchema": empty,
            },
            {
                "name": "catia_list_topology",
                "description": "List faces, edges, or vertices and best-effort measurable data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["face", "edge", "vertex"]},
                        "limit": {"type": "integer", "default": 500},
                    },
                    "required": ["kind"],
                },
            },
            {
                "name": "catia_extract_exact_faces",
                "description": "Extract native CATIA B-Rep faces as read-only geometry records; zero-volume faces are retained.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "default": 500}},
                },
            },
            {
                "name": "catia_validate_part",
                "description": "Run a structural health check on the active CATPart.",
                "inputSchema": empty,
            },
            {
                "name": "catia_get_model_manifest",
                "description": "Recursively inventory the active CATPart or CATProduct and optionally save a JSON model baseline.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "output_path": {"type": "string"},
                        "include_parameters": {"type": "boolean", "default": True},
                    },
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        routes = {
            "catia_list_bodies_detailed": lambda: self._list_bodies(),
            "catia_create_body": lambda: self._create_body(
                arguments["name"], arguments.get("set_in_work", True)
            ),
            "catia_set_in_work_body": lambda: self._set_in_work_body(arguments["name"]),
            "catia_list_sketches": lambda: self._list_sketches(),
            "catia_get_sketch_details": lambda: self._get_sketch_details(arguments["name"]),
            "catia_get_feature_details": lambda: self._get_feature_details(arguments["name"]),
            "catia_delete_features": lambda: self._delete_named(arguments["names"], "feature"),
            "catia_delete_sketches": lambda: self._delete_named(arguments["names"], "sketch"),
            "catia_delete_hybrid_shapes": lambda: self._delete_hybrid_shapes(arguments["names"]),
            "catia_search_elements": lambda: self._search(
                arguments["query"], arguments.get("limit", 200)
            ),
            "catia_select_elements": lambda: self._select(arguments["names"]),
            "catia_select_issue_bodies": lambda: self._select_issue_bodies(
                arguments["report_path"], arguments["issue_id"]
            ),
            "catia_select_issue_target": lambda: self._select_issue_target(
                arguments["report_path"], arguments["issue_id"]
            ),
            "catia_get_selection": lambda: self._get_selection(),
            "catia_clear_selection": lambda: self._clear_selection(),
            "catia_set_visibility": lambda: self._set_visibility(
                arguments["names"], arguments["visible"]
            ),
            "catia_hide_all_sketches": lambda: self._hide_all_sketches(),
            "catia_list_topology": lambda: self._list_topology(
                arguments["kind"], arguments.get("limit", 500)
            ),
            "catia_extract_exact_faces": lambda: self._extract_exact_faces(
                int(arguments.get("limit", 500))
            ),
            "catia_validate_part": lambda: self._validate_part(),
            "catia_get_model_manifest": lambda: self._model_manifest(
                arguments.get("output_path"), arguments.get("include_parameters", True)
            ),
        }
        if tool_name not in routes:
            raise ValueError(f"Unknown inspection tool: {tool_name}")
        return routes[tool_name]()

    def _iter_bodies(self) -> list[Any]:
        part = self.conn.get_active_part()
        return [part.Bodies.Item(i) for i in range(1, part.Bodies.Count + 1)]

    def _find_sketch(self, name: str) -> tuple[Any, Any]:
        for body in self._iter_bodies():
            for i in range(1, body.Sketches.Count + 1):
                sketch = body.Sketches.Item(i)
                if sketch.Name == name:
                    return body, sketch
        raise RuntimeError(f"Sketch not found: {name}")

    def _find_feature(self, name: str) -> tuple[Any, Any]:
        for body in self._iter_bodies():
            for i in range(1, body.Shapes.Count + 1):
                feature = body.Shapes.Item(i)
                if feature.Name == name:
                    return body, feature
        raise RuntimeError(f"Feature not found: {name}")

    def _find_hybrid_shape(self, name: str) -> tuple[Any, Any]:
        part = self.conn.get_active_part()

        def walk(collection: Any) -> tuple[Any, Any] | None:
            for i in range(1, collection.Count + 1):
                hybrid_body = collection.Item(i)
                for j in range(1, hybrid_body.HybridShapes.Count + 1):
                    shape = hybrid_body.HybridShapes.Item(j)
                    if shape.Name == name:
                        return hybrid_body, shape
                result = walk(hybrid_body.HybridBodies)
                if result is not None:
                    return result
            return None

        result = walk(part.HybridBodies)
        if result is None:
            raise RuntimeError(f"HybridShape not found: {name}")
        return result

    def _list_bodies(self) -> str:
        part = self.conn.get_active_part()
        active_body_name = _safe_attr(self.conn.get_active_part_body(), "Name")
        result = []
        for body in self._iter_bodies():
            result.append({
                "name": body.Name,
                "is_main": body.Name == part.MainBody.Name,
                "is_in_work": body.Name == active_body_name,
                "feature_count": body.Shapes.Count,
                "features": [body.Shapes.Item(i).Name for i in range(1, body.Shapes.Count + 1)],
                "sketch_count": body.Sketches.Count,
                "sketches": [body.Sketches.Item(i).Name for i in range(1, body.Sketches.Count + 1)],
            })
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _create_body(self, name: str, set_in_work: bool) -> str:
        part = self.conn.get_active_part()
        if any(body.Name == name for body in self._iter_bodies()):
            raise ValueError(f"Body already exists: {name}")
        body = part.Bodies.Add()
        body.Name = name
        if set_in_work:
            part.InWorkObject = body
        part.Update()
        return json.dumps({"created": body.Name, "set_in_work": set_in_work})

    def _set_in_work_body(self, name: str) -> str:
        part = self.conn.get_active_part()
        body = part.Bodies.Item(name)
        part.InWorkObject = body
        return f"In-work Body set to '{body.Name}'"

    def _list_sketches(self) -> str:
        result = []
        for body in self._iter_bodies():
            for i in range(1, body.Sketches.Count + 1):
                sketch = body.Sketches.Item(i)
                result.append({
                    "name": sketch.Name,
                    "body": body.Name,
                    "geometry_count": sketch.GeometricElements.Count,
                    "constraint_count": sketch.Constraints.Count,
                    "support": _safe_attr(sketch, "Support"),
                })
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _get_sketch_details(self, name: str) -> str:
        body, sketch = self._find_sketch(name)
        geometry = []
        elements = sketch.GeometricElements
        for i in range(1, elements.Count + 1):
            item = elements.Item(i)
            entry: dict[str, Any] = {
                "index": i,
                "name": _safe_attr(item, "Name") or f"Geometry.{i}",
                "type": _type_name(item),
            }
            for attr in ("Radius", "StartAngle", "EndAngle", "Construction"):
                value = _safe_attr(item, attr)
                if value is not None:
                    entry[attr.lower()] = value
            geometry.append(entry)

        constraints = []
        for i in range(1, sketch.Constraints.Count + 1):
            constraint = sketch.Constraints.Item(i)
            dimension = _safe_attr(constraint, "Dimension")
            constraints.append({
                "index": i,
                "name": _safe_attr(constraint, "Name") or f"Constraint.{i}",
                "type": _safe_attr(constraint, "Type"),
                "status": _safe_attr(constraint, "Status"),
                "value": _safe_attr(dimension, "Value"),
            })
        return json.dumps({
            "name": sketch.Name,
            "body": body.Name,
            "geometry": geometry,
            "constraints": constraints,
        }, indent=2, ensure_ascii=False)

    def _get_feature_details(self, name: str) -> str:
        part = self.conn.get_active_part()
        body, feature = self._find_feature(name)
        details: dict[str, Any] = {
            "name": feature.Name,
            "type": _type_name(feature),
            "body": body.Name,
        }
        try:
            details["up_to_date"] = bool(part.IsUpToDate(feature))
        except Exception:
            pass
        for attr in ("DirectionOrientation", "DirectionType", "IsSymmetric", "IsThin"):
            value = _safe_attr(feature, attr)
            if value is not None:
                details[attr] = value
        for limit_name in ("FirstLimit", "SecondLimit"):
            try:
                limit = getattr(feature, limit_name)
                details[limit_name] = {
                    "limit_mode": _safe_attr(limit, "LimitMode"),
                    "dimension": _safe_attr(getattr(limit, "Dimension", None), "Value"),
                }
            except Exception:
                pass
        return json.dumps(details, indent=2, ensure_ascii=False)

    def _delete_named(self, names: list[str], kind: str) -> str:
        if not names:
            raise ValueError("names must not be empty")
        doc = self.conn.active_document
        objects = []
        for name in dict.fromkeys(names):
            _, obj = self._find_feature(name) if kind == "feature" else self._find_sketch(name)
            objects.append(obj)
        selection = doc.Selection
        selection.Clear()
        for obj in objects:
            selection.Add(obj)
        selection.Delete()
        selection.Clear()
        self.conn.get_active_part().Update()
        return json.dumps({"deleted": names, "kind": kind}, ensure_ascii=False)

    def _delete_hybrid_shapes(self, names: list[str]) -> str:
        if not names:
            raise ValueError("names must not be empty")
        doc = self.conn.active_document
        objects = []
        resolved = []
        for name in dict.fromkeys(names):
            parent, obj = self._find_hybrid_shape(name)
            objects.append(obj)
            resolved.append({"name": obj.Name, "parent_set": parent.Name})
        selection = doc.Selection
        selection.Clear()
        for obj in objects:
            selection.Add(obj)
        selection.Delete()
        selection.Clear()
        self.conn.get_active_part().Update()
        return json.dumps({"deleted": resolved, "kind": "hybrid_shape"}, ensure_ascii=False)

    def _selection_items(self, limit: int = 1000) -> list[dict[str, Any]]:
        selection = self.conn.active_document.Selection
        result = []
        count = min(selection.Count, max(0, limit))
        for i in range(1, count + 1):
            selected = selection.Item(i)
            value = selected.Value
            result.append({
                "index": i,
                "name": _safe_attr(value, "Name") or _safe_attr(selected, "Name"),
                "type": _type_name(value),
            })
        return result

    def _search(self, query: str, limit: int) -> str:
        selection = self.conn.active_document.Selection
        selection.Clear()
        selection.Search(query)
        result = {
            "query": query,
            "total": selection.Count,
            "items": self._selection_items(limit),
            "truncated": selection.Count > limit,
        }
        selection.Clear()
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _select(self, names: list[str]) -> str:
        selection = self.conn.active_document.Selection
        selection.Clear()
        missing = []
        found = []
        for name in dict.fromkeys(names):
            selection.Clear()
            selection.Search(f"Name={name},all")
            if selection.Count == 0:
                missing.append(name)
            else:
                found.extend(selection.Item(i).Value for i in range(1, selection.Count + 1))
        selection.Clear()
        for value in found:
            selection.Add(value)
        result = json.dumps({
            "selected_count": selection.Count,
            "selected": self._selection_items(),
            "missing": missing,
        }, indent=2, ensure_ascii=False)
        return result

    def _select_issue_bodies(self, report_path: str, issue_id: str) -> str:
        # Route through the reloadable extension so locator fixes do not require
        # restarting Codex or the long-running MCP server during development.
        import importlib
        from catia_mcp import dev_extensions
        importlib.reload(dev_extensions)
        return dev_extensions.dispatch(
            self.conn,
            "select_issue_bodies",
            {"report_path": report_path, "issue_id": issue_id},
        )

    def _select_issue_target(self, report_path: str, issue_id: str) -> str:
        import importlib
        from catia_mcp import dev_extensions
        importlib.reload(dev_extensions)
        return dev_extensions.dispatch(self.conn, "select_issue_target",
            {"report_path": report_path, "issue_id": issue_id})

    def _get_selection(self) -> str:
        selection = self.conn.active_document.Selection
        return json.dumps({"count": selection.Count, "items": self._selection_items()}, indent=2, ensure_ascii=False)

    def _clear_selection(self) -> str:
        self.conn.active_document.Selection.Clear()
        return "Selection cleared"

    def _set_visibility(self, names: list[str], visible: bool) -> str:
        selection = self.conn.active_document.Selection
        selection.Clear()
        missing = []
        found = []
        for name in dict.fromkeys(names):
            selection.Clear()
            selection.Search(f"Name={name},all")
            if selection.Count == 0:
                missing.append(name)
            else:
                found.extend(selection.Item(i).Value for i in range(1, selection.Count + 1))
        selection.Clear()
        for value in found:
            selection.Add(value)
        if selection.Count:
            selection.VisProperties.SetShow(0 if visible else 1)
        changed = self._selection_items()
        selection.Clear()
        return json.dumps({"visible": visible, "changed": changed, "missing": missing}, indent=2, ensure_ascii=False)

    def _hide_all_sketches(self) -> str:
        selection = self.conn.active_document.Selection
        selection.Clear()
        # CATPrtSearch searches through all referenced CATParts when the active
        # document is a CATProduct.
        selection.Search("CATPrtSearch.Sketch,all")
        count = selection.Count
        if count:
            selection.VisProperties.SetShow(1)
        selection.Clear()
        construction_sets = 0
        try:
            root = self.conn.get_active_product()
            products = root.Products
            seen = set()
            for i in range(1, products.Count + 1):
                component = products.Item(i)
                try:
                    part_doc = component.ReferenceProduct.Parent
                    key = part_doc.FullName
                    if key in seen:
                        continue
                    seen.add(key)
                    hybrid_bodies = part_doc.Part.HybridBodies
                    selection.Clear()
                    for j in range(1, hybrid_bodies.Count + 1):
                        selection.Add(hybrid_bodies.Item(j))
                    if selection.Count:
                        construction_sets += selection.Count
                        selection.VisProperties.SetShow(1)
                except Exception:
                    continue
        except Exception:
            pass
        selection.Clear()
        self.conn.refresh_display()
        return json.dumps({"hidden_sketches": count, "hidden_geometrical_sets": construction_sets}, ensure_ascii=False)

    def _model_manifest(self, output_path: str | None, include_parameters: bool) -> str:
        self.conn.ensure_connected()
        document = self.conn.active_document

        def collection_items(collection: Any) -> list[Any]:
            try:
                return [collection.Item(i) for i in range(1, collection.Count + 1)]
            except Exception:
                return []

        def part_record(part_doc: Any) -> dict[str, Any]:
            part = part_doc.Part
            bodies = []
            for body in collection_items(part.Bodies):
                bodies.append({
                    "name": body.Name,
                    "in_work": _safe_attr(part.InWorkObject, "Name") == body.Name,
                    "shapes": [
                        {"index": i, "name": shape.Name, "type": _type_name(shape)}
                        for i, shape in enumerate(collection_items(body.Shapes), 1)
                    ],
                    "sketches": [
                        {
                            "index": i, "name": sketch.Name, "type": _type_name(sketch),
                            "geometry_count": _safe_attr(sketch.GeometricElements, "Count"),
                            "constraint_count": _safe_attr(sketch.Constraints, "Count"),
                        }
                        for i, sketch in enumerate(collection_items(body.Sketches), 1)
                    ],
                })
            geometrical_sets = []
            for hybrid_body in collection_items(part.HybridBodies):
                geometrical_sets.append({
                    "name": hybrid_body.Name,
                    "elements": [
                        {"index": i, "name": shape.Name, "type": _type_name(shape)}
                        for i, shape in enumerate(collection_items(hybrid_body.HybridShapes), 1)
                    ],
                })
            relations = [
                {"index": i, "name": rel.Name, "type": _type_name(rel), "value": _safe_attr(rel, "Value")}
                for i, rel in enumerate(collection_items(part.Relations), 1)
            ]
            parameters = []
            if include_parameters:
                for i, parameter in enumerate(collection_items(part.Parameters), 1):
                    parameters.append({
                        "index": i, "name": parameter.Name, "type": _type_name(parameter),
                        "value": _safe_attr(parameter, "Value"),
                    })
            return {
                "document": part_doc.Name,
                "full_path": _safe_attr(part_doc, "FullName"),
                "part_number": _safe_attr(part_doc.Product, "PartNumber"),
                "bodies": bodies,
                "geometrical_sets": geometrical_sets,
                "relations": relations,
                "parameters": parameters,
                "counts": {
                    "bodies": len(bodies),
                    "sketches": sum(len(body["sketches"]) for body in bodies),
                    "features": sum(len(body["shapes"]) for body in bodies),
                    "geometrical_sets": len(geometrical_sets),
                    "hybrid_elements": sum(len(item["elements"]) for item in geometrical_sets),
                    "relations": len(relations),
                    "parameters": len(parameters),
                },
            }

        parts: dict[str, dict[str, Any]] = {}

        def component_record(product: Any) -> dict[str, Any]:
            record = {
                "name": product.Name,
                "part_number": _safe_attr(product, "PartNumber"),
                "children": [],
            }
            try:
                ref_doc = product.ReferenceProduct.Parent
                if hasattr(ref_doc, "Part"):
                    key = _safe_attr(ref_doc, "FullName") or ref_doc.Name
                    record["part_key"] = key
                    if key not in parts:
                        parts[key] = part_record(ref_doc)
            except Exception:
                pass
            for child in collection_items(product.Products):
                record["children"].append(component_record(child))
            return record

        if hasattr(document, "Part"):
            key = _safe_attr(document, "FullName") or document.Name
            parts[key] = part_record(document)
            root = {"name": document.Name, "part_key": key, "children": []}
            document_type = "CATPart"
        else:
            root = component_record(document.Product)
            document_type = "CATProduct"

        manifest = {
            "schema_version": 1,
            "active_document": document.Name,
            "document_type": document_type,
            "assembly": root,
            "parts": parts,
            "summary": {
                "unique_parts": len(parts),
                "total_bodies": sum(p["counts"]["bodies"] for p in parts.values()),
                "total_sketches": sum(p["counts"]["sketches"] for p in parts.values()),
                "total_features": sum(p["counts"]["features"] for p in parts.values()),
                "total_hybrid_elements": sum(p["counts"]["hybrid_elements"] for p in parts.values()),
                "total_parameters": sum(p["counts"]["parameters"] for p in parts.values()),
            },
        }
        payload = json.dumps(manifest, indent=2, ensure_ascii=False)
        if output_path:
            path = os.path.abspath(output_path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(payload)
            return json.dumps({"saved_to": path, "summary": manifest["summary"]}, indent=2, ensure_ascii=False)
        return payload

    def _list_topology(self, kind: str, limit: int) -> str:
        vertices, triangles = _mesh_from_active_document(self.conn)
        items: list[dict[str, Any]] = []

        if kind == "vertex":
            total = len(vertices)
            items = [
                {"index": i + 1, "coordinates": list(point)}
                for i, point in enumerate(vertices[:limit])
            ]
        elif kind == "edge":
            edge_set = set()
            for a, b, c in triangles:
                edge_set.update((tuple(sorted((a, b))), tuple(sorted((b, c))), tuple(sorted((c, a)))))
            edges = sorted(edge_set)
            total = len(edges)
            for i, (a, b) in enumerate(edges[:limit], start=1):
                p1, p2 = vertices[a], vertices[b]
                length = math.sqrt(sum((p2[j] - p1[j]) ** 2 for j in range(3)))
                items.append({"index": i, "vertex_indices": [a + 1, b + 1], "length": length})
        else:
            total = len(triangles)
            for i, (a, b, c) in enumerate(triangles[:limit], start=1):
                p1, p2, p3 = vertices[a], vertices[b], vertices[c]
                u = tuple(p2[j] - p1[j] for j in range(3))
                v = tuple(p3[j] - p1[j] for j in range(3))
                cross = (
                    u[1] * v[2] - u[2] * v[1],
                    u[2] * v[0] - u[0] * v[2],
                    u[0] * v[1] - u[1] * v[0],
                )
                area = 0.5 * math.sqrt(sum(value * value for value in cross))
                center = [sum(point[j] for point in (p1, p2, p3)) / 3 for j in range(3)]
                items.append({
                    "index": i,
                    "vertex_indices": [a + 1, b + 1, c + 1],
                    "area": area,
                    "center": center,
                })

        return json.dumps({
            "kind": kind,
            "representation": "tessellated_stl",
            "total": total,
            "items": items,
            "truncated": total > limit,
        }, indent=2, ensure_ascii=False)

    def _extract_exact_faces(self, limit: int) -> str:
        """Read CATIA-native topology faces without STL export or model mutation."""
        self.conn.ensure_connected()
        if limit < 1:
            raise ValueError("limit must be at least 1")
        doc = self.conn.active_document
        if not doc.Name.lower().endswith(".catpart"):
            raise RuntimeError("Active document is not a CATPart")
        selection = doc.Selection
        saved_before = bool(doc.Saved)
        selection.Clear()
        try:
            selection.Search("Topology.Face,all")
            total = int(selection.Count2)
            faces = []
            spa = self.conn.spa_workbench
            part = doc.Part
            for index in range(1, min(total, limit) + 1):
                selected = selection.Item2(index)
                face = selected.Value
                record = {
                    "face_id": f"FACE_{index:06d}",
                    "name": str(getattr(face, "Name", f"Face.{index}")),
                    "type": _type_name(face),
                    "geometry_kind": "SURFACE",
                    "volume_mm3": 0.0,
                    "zero_volume_retained": True,
                    "measurement_method": "CATIA_NATIVE_BREP_FACE_REFERENCE",
                    "measurement_quality": "EXACT",
                    "world_bounds": None,
                    "bounds_quality": "UNAVAILABLE",
                    "bounds_status": "REVIEW_REQUIRED",
                    "source_document": doc.Name,
                }
                try:
                    measurable = spa.GetMeasurable(part.CreateReferenceFromObject(face))
                    try:
                        record["surface_area_mm2"] = round(float(measurable.Area) * 1e6, 6)
                    except Exception:
                        record["surface_area_mm2"] = None
                    try:
                        point = [0.0, 0.0, 0.0]
                        measurable.GetCOG(point)
                        record["centroid_mm"] = [round(float(value), 6) for value in point]
                    except Exception:
                        record["centroid_mm"] = None
                except Exception as exc:
                    record["measurement_quality"] = "PARTIAL"
                    record["measurement_error"] = type(exc).__name__
                faces.append(record)
        finally:
            selection.Clear()
        return json.dumps({
            "schema_version": "catia.exact-faces.v1.0",
            "document": doc.Name,
            "topology_authority": "CATIA_NATIVE_BREP",
            "face_count": total,
            "returned_face_count": len(faces),
            "truncated": total > limit,
            "faces": faces,
            "source_document_saved_before": saved_before,
            "source_document_saved_after": bool(doc.Saved),
            "source_saved_by_tool": False,
            "mesh_used": False,
            "bounds_note": "CATIA native Face measurable does not expose a stable per-face AABB; bounds remain explicit REVIEW until a broad-phase provider supplies them.",
        }, indent=2, ensure_ascii=False)

    def _validate_part(self) -> str:
        part = self.conn.get_active_part()
        body_results = []
        stale = []
        empty = []
        geometrical_sets = []

        def inspect_sets(collection):
            for index in range(1, collection.Count + 1):
                hybrid_body = collection.Item(index)
                shape_names = []
                for shape_index in range(1, hybrid_body.HybridShapes.Count + 1):
                    shape = hybrid_body.HybridShapes.Item(shape_index)
                    shape_names.append(shape.Name)
                    try:
                        if not part.IsUpToDate(shape):
                            stale.append(shape.Name)
                    except Exception:
                        pass
                geometrical_sets.append({
                    "name": hybrid_body.Name,
                    "shape_count": hybrid_body.HybridShapes.Count,
                    "shapes": shape_names,
                })
                inspect_sets(hybrid_body.HybridBodies)

        inspect_sets(part.HybridBodies)
        for body in self._iter_bodies():
            feature_names = []
            for i in range(1, body.Shapes.Count + 1):
                feature = body.Shapes.Item(i)
                feature_names.append(feature.Name)
                try:
                    if not part.IsUpToDate(feature):
                        stale.append(feature.Name)
                except Exception:
                    pass
            if body.Shapes.Count == 0:
                empty.append(body.Name)
            body_results.append({
                "name": body.Name,
                "features": feature_names,
                "sketch_count": body.Sketches.Count,
            })
        try:
            part.Update()
            update_ok = True
            update_error = None
        except Exception as exc:
            update_ok = False
            update_error = str(exc)
        return json.dumps({
            "part": part.Name,
            "update_ok": update_ok,
            "update_error": update_error,
            "body_count": len(body_results),
            "bodies": body_results,
            "empty_bodies": empty,
            "geometrical_set_count": len(geometrical_sets),
            "geometrical_sets": geometrical_sets,
            "stale_features_before_update": stale,
        }, indent=2, ensure_ascii=False)
