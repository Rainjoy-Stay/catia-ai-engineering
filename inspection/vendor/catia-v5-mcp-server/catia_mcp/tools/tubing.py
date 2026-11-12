"""Native CATIA V5 Tubing Design automation tools.

The implementation uses the registered CATPlantShipInterfaces and
CATArrangementInterfaces automation layers.  It deliberately fails closed:
native-object mutations are attempted only after the Tubing application has
been initialized and every named object has been resolved uniquely.
"""

from __future__ import annotations

import json
import math
import os
import shutil
from array import array
from typing import Any

from catia_mcp.connection import CATIAConnection
from catia_mcp.arrangement_geometry import node_point
from catia_checker.route_preflight_tokens import consume_preflight_token
from catia_checker.route_creation_verification import verify_created_route


def _validate_fillet_fit(points: list[tuple[float, float, float]], radii: list[float]) -> None:
    """Fail before CATIA mutation when adjacent requested bends overlap."""
    expanded = radii * (len(points) - 2) if len(radii) == 1 else radii
    setbacks = [0.0] * len(points)
    for i, radius in enumerate(expanded, 1):
        incoming = tuple(points[i][k] - points[i-1][k] for k in range(3))
        outgoing = tuple(points[i+1][k] - points[i][k] for k in range(3))
        ni, no = math.dist((0,0,0), incoming), math.dist((0,0,0), outgoing)
        cosine = sum(incoming[k]*outgoing[k] for k in range(3)) / (ni*no)
        angle = math.acos(max(-1.0, min(1.0, cosine)))
        if angle >= math.pi - 1e-6:
            raise ValueError(f"Route reverses direction at internal node {i+1}")
        setbacks[i] = radius * math.tan(angle / 2.0)
    for i, (first, second) in enumerate(zip(points, points[1:]), 1):
        available, required = math.dist(first, second), setbacks[i-1] + setbacks[i]
        if available + 1e-6 < required:
            raise ValueError(
                f"Bends overlap on segment {i}: available {available:.6g} mm, "
                f"required tangent length {required:.6g} mm"
            )


TUBING_APPLICATION_ID = 4  # CatPspIDLApplicationID.catPspIDLCATTubing
PSP_INTERFACE_NAMES = {
    "place_part": "CATIAPspPlacePart",
    "connectable": "CATIAPspConnectable",
    "connector": "CATIAPspConnector",
    "light_bend": "CATIAPspLightBend",
    "light_part": "CATIAPspLightPart",
    "stretchable_data": "CATIAPspStretchableData",
    "attribute": "CATIAPspAttribute",
    "functional": "CATIAPspFunctional",
}


