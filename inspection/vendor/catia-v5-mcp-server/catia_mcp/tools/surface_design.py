"""Generative Shape Design (GSD) tools for CATIA V5."""

from __future__ import annotations

import json
from typing import Any

from catia_mcp.connection import CATIAConnection


def _safe_name(value: Any) -> str | None:
    try:
        return value.Name
    except Exception:
        return None


class SurfaceDesignTools:
    """Create and inspect wireframe/surface geometry in geometrical sets."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection
        self._last_set: Any | None = None
        self._last_shape: Any | None = None

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        name = {"type": "string", "description": "CATIA element name"}
        set_name = {"type": "string", "description": "Target geometrical set name"}
        return [
            {
                "name": "catia_gsd_create_set",
                "description": "Create a geometrical set (HybridBody) and make it the GSD target.",
                "inputSchema": {"type": "object", "properties": {"name": name}, "required": ["name"]},
            },
            {
                "name": "catia_gsd_set_active_set",
                "description": "Choose an existing geometrical set as the target for new wireframe/surface elements.",
                "inputSchema": {"type": "object", "properties": {"name": name}, "required": ["name"]},
            },
            {
                "name": "catia_gsd_list",
                "description": "List geometrical sets and their hybrid shapes.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "catia_gsd_point",
                "description": "Create a 3D coordinate point.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["x", "y", "z"],
                },
            },
            {
                "name": "catia_gsd_line",
                "description": "Create a 3D line segment between two named points.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"point1": name, "point2": name, "name": name, "set_name": set_name},
                    "required": ["point1", "point2"],
                },
            },
            {
                "name": "catia_gsd_offset_plane",
                "description": "Create a plane offset from XY, YZ, ZX, or a named plane.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "reference": {"type": "string", "description": "xy, yz, zx, or element name"},
                        "offset": {"type": "number"}, "reverse": {"type": "boolean", "default": False},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["reference", "offset"],
                },
            },
            {
                "name": "catia_gsd_circle",
                "description": "Create a full 3D circle from a center point, support plane, and radius.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "center": name, "support": name, "radius": {"type": "number"},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["center", "support", "radius"],
                },
            },
            {
                "name": "catia_gsd_spline",
                "description": "Create a 3D spline through named points.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "points": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        "closed": {"type": "boolean", "default": False}, "name": name, "set_name": set_name,
                    },
                    "required": ["points"],
                },
            },
            {
                "name": "catia_gsd_extrude",
                "description": "Extrude a named curve along an XYZ direction to create a surface.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "profile": name, "length1": {"type": "number"},
                        "length2": {"type": "number", "default": 0},
                        "x": {"type": "number", "default": 0},
                        "y": {"type": "number", "default": 0},
                        "z": {"type": "number", "default": 1},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["profile", "length1"],
                },
            },
            {
                "name": "catia_gsd_revolve",
                "description": "Revolve a named profile about a named line to create a surface.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "profile": name, "axis": name,
                        "angle1": {"type": "number", "default": 360},
                        "angle2": {"type": "number", "default": 0},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["profile", "axis"],
                },
            },
            {
                "name": "catia_gsd_sweep",
                "description": "Sweep a named profile along a named guide curve.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"profile": name, "guide": name, "name": name, "set_name": set_name},
                    "required": ["profile", "guide"],
                },
            },
            {
                "name": "catia_gsd_loft",
                "description": "Create a multi-section loft surface with optional guide curves.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sections": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        "guides": {"type": "array", "items": {"type": "string"}, "default": []},
                        "closing_points": {
                            "type": "array", "items": {"type": "string"},
                            "description": "Optional one point on each closed section to align coupling",
                        },
                        "orientation": {"type": "integer", "enum": [-1, 1], "default": 1},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["sections"],
                },
            },
            {
                "name": "catia_gsd_offset_surface",
                "description": "Create an offset from a named surface.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "surface": name, "distance": {"type": "number"},
                        "reverse": {"type": "boolean", "default": False},
                        "tolerance": {"type": "number", "default": 0.001},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["surface", "distance"],
                },
            },
            {
                "name": "catia_gsd_join",
                "description": "Join two or more named curves or surfaces.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "elements": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        "tolerance": {"type": "number", "default": 0.001},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["elements"],
                },
            },
            {
                "name": "catia_gsd_fill",
                "description": "Create a fill surface bounded by named closed curves or edges.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "boundaries": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["boundaries"],
                },
            },
            {
                "name": "catia_gsd_split",
                "description": "Split a named surface with another surface or plane.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "surface": name, "cutter": name,
                        "orientation": {"type": "integer", "enum": [-1, 1], "default": 1},
                        "name": name, "set_name": set_name,
                    },
                    "required": ["surface", "cutter"],
                },
            },
            {
                "name": "catia_gsd_thicken",
                "description": "Thicken a named surface into a Part Design solid in the active body.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "surface": name, "top": {"type": "number"},
                        "bottom": {"type": "number", "default": 0},
                        "reverse": {"type": "boolean", "default": False},
                    },
                    "required": ["surface", "top"],
                },
            },
            {
                "name": "catia_gsd_close_surface",
                "description": "Convert a closed surface skin into a Part Design solid in the active body.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"surface": name, "name": name},
                    "required": ["surface"],
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        routes = {
            "catia_gsd_create_set": lambda: self._create_set(arguments["name"]),
            "catia_gsd_set_active_set": lambda: self._set_active(arguments["name"]),
            "catia_gsd_list": self._list,
            "catia_gsd_point": lambda: self._point(arguments),
            "catia_gsd_line": lambda: self._line(arguments),
            "catia_gsd_offset_plane": lambda: self._offset_plane(arguments),
            "catia_gsd_circle": lambda: self._circle(arguments),
            "catia_gsd_spline": lambda: self._spline(arguments),
            "catia_gsd_extrude": lambda: self._extrude(arguments),
            "catia_gsd_revolve": lambda: self._revolve(arguments),
            "catia_gsd_sweep": lambda: self._sweep(arguments),
            "catia_gsd_loft": lambda: self._loft(arguments),
            "catia_gsd_offset_surface": lambda: self._offset(arguments),
            "catia_gsd_join": lambda: self._join(arguments),
            "catia_gsd_fill": lambda: self._fill(arguments),
            "catia_gsd_split": lambda: self._split(arguments),
            "catia_gsd_thicken": lambda: self._thicken(arguments),
            "catia_gsd_close_surface": lambda: self._close_surface(arguments),
        }
        if tool_name not in routes:
            raise ValueError(f"Unknown surface design tool: {tool_name}")
        self.conn.ensure_connected()
        return routes[tool_name]()

    @property
    def part(self) -> Any:
        return self.conn.get_active_part()

    @property
    def factory(self) -> Any:
        return self.part.HybridShapeFactory

    def _iter_sets(self, collection: Any | None = None):
        collection = collection or self.part.HybridBodies
        for i in range(1, collection.Count + 1):
            body = collection.Item(i)
            yield body
            yield from self._iter_sets(body.HybridBodies)

    def _find_set(self, name: str) -> Any:
        for body in self._iter_sets():
            if body.Name == name:
                return body
        raise RuntimeError(f"Geometrical set not found: {name}")

    def _target_set(self, requested: str | None = None) -> Any:
        if requested:
            body = self._find_set(requested)
        elif self._last_set is not None:
            try:
                _ = self._last_set.Name
                body = self._last_set
            except Exception:
                self._last_set = None
                body = self._target_set()
        elif self.part.HybridBodies.Count:
            body = self.part.HybridBodies.Item(self.part.HybridBodies.Count)
        else:
            body = self.part.HybridBodies.Add()
            body.Name = "MCP_Geometry"
        self._last_set = body
        return body

    def _find(self, name: str) -> Any:
        key = name.lower()
        origin = self.part.OriginElements
        planes = {
            "xy": origin.PlaneXY, "xy plane": origin.PlaneXY,
            "yz": origin.PlaneYZ, "yz plane": origin.PlaneYZ,
            "zx": origin.PlaneZX, "zx plane": origin.PlaneZX,
        }
        if key in planes:
            return planes[key]
        for body in self._iter_sets():
            if body.Name == name:
                return body
            shapes = body.HybridShapes
            for i in range(1, shapes.Count + 1):
                shape = shapes.Item(i)
                if _safe_name(shape) == name:
                    return shape
        selection = self.conn.active_document.Selection
        selection.Clear()
        selection.Search(f"Name={name},all")
        try:
            if selection.Count:
                return selection.Item(1).Value
        finally:
            selection.Clear()
        raise RuntimeError(f"Element not found: {name}")

    def _ref(self, name: str) -> Any:
        return self.part.CreateReferenceFromObject(self._find(name))

    def _append(self, shape: Any, args: dict[str, Any]) -> str:
        body = self._target_set(args.get("set_name"))
        body.AppendHybridShape(shape)
        if args.get("name"):
            shape.Name = args["name"]
        self.part.InWorkObject = shape
        self.part.UpdateObject(shape)
        self._last_shape = shape
        return json.dumps({
            "name": shape.Name, "type": type(shape).__name__, "set": body.Name,
        }, ensure_ascii=False)

    def _create_set(self, name: str) -> str:
        if any(body.Name == name for body in self._iter_sets()):
            raise RuntimeError(f"Geometrical set already exists: {name}")
        body = self.part.HybridBodies.Add()
        body.Name = name
        self._last_set = body
        self.part.InWorkObject = body
        return json.dumps({"created": name}, ensure_ascii=False)

    def _set_active(self, name: str) -> str:
        body = self._find_set(name)
        self._last_set = body
        self.part.InWorkObject = body
        return json.dumps({"active_set": name}, ensure_ascii=False)

    def _list(self) -> str:
        result = []
        for body in self._iter_sets():
            result.append({
                "name": body.Name,
                "shapes": [
                    {"name": body.HybridShapes.Item(i).Name,
                     "type": type(body.HybridShapes.Item(i)).__name__}
                    for i in range(1, body.HybridShapes.Count + 1)
                ],
            })
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _point(self, args: dict[str, Any]) -> str:
        return self._append(self.factory.AddNewPointCoord(args["x"], args["y"], args["z"]), args)

    def _line(self, args: dict[str, Any]) -> str:
        return self._append(self.factory.AddNewLinePtPt(self._ref(args["point1"]), self._ref(args["point2"])), args)

    def _offset_plane(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewPlaneOffset(
            self._ref(args["reference"]), args["offset"], bool(args.get("reverse", False))
        )
        return self._append(shape, args)

    def _circle(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewCircleCtrRad(
            self._ref(args["center"]), self._ref(args["support"]), False, args["radius"]
        )
        try:
            shape.SetLimitation(1)
        except Exception:
            pass
        return self._append(shape, args)

    def _spline(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewSpline()
        for point in args["points"]:
            shape.AddPoint(self._ref(point))
        if args.get("closed"):
            shape.SetClosing(1)
        return self._append(shape, args)

    def _extrude(self, args: dict[str, Any]) -> str:
        x, y, z = args.get("x", 0), args.get("y", 0), args.get("z", 1)
        if x == 0 and y == 0 and z == 0:
            raise ValueError("Extrusion direction cannot be the zero vector")
        direction = self.factory.AddNewDirectionByCoord(x, y, z)
        shape = self.factory.AddNewExtrude(
            self._ref(args["profile"]), args["length1"], args.get("length2", 0), direction
        )
        return self._append(shape, args)

    def _revolve(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewRevol(
            self._ref(args["profile"]), args.get("angle1", 360),
            args.get("angle2", 0), self._ref(args["axis"])
        )
        return self._append(shape, args)

    def _sweep(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewSweepExplicit(
            self._ref(args["profile"]), self._ref(args["guide"])
        )
        return self._append(shape, args)

    def _loft(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewLoft()
        body = self._target_set(args.get("set_name"))
        body.AppendHybridShape(shape)
        if args.get("name"):
            shape.Name = args["name"]
        orientation = args.get("orientation", 1)
        empty_ref = self.part.CreateReferenceFromName("")
        closing_points = args.get("closing_points")
        if closing_points and len(closing_points) != len(args["sections"]):
            raise ValueError("closing_points must have the same length as sections")
        for index, section in enumerate(args["sections"]):
            point_ref = self._ref(closing_points[index]) if closing_points else empty_ref
            shape.AddSectionToLoft(self._ref(section), orientation, point_ref)
        for guide in args.get("guides", []):
            shape.AddGuide(self._ref(guide))
        self.part.InWorkObject = shape
        self.part.UpdateObject(shape)
        self._last_shape = shape
        return json.dumps({"name": shape.Name, "type": type(shape).__name__, "set": body.Name}, ensure_ascii=False)

    def _offset(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewOffset(
            self._ref(args["surface"]), args["distance"],
            bool(args.get("reverse", False)), args.get("tolerance", 0.001)
        )
        return self._append(shape, args)

    def _join(self, args: dict[str, Any]) -> str:
        elements = args["elements"]
        shape = self.factory.AddNewJoin(self._ref(elements[0]), self._ref(elements[1]))
        for element in elements[2:]:
            shape.AddElement(self._ref(element))
        try:
            shape.Connex = False
            shape.Tolerance = args.get("tolerance", 0.001)
        except Exception:
            pass
        return self._append(shape, args)

    def _fill(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewFill()
        for boundary in args["boundaries"]:
            shape.AddBound(self._ref(boundary))
        return self._append(shape, args)

    def _split(self, args: dict[str, Any]) -> str:
        shape = self.factory.AddNewHybridSplit(
            self._ref(args["surface"]), self._ref(args["cutter"]), args.get("orientation", 1)
        )
        return self._append(shape, args)

    def _thicken(self, args: dict[str, Any]) -> str:
        body = self.conn.get_active_part_body()
        self.part.InWorkObject = body
        feature = self.part.ShapeFactory.AddNewThickSurface(
            self._ref(args["surface"]), bool(args.get("reverse", False)),
            args["top"], args.get("bottom", 0)
        )
        self.part.UpdateObject(feature)
        self.conn.last_feature = feature
        return json.dumps({"name": feature.Name, "body": body.Name}, ensure_ascii=False)

    def _close_surface(self, args: dict[str, Any]) -> str:
        body = self.conn.get_active_part_body()
        self.part.InWorkObject = body
        feature = self.part.ShapeFactory.AddNewCloseSurface(self._ref(args["surface"]))
        if args.get("name"):
            feature.Name = args["name"]
        self.part.UpdateObject(feature)
        self.conn.last_feature = feature
        return json.dumps({"name": feature.Name, "body": body.Name}, ensure_ascii=False)