class TubingTools:
    """Typed access to CATIA V5 native Tubing/Plant Ship interfaces."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        point = {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 3,
            "maxItems": 3,
            "description": "XYZ coordinates in millimetres",
        }
        return [
            {
                "name": "catia_tubing_get_capabilities",
                "description": (
                    "Read-only probe of the active CATProduct for native Tubing Design, "
                    "PspWorkbench, CATPlantShip and Arrangement automation support."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "catia_tubing_initialize",
                "description": (
                    "Initialize the native CATTubing application (application ID 4) on "
                    "the exact active CATProduct. Does not create geometry."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "catia_tubing_list_native_objects",
                "description": (
                    "Inventory native tubing lines, bendable tubes and objects exposing "
                    "Psp connectable/bend interfaces in the active CATProduct."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200}
                    },
                },
            },
            {
                "name": "catia_tubing_list_logical_lines",
                "description": "List native CATTubing logical lines available in the active CATProduct.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "catia_tubing_create_arrangement_run",
                "description": (
                    "Create a native CATIA Arrangement Run centerline in the active "
                    "CATProduct from ordered XYZ points, with bend radii and section size. "
                    "This creates an editable routing object, not a Part Design solid."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "points": {"type": "array", "items": point, "minItems": 2},
                        "up_direction": {**point, "default": [0, 0, 1]},
                        "section_diameter": {"type": "number", "exclusiveMinimum": 0},
                        "bend_radii": {
                            "type": "array",
                            "items": {"type": "number", "minimum": 0},
                            "description": "One radius per internal node, or one radius applied to all internal nodes",
                        },
                    },
                    "required": ["name", "points", "section_diameter", "bend_radii"],
                },
            },
            {
                "name": "catia_tubing_create_validated_arrangement_run",
                "description": (
                    "Create one native Arrangement Run only from a short-lived one-time "
                    "preflight token issued for an exact B-Rep PASS candidate. Route "
                    "points, per-bend radii and diameter are taken from the token and "
                    "cannot be overridden by this call."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "preflight_token": {"type": "string", "minLength": 1},
                        "up_direction": {
                            "type": "array", "items": {"type": "number"},
                            "minItems": 3, "maxItems": 3, "default": [0, 0, 1]
                        }
                    },
                    "required": ["name", "preflight_token"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "catia_tubing_create_interface_carriers",
                "description": (
                    "Create native CATTubTubingPart connector carriers at exact assembly "
                    "coordinates. Intended for attaching tubing interfaces to points on a "
                    "generic CATPart without changing that source part's type."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "interfaces": {
                            "type": "array", "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "point": point,
                                    "direction": point,
                                    "up_direction": {**point, "default": [0, 1, 0]},
                                    "source_component": {"type": "string"},
                                    "source_sketch": {"type": "string"},
                                    "source_point": {"type": "string"},
                                },
                                "required": ["name", "point", "direction"],
                            },
                        }
                    },
                    "required": ["interfaces"],
                },
            },
            {
                "name": "catia_tubing_inspect_route",
                "description": (
                    "Read centerline nodes, bend radii, length, section dimensions and "
                    "native Plant Ship interface availability for an exact route name."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"route_name": {"type": "string"}},
                    "required": ["route_name"],
                },
            },
            {
                "name": "catia_tubing_delete_route",
                "description": (
                    "Delete one exact native Arrangement Run by name and verify the "
                    "collection count. Intended for transactional cleanup of failed routes."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"route_name": {"type": "string"}},
                    "required": ["route_name"],
                },
            },
            {
                "name": "catia_tubing_set_bend_radii",
                "description": (
                    "Set native bend radii on an exact Arrangement Run or bendable tube. "
                    "The radius count must be one or match the internal-node count."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "route_name": {"type": "string"},
                        "bend_radii": {
                            "type": "array", "items": {"type": "number", "exclusiveMinimum": 0}, "minItems": 1
                        },
                    },
                    "required": ["route_name", "bend_radii"],
                },
            },
            {
                "name": "catia_tubing_connect",
                "description": (
                    "Connect two exact native Psp connectors by owner name and connector "
                    "name, then verify both report a connected state."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "owner1": {"type": "string"},
                        "connector1": {"type": "string"},
                        "owner2": {"type": "string"},
                        "connector2": {"type": "string"},
                    },
                    "required": ["owner1", "connector1", "owner2", "connector2"],
                },
            },
            {
                "name": "catia_tubing_get_attributes",
                "description": (
                    "Read native Plant Ship/Tubing attributes and parameter values from "
                    "an exact object, including line, standard, specification and size data."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_name": {"type": "string"},
                        "attribute_names": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["object_name"],
                },
            },
            {
                "name": "catia_tubing_set_attribute",
                "description": (
                    "Set one exact native Plant Ship/Tubing parameter-backed attribute, "
                    "then update and read it back."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_name": {"type": "string"},
                        "attribute_name": {"type": "string"},
                        "value": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "number"},
                                {"type": "boolean"},
                            ]
                        },
                    },
                    "required": ["object_name", "attribute_name", "value"],
                },
            },
            {
                "name": "catia_tubing_list_compatible_parts",
                "description": (
                    "Query the native catalog compatibility service for an exact logical "
                    "or functional tubing object, standard and part type."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_name": {"type": "string"},
                        "logical_line_id": {
                            "type": "string",
                            "description": "Exact Logical Line Name or PartNumber",
                        },
                        "standard": {"type": "string"},
                        "part_type": {"type": "string"},
                        "catalog_name": {"type": "string", "default": ""},
                    },
                    "required": ["standard", "part_type"],
                    "oneOf": [
                        {"required": ["object_name"]},
                        {"required": ["logical_line_id"]},
                    ],
                },
            },
            {
                "name": "catia_tubing_realize_bendable_tube",
                "description": (
                    "Realize one exact Arrangement Run as an independent physical "
                    "CATTubBendableTube component copied from a native CATIA tubing template. "
                    "Writes route definition and bend data transactionally."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "route_name": {"type": "string"},
                        "physical_name": {"type": "string"},
                        "template_file": {"type": "string"},
                        "output_file": {"type": "string"},
                        "standard": {"type": "string", "default": "SSTLMM"},
                        "function_type": {"type": "string", "default": "TubingTubeFunc"},
                        "logical_line_id": {
                            "type": "string",
                            "description": (
                                "Exact native CATTubing logical-line Name or PartNumber. "
                                "May be omitted only when exactly one logical line exists."
                            ),
                        },
                        "up_direction": {**point, "default": [0, 0, 1]},
                        "points": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3
                            },
                            "minItems": 2,
                            "description": (
                                "Optional verified XYZ route nodes used when this V5 service "
                                "pack does not marshal ArrangementNode.GetPoint output correctly"
                            )
                        },
                        "point_source": {
                            "type": "string",
                            "enum": ["arrangement_nodes", "template_geometry"],
                            "default": "arrangement_nodes",
                            "description": "Objects supplied to RouteStringPartInSpace as route-definition points",
                        },
                    },
                    "required": ["route_name", "physical_name", "template_file", "output_file"],
                },
            },
            {
                "name": "catia_tubing_probe_template",
                "description": (
                    "Open a CATIA tubing template read-only and report whether its root product "
                    "exposes the native Psp interfaces required for physical realization."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "template_file": {"type": "string"}
                    },
                    "required": ["template_file"],
                },
            },
            {
                "name": "catia_tubing_inspect_physical_tube",
                "description": (
                    "Inspect one exact physical tubing component for Psp light-part, bend, "
                    "connectable, attribute and physical-product interfaces."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"component_name": {"type": "string"}},
                    "required": ["component_name"],
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        match tool_name:
            case "catia_tubing_get_capabilities":
                return self._get_capabilities()
            case "catia_tubing_initialize":
                return self._initialize()
            case "catia_tubing_list_native_objects":
                return self._list_native_objects(int(arguments.get("limit", 200)))
            case "catia_tubing_list_logical_lines":
                return self._list_logical_lines()
            case "catia_tubing_create_arrangement_run":
                if os.environ.get("CATIA_ALLOW_UNVALIDATED_ROUTE_CREATE", "").strip().lower() not in {
                    "1", "true", "yes"
                }:
                    raise RuntimeError(
                        "Unvalidated Arrangement Run creation is disabled. Run the exact "
                        "B-Rep pipeline, issue a preflight token, then call "
                        "catia_tubing_create_validated_arrangement_run."
                    )
                return self._create_arrangement_run(arguments)
            case "catia_tubing_create_validated_arrangement_run":
                return self._create_validated_arrangement_run(arguments)
            case "catia_tubing_create_interface_carriers":
                return self._create_interface_carriers(arguments["interfaces"])
            case "catia_tubing_inspect_route":
                return self._inspect_route(arguments["route_name"])
            case "catia_tubing_delete_route":
                return self._delete_route(arguments["route_name"])
            case "catia_tubing_set_bend_radii":
                return self._set_bend_radii(arguments["route_name"], arguments["bend_radii"])
            case "catia_tubing_connect":
                return self._connect(arguments)
            case "catia_tubing_get_attributes":
                return self._get_attributes(arguments["object_name"], arguments.get("attribute_names"))
            case "catia_tubing_set_attribute":
                return self._set_attribute(arguments)
            case "catia_tubing_list_compatible_parts":
                return self._list_compatible_parts(arguments)
            case "catia_tubing_realize_bendable_tube":
                return self._realize_bendable_tube(arguments)
            case "catia_tubing_probe_template":
                return self._probe_template(arguments["template_file"])
            case "catia_tubing_inspect_physical_tube":
                return self._inspect_physical_tube(arguments["component_name"])
            case _:
                raise ValueError(f"Unknown tubing tool: {tool_name}")

    def _root_product(self) -> Any:
        doc = self.conn.active_document
        try:
            product = doc.Product
        except Exception as exc:
            raise RuntimeError("Active document must be a CATProduct for native Tubing Design") from exc
        return product

    def _psp_workbench(self) -> Any:
        root = self._root_product()
        try:
            return root.GetTechnologicalObject("PspWorkbench")
        except Exception as exc:
            raise RuntimeError(
                "PspWorkbench is unavailable. Verify the Equipment & Systems/Tubing "
                "license and that a CATProduct is active."
            ) from exc

    def _initialize_objects(self) -> tuple[Any, Any, Any]:
        source_document = self.conn.active_document
        root = self._root_product()
        workbench = self._psp_workbench()
        try:
            application = workbench.GetApplication(TUBING_APPLICATION_ID)
            application.Initialization()
        except Exception as exc:
            raise RuntimeError("Failed to initialize native CATTubing application ID 4") from exc
        # CATTubing initialization may open and activate catalog/service documents.
        # Always restore the caller's assembly before any subsequent selection,
        # placement, measurement, or save operation.
        try:
            source_document.Activate()
        except Exception as exc:
            raise RuntimeError(
                "CATTubing initialized, but the source CATProduct could not be reactivated"
            ) from exc
        if self.conn.active_document.Name != source_document.Name:
            raise RuntimeError(
                "CATTubing initialization changed the active document and CATIA did not "
                f"restore '{source_document.Name}'"
            )
        return root, workbench, application

    @staticmethod
    def _validate_vector(values: list[float], label: str, *, nonzero: bool = False) -> tuple[float, float, float]:
        if len(values) != 3 or not all(math.isfinite(float(v)) for v in values):
            raise ValueError(f"{label} must contain three finite numbers")
        vector = tuple(float(v) for v in values)
        if nonzero and math.sqrt(sum(v * v for v in vector)) < 1e-9:
            raise ValueError(f"{label} must be non-zero")
        return vector

    def _get_capabilities(self) -> str:
        result: dict[str, Any] = {
            "document": self.conn.active_document.Name,
            "document_type": "CATProduct",
            "tubing_application_id": TUBING_APPLICATION_ID,
            "psp_workbench": False,
            "tubing_application": False,
            "arrangement_product": False,
            "interfaces": {},
        }
        root = self._root_product()
        try:
            workbench = self._psp_workbench()
            result["psp_workbench"] = True
            app = workbench.GetApplication(TUBING_APPLICATION_ID)
            result["tubing_application"] = app is not None
            for key, interface_name in PSP_INTERFACE_NAMES.items():
                try:
                    result["interfaces"][key] = workbench.GetInterface(interface_name, root) is not None
                except Exception:
                    result["interfaces"][key] = False
        except Exception as exc:
            result["error"] = str(exc)
        try:
            result["arrangement_product"] = root.GetTechnologicalObject("CATIAArrangementProduct") is not None
        except Exception:
            try:
                result["arrangement_product"] = root.GetTechnologicalObject("ArrangementProduct") is not None
            except Exception:
                pass
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _initialize(self) -> str:
        root, _, application = self._initialize_objects()
        return json.dumps({
            "document": self.conn.active_document.Name,
            "root_product": root.Name,
            "application_id": TUBING_APPLICATION_ID,
            "initialized": application is not None,
        }, indent=2, ensure_ascii=False)

    def _list_logical_lines(self) -> str:
        root, workbench, application = self._initialize_objects()
        factory = workbench.GetInterface("CATIAPspAppFactory", application)
        if factory is None:
            raise RuntimeError("CATTubing application does not expose CATIAPspAppFactory")
        try:
            collection = factory.ListLogicalLines(root)
        except Exception:
            # This V5 release raises E_UNEXPECTED when the product contains no
            # logical lines instead of returning an empty CATIAPspListOfObjects.
            collection = None
        lines = []
        count = int(getattr(collection, "Count", 0)) if collection is not None else 0
        for index in range(1, count + 1):
            logical = None
            for interface_name in ("CATIAPspLogicalLine", ""):
                try:
                    logical = collection.Item(index, interface_name)
                    if logical is not None:
                        break
                except Exception:
                    continue
            if logical is None:
                continue
            entry = {"index": index}
            for attr in ("Name", "PartNumber"):
                try:
                    entry[attr] = str(getattr(logical, attr))
                except Exception:
                    pass
            try:
                entry["members_count"] = int(logical.Members.Count)
            except Exception:
                pass
            lines.append(entry)
        return json.dumps({
            "document": self.conn.active_document.Name,
            "count": len(lines),
            "logical_lines": lines,
        }, indent=2, ensure_ascii=False)

    def _resolve_logical_line(self, root: Any, workbench: Any, application: Any,
                              requested_id: str | None) -> tuple[Any, str]:
        factory = workbench.GetInterface("CATIAPspAppFactory", application)
        if factory is None:
            raise RuntimeError("CATTubing application does not expose CATIAPspAppFactory")
        collection = factory.ListLogicalLines(root)
        count = int(getattr(collection, "Count", 0)) if collection is not None else 0
        candidates: list[tuple[Any, set[str]]] = []
        for index in range(1, count + 1):
            logical = None
            for interface_name in ("CATIAPspLogicalLine", ""):
                try:
                    logical = collection.Item(index, interface_name)
                    if logical is not None:
                        break
                except Exception:
                    continue
            if logical is None:
                continue
            identifiers: set[str] = set()
            for attr in ("Name", "PartNumber"):
                try:
                    value = str(getattr(logical, attr)).strip()
                    if value:
                        identifiers.add(value)
                except Exception:
                    pass
            candidates.append((logical, identifiers))
        if requested_id:
            matches = [(obj, ids) for obj, ids in candidates if requested_id in ids]
            if len(matches) != 1:
                available = sorted({value for _, ids in candidates for value in ids})
                raise RuntimeError(
                    f"Logical line '{requested_id}' resolved to {len(matches)} objects; "
                    f"available identifiers: {available}"
                )
            return matches[0][0], requested_id
        if len(candidates) != 1:
            available = sorted({value for _, ids in candidates for value in ids})
            raise RuntimeError(
                "Physical Tubing Design realization requires one exact native logical line; "
                f"found {len(candidates)}. Supply logical_line_id after creating/importing a "
                f"Tubing Line. Available identifiers: {available}"
            )
        identifiers = sorted(candidates[0][1])
        return candidates[0][0], identifiers[0] if identifiers else "<single-logical-line>"

    def _selection_matches(self, name: str) -> list[Any]:
        selection = self.conn.active_document.Selection
        selection.Clear()
        # Quoting the value prevents wildcard expansion and keeps exact-name intent.
        escaped = name.replace("'", "''")
        selection.Search(f"Name='{escaped}',all")
        matches = []
        for index in range(1, selection.Count2 + 1):
            value = selection.Item2(index).Value
            try:
                if value.Name == name:
                    matches.append(value)
            except Exception:
                continue
        selection.Clear()
        return matches

    def _resolve_exact(self, name: str) -> Any:
        matches = self._selection_matches(name)
        if not matches:
            raise ValueError(f"No active-document object named '{name}'")
        if len(matches) > 1:
            raise ValueError(f"Object name '{name}' is ambiguous ({len(matches)} matches)")
        return matches[0]

    def _arrangement_product(self) -> Any:
        root = self._root_product()
        for token in ("CATIAArrangementProduct", "ArrangementProduct"):
            try:
                obj = root.GetTechnologicalObject(token)
                if obj is not None:
                    return obj
            except Exception:
                continue
        raise RuntimeError(
            "Active root product does not expose CATIAArrangementProduct. "
            "Convert it to an Arrangement Product in CATIA before creating a run."
        )

    def _create_arrangement_run(self, args: dict[str, Any]) -> str:
        self._initialize_objects()
        points = [self._validate_vector(p, "points[]") for p in args["points"]]
        if len(points) < 2:
            raise ValueError("At least two route points are required")
        for first, second in zip(points, points[1:]):
            if math.dist(first, second) < 1e-6:
                raise ValueError("Adjacent route points must be distinct")
        up = self._validate_vector(args.get("up_direction", [0, 0, 1]), "up_direction", nonzero=True)
        diameter = float(args["section_diameter"])
        if not math.isfinite(diameter) or diameter <= 0:
            raise ValueError("section_diameter must be positive")
        radii = [float(v) for v in args["bend_radii"]]
        internal_count = max(0, len(points) - 2)
        if internal_count == 0 and radii:
            raise ValueError("A two-point run has no bend nodes; bend_radii must be empty")
        if internal_count and len(radii) not in (1, internal_count):
            raise ValueError("bend_radii must contain one value or one per internal node")
        if any(not math.isfinite(v) or v <= 0 for v in radii):
            raise ValueError("Every bend radius must be positive")

        _validate_fillet_fit(points, radii)

        arrangement = self._arrangement_product()
        runs = arrangement.ArrangementRuns
        before = runs.Count
        # CATIA's Automation binding accepts SAFEARRAY(VARIANT) values here.
        # AddRun requires a CATIMovable relative axis; passing Automation
        # Nothing is rejected by V5 with E_INVALIDARG.  The root Product is
        # the stable assembly axis for routes expressed in global XYZ.
        flat_points = tuple(value for point in points for value in point)
        try:
            run = runs.AddRun(self._root_product(), flat_points, tuple(up))
        except Exception:
            # A rejected AddRun must be transactionally clean.  If a service
            # pack leaves a partial object behind, remove only the newly added
            # tail item before propagating the original COM error.
            while runs.Count > before:
                runs.Remove(runs.Count)
            raise
        try:
            run.Name = args["name"]
            run.SectionType = 2  # CatArrangementRouteSectionRound
            run.SectionDiameter = diameter
            run.VisuMode = 2  # CatArrangementRouteVisuModeSolid
            nodes = run.ArrangementNodes
            if internal_count:
                expanded = radii * internal_count if len(radii) == 1 else radii
                for offset, radius in enumerate(expanded, start=2):
                    nodes.Item(offset).BendRadius = radius
            self._root_product().Update()
        except Exception:
            while runs.Count > before:
                runs.Remove(runs.Count)
            raise
        after = runs.Count
        if after != before + 1:
            raise RuntimeError(f"Arrangement run count did not increase ({before} -> {after})")
        return self._inspect_route(args["name"])

    def _resolve_arrangement_run(self, route_name: str) -> tuple[Any, int]:
        runs = self._arrangement_product().ArrangementRuns
        matches: list[tuple[Any, int]] = []
        for index in range(1, runs.Count + 1):
            run = runs.Item(index)
            try:
                if run.Name == route_name:
                    matches.append((run, index))
            except Exception:
                continue
        if not matches:
            raise ValueError(f"No Arrangement Run named '{route_name}'")
        if len(matches) > 1:
            raise ValueError(f"Arrangement Run name '{route_name}' is ambiguous")
        return matches[0]

    def _create_validated_arrangement_run(self, arguments: dict[str, Any]) -> str:
        name = str(arguments["name"])
        # Exact-name uniqueness makes rollback target resolution deterministic.
        try:
            self._resolve_arrangement_run(name)
        except ValueError as exc:
            if "No Arrangement Run" not in str(exc):
                raise
        else:
            raise ValueError(f"Arrangement Run name {name!r} already exists")
        payload = consume_preflight_token(arguments["preflight_token"])
        try:
            raw = self._create_arrangement_run({
                "name": name,
                "points": [list(point) for point in payload.points],
                "section_diameter": payload.section_diameter,
                "bend_radii": list(payload.bend_radii),
                "up_direction": arguments.get("up_direction", [0, 0, 1]),
            })
            inspection = json.loads(raw)
            verification = verify_created_route(
                inspection, payload.points, payload.bend_radii,
                payload.section_diameter,
            )
            if verification["status"] != "PASS":
                rollback = json.loads(self._delete_route(name))
                raise RuntimeError(json.dumps({
                    "transaction": "ROLLED_BACK",
                    "reason": "POST_CREATE_VERIFICATION_FAILED",
                    "verification": verification,
                    "rollback": rollback,
                    "saved": False,
                }, ensure_ascii=False))
            dmu = self._validate_created_route_dmu(name, payload.component_policies)
            if dmu["status"] != "PASS":
                rollback = json.loads(self._delete_route(name))
                raise RuntimeError(json.dumps({
                    "transaction": "ROLLED_BACK",
                    "reason": "NATIVE_DMU_VALIDATION_FAILED",
                    "dmu": dmu,
                    "rollback": rollback,
                    "saved": False,
                }, ensure_ascii=False))
            return json.dumps({
                "transaction": "COMMITTED_IN_MEMORY",
                "saved": False,
                "preflight_source": payload.source_result,
                "preflight_sha256": payload.source_sha256,
                "candidate_rank": payload.candidate_rank,
                "verification": verification,
                "native_dmu": dmu,
                "route": inspection,
            }, indent=2, ensure_ascii=False, default=str)
        except Exception:
            # _create_arrangement_run already removes partial objects on its
            # own failure. If it completed but a later unexpected exception
            # occurred, remove only the uniquely named object created here.
            try:
                self._resolve_arrangement_run(name)
            except Exception:
                pass
            else:
                self._delete_route(name)
            raise

    def _validate_created_route_dmu(
        self, route_name: str, policies: tuple[tuple[str, str, float], ...],
    ) -> dict[str, Any]:
        route, _ = self._resolve_arrangement_run(route_name)
        doc = self.conn.active_document
        root = self._root_product()
        products = root.Products
        selection = doc.Selection
        clashes = root.GetTechnologicalObject("Clashes")
        results = []
        for component_name, mode, minimum_clearance in policies:
            matches = [products.Item(i) for i in range(1, products.Count + 1)
                       if str(products.Item(i).Name) == component_name]
            if len(matches) != 1:
                raise ValueError(
                    f"DMU scope component {component_name!r} resolved {len(matches)} times")
            previous = []
            for index in range(1, selection.Count2 + 1):
                try: previous.append(selection.Item2(index).Value)
                except Exception: continue
            before = clashes.Count
            conflicts = []
            try:
                selection.Clear(); selection.Add(route); selection.Add(matches[0])
                clash = clashes.AddFromSel()
                clash.ComputationType = 1
                clash.InterferenceType = 1
                clash.Clearance = max(float(minimum_clearance), 1e-6)
                clash.Compute()
                for index in range(1, clash.Conflicts.Count + 1):
                    item = clash.Conflicts.Item(index)
                    conflicts.append({"type_code": int(item.Type), "value_mm": float(item.Value)})
            finally:
                while clashes.Count > before: clashes.Remove(clashes.Count)
                selection.Clear()
                for item in previous:
                    try: selection.Add(item)
                    except Exception: continue
            has_clash = any(item["type_code"] == 0 for item in conflicts)
            has_contact = any(item["type_code"] == 1 for item in conflicts)
            low_clearance = any(
                item["type_code"] == 2 and item["value_mm"] + 1e-6 < minimum_clearance
                for item in conflicts)
            if has_clash:
                state, passed = "INTERFERENCE", False
            elif mode == "REQUIRED_CONTACT":
                state, passed = (("REQUIRED_CONTACT_OK", True) if has_contact
                                 else ("MISSING_REQUIRED_CONTACT", False))
            elif mode == "ALLOW_CONTACT":
                state, passed = ("ACCEPTED_CONTACT" if has_contact else "CLEARANCE"), True
            elif (has_contact and minimum_clearance > 1e-6) or low_clearance:
                state, passed = "INSUFFICIENT_CLEARANCE", False
            else:
                state, passed = "CLEARANCE", True
            results.append({
                "component": component_name, "policy": mode,
                "minimum_clearance_mm": minimum_clearance,
                "state": state, "passed": passed, "conflicts": conflicts,
                "method": "CATIA_DMU_SPACE_ANALYSIS_CLASH",
            })
        return {
            "status": "PASS" if results and all(item["passed"] for item in results) else "FAIL",
            "complete": bool(results) and len(results) == len(policies),
            "route_name": route_name, "components": results,
        }

    def _inspect_route(self, route_name: str) -> str:
        route, _ = self._resolve_arrangement_run(route_name)
        data: dict[str, Any] = {"name": route_name, "type": getattr(route, "Type", type(route).__name__)}
        for attr in ("Length", "SectionDiameter", "SectionWidth", "SectionHeight", "VisuMode", "SectionType"):
            try:
                data[attr] = getattr(route, attr)
            except Exception:
                pass
        try:
            nodes = route.ArrangementNodes
            data["nodes"] = []
            for index in range(1, nodes.Count + 1):
                node = nodes.Item(index)
                entry: dict[str, Any] = {"index": index}
                try:
                    entry["bend_radius"] = node.BendRadius
                    entry["bend_angle"] = node.BendAngle
                except Exception:
                    pass
                try:
                    entry["point"] = list(node_point(node, self._root_product()))
                except Exception:
                    pass
                data["nodes"].append(entry)
        except Exception:
            pass
        try:
            workbench = self._psp_workbench()
            data["native_interfaces"] = {
                key: workbench.GetInterface(name, route) is not None
                for key, name in PSP_INTERFACE_NAMES.items()
            }
        except Exception:
            data["native_interfaces"] = {}
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    def _delete_route(self, route_name: str) -> str:
        self._initialize_objects()
        _, index = self._resolve_arrangement_run(route_name)
        runs = self._arrangement_product().ArrangementRuns
        before = runs.Count
        runs.Remove(index)
        self._root_product().Update()
        after = runs.Count
        if after != before - 1:
            raise RuntimeError(f"Arrangement run count did not decrease ({before} -> {after})")
        return json.dumps({
            "deleted": route_name,
            "count_before": before,
            "count_after": after,
        }, indent=2, ensure_ascii=False)

    def _set_bend_radii(self, route_name: str, bend_radii: list[float]) -> str:
        self._initialize_objects()
        try:
            route, _ = self._resolve_arrangement_run(route_name)
        except Exception:
            route = self._resolve_exact(route_name)
        radii = [float(value) for value in bend_radii]
        if any(not math.isfinite(value) or value <= 0 for value in radii):
            raise ValueError("Every bend radius must be positive")
        updated = False
        try:
            nodes = route.ArrangementNodes
            internal_count = max(0, nodes.Count - 2)
            if internal_count == 0:
                raise ValueError("Route has no internal bend nodes")
            if len(radii) not in (1, internal_count):
                raise ValueError("bend_radii must contain one value or one per internal node")
            expanded = radii * internal_count if len(radii) == 1 else radii
            for offset, radius in enumerate(expanded, start=2):
                nodes.Item(offset).BendRadius = radius
            updated = True
        except ValueError:
            raise
        except Exception:
            workbench = self._psp_workbench()
            light_bend = workbench.GetInterface(PSP_INTERFACE_NAMES["light_bend"], route)
            if light_bend is None:
                raise RuntimeError(f"'{route_name}' exposes neither ArrangementNodes nor CATIAPspLightBend")
            light_bend.SetBendData(tuple(radii))
            updated = True
        if not updated:
            raise RuntimeError("No bend data was changed")
        self._root_product().Update()
        return self._inspect_route(route_name)

    def _connector(self, owner_name: str, connector_name: str) -> Any:
        owner = self._resolve_exact(owner_name)
        workbench = self._psp_workbench()
        connectable = workbench.GetInterface(PSP_INTERFACE_NAMES["connectable"], owner)
        if connectable is None:
            raise RuntimeError(f"'{owner_name}' does not expose CATIAPspConnectable")
        connector = connectable.GetConnectorByName(connector_name)
        if connector is None:
            raise ValueError(f"Connector '{connector_name}' not found on '{owner_name}'")
        return connector

    def _connect(self, args: dict[str, Any]) -> str:
        self._initialize_objects()
        raw1 = self._connector(args["owner1"], args["connector1"])
        raw2 = self._connector(args["owner2"], args["connector2"])
        workbench = self._psp_workbench()
        connector1 = workbench.GetInterface(PSP_INTERFACE_NAMES["connector"], raw1)
        connector2 = workbench.GetInterface(PSP_INTERFACE_NAMES["connector"], raw2)
        if connector1 is None or connector2 is None:
            raise RuntimeError("Both endpoints must expose CATIAPspConnector")
        connector1.Connect(connector2)
        self._root_product().Update()
        connected1 = bool(connector1.IsCntrConnected())
        connected2 = bool(connector2.IsCntrConnected())
        if not connected1 or not connected2:
            raise RuntimeError("CATIA returned from Connect but bidirectional verification failed")
        return json.dumps({
            "endpoint1": f"{args['owner1']}/{args['connector1']}",
            "endpoint2": f"{args['owner2']}/{args['connector2']}",
            "connected": True,
        }, indent=2, ensure_ascii=False)

    def _list_native_objects(self, limit: int) -> str:
        self._initialize_objects()
        selection = self.conn.active_document.Selection
        queries = {
            "tubing_lines": "CATPspObject.DomainID=5,all",
            "bendable_tubes": "Name=*,all",
        }
        found: dict[str, Any] = {"document": self.conn.active_document.Name, "objects": []}
        seen: set[int] = set()
        # Search broadly because startup-type queries vary across V5 service packs;
        # interface checks below are authoritative.
        for query in queries.values():
            selection.Clear()
            try:
                selection.Search(query)
            except Exception:
                continue
            for index in range(1, min(selection.Count2, limit) + 1):
                obj = selection.Item2(index).Value
                marker = id(obj)
                if marker in seen:
                    continue
                seen.add(marker)
                entry = {"name": getattr(obj, "Name", ""), "interfaces": []}
                workbench = self._psp_workbench()
                for key, interface_name in PSP_INTERFACE_NAMES.items():
                    try:
                        if workbench.GetInterface(interface_name, obj) is not None:
                            entry["interfaces"].append(key)
                    except Exception:
                        pass
                if entry["interfaces"]:
                    found["objects"].append(entry)
                    if len(found["objects"]) >= limit:
                        break
            if len(found["objects"]) >= limit:
                break
        selection.Clear()
        found["count"] = len(found["objects"])
        return json.dumps(found, indent=2, ensure_ascii=False)

    @staticmethod
    def _list_values(collection: Any) -> list[Any]:
        if collection is None:
            return []
        try:
            return [collection.Item(index) for index in range(1, collection.Count + 1)]
        except Exception:
            if isinstance(collection, (tuple, list)):
                return list(collection)
            return [collection]

    def _attribute_interface(self, object_name: str) -> Any:
        obj = self._resolve_exact(object_name)
        interface = self._psp_workbench().GetInterface(PSP_INTERFACE_NAMES["attribute"], obj)
        if interface is None:
            raise RuntimeError(f"'{object_name}' does not expose CATIAPspAttribute")
        return interface

    def _get_attributes(self, object_name: str, requested: list[str] | None) -> str:
        self._initialize_objects()
        interface = self._attribute_interface(object_name)
        names = requested
        if not names:
            try:
                names = [str(value) for value in self._list_values(interface.ListAttributes(5))]
            except Exception as exc:
                raise RuntimeError("Unable to enumerate CATTUB domain attributes") from exc
        values: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for name in names:
            try:
                parameter = interface.GetParameter(name)
                value = parameter.Value
                values[name] = value
            except Exception as exc:
                errors[name] = str(exc)
        return json.dumps({
            "object": object_name,
            "domain_id": 5,
            "attributes": values,
            "errors": errors,
        }, indent=2, ensure_ascii=False, default=str)

    def _set_attribute(self, args: dict[str, Any]) -> str:
        self._initialize_objects()
        interface = self._attribute_interface(args["object_name"])
        try:
            parameter = interface.GetParameter(args["attribute_name"])
            before = parameter.Value
            parameter.Value = args["value"]
            self._root_product().Update()
            after = parameter.Value
        except Exception as exc:
            raise RuntimeError(
                f"Unable to set native attribute '{args['attribute_name']}'. It may be "
                "derived, discrete, read-only, or incompatible with the supplied value."
            ) from exc
        return json.dumps({
            "object": args["object_name"],
            "attribute": args["attribute_name"],
            "before": before,
            "after": after,
        }, indent=2, ensure_ascii=False, default=str)

    def _list_compatible_parts(self, args: dict[str, Any]) -> str:
        root, workbench, application = self._initialize_objects()
        if args.get("logical_line_id"):
            obj, resolved_name = self._resolve_logical_line(
                root, workbench, application, args["logical_line_id"]
            )
        else:
            obj = self._resolve_exact(args["object_name"])
            resolved_name = args["object_name"]
        functional = workbench.GetInterface(PSP_INTERFACE_NAMES["functional"], obj)
        if functional is None:
            raise RuntimeError(f"'{resolved_name}' does not expose CATIAPspFunctional")
        try:
            result = functional.ListCompatiblePartNumbers(
                args["part_type"], args["standard"], args.get("catalog_name", "")
            )
        except Exception as exc:
            raise RuntimeError("Native compatible-part catalog query failed") from exc
        if not isinstance(result, tuple) or len(result) < 2:
            raise RuntimeError("CATIA returned an unexpected compatible-part result")
        part_types = self._list_values(result[-2])
        catalog_parts = self._list_values(result[-1])
        return json.dumps({
            "object": resolved_name,
            "standard": args["standard"],
            "requested_part_type": args["part_type"],
            "catalog": args.get("catalog_name", ""),
            "compatible": [
                {"part_type": str(kind), "catalog_part_name": str(part)}
                for kind, part in zip(part_types, catalog_parts)
            ],
        }, indent=2, ensure_ascii=False)

    def _exact_component(self, name: str) -> tuple[Any, int]:
        products = self._root_product().Products
        matches = [(products.Item(index), index) for index in range(1, products.Count + 1)
                   if products.Item(index).Name == name]
        if not matches:
            raise ValueError(f"No root-level component named '{name}'")
        if len(matches) > 1:
            raise ValueError(f"Component name '{name}' is ambiguous")
        return matches[0]

    def _create_interface_carriers(self, specs: list[dict[str, Any]]) -> str:
        """Create independently owned native connectors colocated with source-part points."""
        root, workbench, application = self._initialize_objects()
        build = workbench.GetInterface("CATIAPspBuildPart", application)
        if build is None:
            raise RuntimeError("CATTubing does not expose CATIAPspBuildPart")
        baseline_count = int(root.Products.Count)
        existing = {str(root.Products.Item(i).PartNumber) for i in range(1, root.Products.Count + 1)}
        names = [str(spec["name"]).strip() for spec in specs]
        if any(not name for name in names) or len(set(names)) != len(names):
            raise ValueError("Interface carrier names must be non-empty and unique")
        conflicts = sorted(set(names) & existing)
        if conflicts:
            raise ValueError(f"Interface carrier PartNumber already exists: {conflicts}")

        created: list[dict[str, Any]] = []
        created_products: list[Any] = []
        try:
            for spec, name in zip(specs, names):
                p = [float(v) for v in spec["point"]]
                d = [float(v) for v in spec["direction"]]
                u = [float(v) for v in spec.get("up_direction", [0, 1, 0])]
                dn = math.sqrt(sum(v * v for v in d))
                un = math.sqrt(sum(v * v for v in u))
                if dn <= 1e-9 or un <= 1e-9:
                    raise ValueError(f"'{name}' direction and up_direction must be non-zero")
                d = [v / dn for v in d]
                u = [v / un for v in u]
                normal = [d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]
                nn = math.sqrt(sum(v * v for v in normal))
                if nn <= 1e-6:
                    raise ValueError(f"'{name}' direction and up_direction must not be parallel")
                normal = [v / nn for v in normal]

                ref_product = build.NewPart("CATTubTubingPart", name)
                created_products.append(ref_product)
                part_doc = ref_product.Parent
                part = part_doc.Part
                hb = part.HybridBodies.Add()
                hb.Name = "TubingInterface"
                factory = part.HybridShapeFactory
                point_obj = factory.AddNewPointCoord(*p)
                point_obj.Name = "InterfacePoint"
                hb.AppendHybridShape(point_obj)
                direction_obj = factory.AddNewDirectionByCoord(*d)
                line = factory.AddNewLinePtDir(part.CreateReferenceFromObject(point_obj), direction_obj, -10.0, 10.0, False)
                line.Name = "InterfaceAxis"
                hb.AppendHybridShape(line)
                offset = -sum(normal[i] * p[i] for i in range(3))
                plane = factory.AddNewPlaneEquation(normal[0], normal[1], normal[2], offset)
                plane.Name = "InterfaceClockPlane"
                hb.AppendHybridShape(plane)
                part.Update()
                physical = workbench.GetInterface("CATIAPspPhysicalProduct", ref_product)
                if physical is None:
                    raise RuntimeError(f"Native physical interface unavailable for '{name}'")
                face_reference = part.CreateReferenceFromObject(point_obj)
                if spec.get("source_component"):
                    source_component, _ = self._exact_component(str(spec["source_component"]))
                    source_part = source_component.ReferenceProduct.Parent.Part
                    if spec.get("source_hybrid_index") is not None:
                        source_body = source_part.Bodies.Item(str(spec["source_body"]))
                        source_point = source_body.HybridShapes.Item(int(spec["source_hybrid_index"]))
                        expected_name = str(spec["source_point"])
                        if str(source_point.Name) != expected_name:
                            raise RuntimeError(
                                f"HybridShape identity mismatch: expected '{expected_name}', "
                                f"found '{source_point.Name}' at index {spec['source_hybrid_index']}"
                            )
                    else:
                        source_sketch = source_part.Bodies.Item(1).Sketches.Item(str(spec["source_sketch"]))
                        source_point = source_sketch.GeometricElements.Item(str(spec["source_point"]))
                    face_reference = source_part.CreateReferenceFromObject(source_point)
                connector = physical.AddConnector(
                    "CATTubTubingPartConnector",
                    face_reference, 3,
                    part.CreateReferenceFromObject(line), 2,
                    part.CreateReferenceFromObject(plane), 14,
                )
                if int(physical.Connectors.Count) != 1:
                    raise RuntimeError(f"Connector verification failed for '{name}'")
                component = root.Products.AddExternalComponent(part_doc)
                created.append({
                    "owner_part_number": name,
                    "component_name": str(component.Name),
                    "point": p,
                    "direction": d,
                    "up_direction": u,
                    "connector_index": 1,
                    "support_reference": (
                        (f"{spec.get('source_component')}/{spec.get('source_body')}/"
                         f"HybridShapes[{spec.get('source_hybrid_index')}]/{spec.get('source_point')}")
                        if spec.get("source_hybrid_index") is not None else
                        f"{spec.get('source_component')}/{spec.get('source_sketch')}/{spec.get('source_point')}"
                        if spec.get("source_component") else "carrier-local-point"
                    ),
                    "face_type": int(connector.FaceType),
                    "align_type": int(connector.AlignType),
                    "clock_type": int(connector.ClockType),
                })
            root.Update()
            if int(root.Products.Count) != baseline_count + len(created):
                raise RuntimeError("Assembly insertion count verification failed")
            return json.dumps({"status": "ok", "created": created}, indent=2, ensure_ascii=False)
        except Exception:
            # Roll back only the exact documents/components created by this call.
            for product in reversed(created_products):
                try:
                    product.Parent.Close()
                except Exception:
                    pass
            raise

    def _interface_on_component(self, component: Any, interface_name: str) -> Any | None:
        workbench = self._psp_workbench()
        candidates = [component]
        try:
            candidates.append(component.ReferenceProduct)
        except Exception:
            pass
        for candidate in candidates:
            try:
                interface = workbench.GetInterface(interface_name, candidate)
                if interface is not None:
                    return interface
            except Exception:
                continue
        return None

    def _probe_template(self, template_file: str) -> str:
        self._initialize_objects()
        template = os.path.abspath(template_file)
        if not os.path.isfile(template) or not template.lower().endswith((".catpart", ".catproduct")):
            raise ValueError("template_file must be an existing CATPart or CATProduct")
        assembly_document = self.conn.active_document
        template_document = None
        try:
            template_document = self.conn.app.Documents.Open(template)
            reference_product = template_document.Product
            assembly_document.Activate()
            interfaces = {
                key: self._interface_on_component(reference_product, interface_name) is not None
                for key, interface_name in PSP_INTERFACE_NAMES.items()
            }
            return json.dumps({
                "template_file": template,
                "document_type": os.path.splitext(template)[1].lstrip(".").upper(),
                "product_name": str(reference_product.Name),
                "part_number": str(reference_product.PartNumber),
                "interfaces": interfaces,
                "eligible_for_bendable_realization": bool(
                    interfaces["light_part"] and interfaces["light_bend"]
                ),
            }, indent=2, ensure_ascii=False)
        finally:
            if template_document is not None:
                try:
                    template_document.Close()
                except Exception:
                    pass
            try:
                assembly_document.Activate()
            except Exception:
                pass

    def _route_definition(self, route_name: str) -> tuple[list[float], list[float]]:
        route, _ = self._resolve_arrangement_run(route_name)
        nodes = route.ArrangementNodes
        flat_points: list[float] = []
        bend_radii: list[float] = []
        root = self._root_product()
        for index in range(1, nodes.Count + 1):
            node = nodes.Item(index)
            coords = array("d", [0.0, 0.0, 0.0])
            returned = node.GetPoint(root, coords)
            values = returned if isinstance(returned, (tuple, list, array)) else coords
            flat_points.extend(float(value) for value in values)
            if 1 < index < nodes.Count:
                bend_radii.append(float(node.BendRadius))
        if not any(abs(value) > 1e-9 for value in flat_points):
            raise RuntimeError(f"Route '{route_name}' returned an invalid all-zero definition")
        return flat_points, bend_radii

    def _realize_bendable_tube(self, args: dict[str, Any]) -> str:
        root, workbench, application = self._initialize_objects()
        logical_line, logical_line_id = self._resolve_logical_line(
            root, workbench, application, args.get("logical_line_id")
        )
        template = os.path.abspath(args["template_file"])
        output = os.path.abspath(args["output_file"])
        if not os.path.isfile(template) or not template.lower().endswith(".catpart"):
            raise ValueError("template_file must be an existing CATPart")
        if not output.lower().endswith(".catpart"):
            raise ValueError("output_file must end with .CATPart")
        if os.path.exists(output):
            raise ValueError(f"output_file already exists: {output}")
        os.makedirs(os.path.dirname(output), exist_ok=True)
        try:
            flat_points, bend_radii = self._route_definition(args["route_name"])
        except RuntimeError as exc:
            supplied = args.get("points")
            if "all-zero definition" not in str(exc) or not supplied:
                raise
            route, _ = self._resolve_arrangement_run(args["route_name"])
            if len(supplied) != route.ArrangementNodes.Count:
                raise ValueError("points count must match the Arrangement Run node count")
            verified = [self._validate_vector(point, "points[]") for point in supplied]
            flat_points = [value for point in verified for value in point]
            bend_radii = [
                float(route.ArrangementNodes.Item(index).BendRadius)
                for index in range(2, route.ArrangementNodes.Count)
            ]
        assembly_document = self.conn.active_document
        products = root.Products
        before = products.Count
        copied = False
        reference_document = None
        try:
            shutil.copy2(template, output)
            copied = True
            reference_document = self.conn.app.Documents.Open(output)
            reference_product = reference_document.Product
            point_features = []
            if args.get("point_source", "arrangement_nodes") == "template_geometry":
                reference_part = reference_document.Part
                route_support = reference_part.HybridBodies.Add()
                route_support.Name = "MCP_ROUTE_POINTS"
                shape_factory = reference_part.HybridShapeFactory
                for offset in range(0, len(flat_points), 3):
                    point_feature = shape_factory.AddNewPointCoord(
                        flat_points[offset], flat_points[offset + 1], flat_points[offset + 2]
                    )
                    point_feature.Name = f"ROUTE_POINT_{offset // 3 + 1:02d}"
                    route_support.AppendHybridShape(point_feature)
                    point_features.append(point_feature)
                reference_part.Update()
            assembly_document.Activate()

            root, workbench, application = self._initialize_objects()
            logical_line, logical_line_id = self._resolve_logical_line(
                root, workbench, application, args.get("logical_line_id")
            )
            try:
                place_part = workbench.GetInterface(
                    PSP_INTERFACE_NAMES["place_part"], application
                )
                list_factory = workbench.GetInterface(
                    "CATIAPspTempListFactory", application
                )
            except Exception as exc:
                raise RuntimeError(
                    "CATTubing does not expose the placement/list factories"
                ) from exc
            if place_part is None or list_factory is None:
                raise RuntimeError("CATTubing placement/list factories are unavailable")

            up_values = list_factory.CreateListOfDoubles()
            for value in self._validate_vector(
                args.get("up_direction", [0, 0, 1]), "up_direction", nonzero=True
            ):
                up_values.Append(value)

            route, _ = self._resolve_arrangement_run(args["route_name"])
            point_objects = list_factory.CreateListOfObjects()
            if args.get("point_source", "arrangement_nodes") == "arrangement_nodes":
                nodes = route.ArrangementNodes
                for index in range(1, nodes.Count + 1):
                    point_objects.Append(nodes.Item(index))
            else:
                for point_feature in point_features:
                    point_objects.Append(point_feature)

            radius_values = list_factory.CreateListOfDoubles()
            for radius in bend_radii:
                radius_values.Append(radius)

            try:
                component = place_part.RouteStringPartInSpace(
                    args.get("standard", "SSTLMM"),
                    args.get("function_type", "TubingTubeFunc"),
                    reference_product,
                    root,
                    logical_line,
                    args["physical_name"],
                    up_values,
                    point_objects,
                    radius_values,
                )
            except Exception as exc:
                detail = ""
                try:
                    detail = str(place_part.ErrorMessage)
                except Exception:
                    pass
                raise RuntimeError(
                    "RouteStringPartInSpace failed"
                    + (f": {detail}" if detail else "")
                ) from exc
            if products.Count != before + 1:
                detail = ""
                try:
                    detail = str(place_part.ErrorMessage)
                except Exception:
                    pass
                returned = "None" if component is None else repr(component)
                raise RuntimeError(
                    "Physical tubing component count did not increase; "
                    f"factory_return={returned}"
                    + (f"; CATIA={detail}" if detail else "")
                )
            if component is None:
                component = products.Item(products.Count)
            component.Name = args["physical_name"]
            try:
                component.PartNumber = args["physical_name"]
            except Exception:
                pass
            light_part = self._interface_on_component(component, PSP_INTERFACE_NAMES["light_part"])
            light_bend = self._interface_on_component(component, PSP_INTERFACE_NAMES["light_bend"])
            if light_part is None or light_bend is None:
                raise RuntimeError(
                    "Template instance does not expose CATIAPspLightPart and CATIAPspLightBend"
                )
            root.Update()
            result = json.loads(self._inspect_physical_tube(component.Name))
            result.update({
                "source_route": args["route_name"],
                "output_file": output,
                "point_count": len(flat_points) // 3,
                "bend_radii": bend_radii,
                "logical_line_id": logical_line_id,
            })
            return json.dumps(result, indent=2, ensure_ascii=False, default=str)
        except Exception:
            while products.Count > before:
                products.Remove(products.Count)
            try:
                self._root_product().Update()
            except Exception:
                pass
            if copied and os.path.exists(output):
                try:
                    os.remove(output)
                except OSError:
                    pass
            raise
        finally:
            if reference_document is not None:
                try:
                    reference_document.Close()
                except Exception:
                    pass
            try:
                assembly_document.Activate()
            except Exception:
                pass

    def _inspect_physical_tube(self, component_name: str) -> str:
        self._initialize_objects()
        component, _ = self._exact_component(component_name)
        interfaces: dict[str, bool] = {}
        for key, interface_name in PSP_INTERFACE_NAMES.items():
            interfaces[key] = self._interface_on_component(component, interface_name) is not None
        result: dict[str, Any] = {
            "component": component.Name,
            "part_number": getattr(component, "PartNumber", ""),
            "interfaces": interfaces,
        }
        light_part = self._interface_on_component(component, PSP_INTERFACE_NAMES["light_part"])
        if light_part is not None:
            try:
                definition = light_part.GetDefinition(self._root_product())
                result["definition"] = self._list_values(definition)
            except Exception as exc:
                result["definition_error"] = str(exc)
        light_bend = self._interface_on_component(component, PSP_INTERFACE_NAMES["light_bend"])
        if light_bend is not None:
            try:
                result["bend_data"] = self._list_values(light_bend.GetBendData())
            except Exception as exc:
                result["bend_error"] = str(exc)
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
