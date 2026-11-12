"""Assembly tools for CATIA V5.

Product/Assembly management: add components, constraints (Fix, Coincidence,
Contact, Offset, Angle), move components, and manage the product tree.
"""

from __future__ import annotations

import json
from typing import Any

from catia_mcp.connection import CATIAConnection


class AssemblyTools:
    """Tools for assembly (Product) operations in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_split_bodies_to_product",
                "description": (
                    "Copy exact named solid Bodies from the active CATPart into separate "
                    "CATPart files as result-without-link solids, then create a CATProduct "
                    "containing those parts at their existing global coordinates."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "body_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Exact source Body names to convert",
                        },
                        "output_directory": {"type": "string"},
                        "product_name": {"type": "string"},
                    },
                    "required": ["body_names", "output_directory", "product_name"],
                },
            },
            {
                "name": "catia_add_component",
                "description": (
                    "Add an existing CATPart or CATProduct file as a component in the active assembly. "
                    "The component is inserted at the origin."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Full path to the .CATPart or .CATProduct file to add",
                        },
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "catia_add_new_part",
                "description": (
                    "Create a new empty Part directly inside the active assembly. "
                    "Returns the name of the created component."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for the new part component",
                        },
                    },
                },
            },
            {
                "name": "catia_fix_constraint",
                "description": (
                    "Fix a component in place (remove all degrees of freedom). "
                    "Typically applied to the base/reference component."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component_name": {
                            "type": "string",
                            "description": "Name of the component to fix",
                        },
                    },
                    "required": ["component_name"],
                },
            },
            {
                "name": "catia_coincidence_constraint",
                "description": (
                    "Create a Coincidence constraint between two components. "
                    "Aligns axes, planes, or points of two components."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component1": {
                            "type": "string",
                            "description": "Name of first component",
                        },
                        "component2": {
                            "type": "string",
                            "description": "Name of second component",
                        },
                        "element1": {
                            "type": "string",
                            "description": "Geometry element on component1 (e.g., 'xy plane', 'Face.1')",
                        },
                        "element2": {
                            "type": "string",
                            "description": "Geometry element on component2",
                        },
                    },
                    "required": ["component1", "component2"],
                },
            },
            {
                "name": "catia_offset_constraint",
                "description": (
                    "Create an Offset constraint between two faces/planes of two components. "
                    "Maintains a constant distance between the reference elements."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component1": {
                            "type": "string",
                            "description": "Name of first component",
                        },
                        "component2": {
                            "type": "string",
                            "description": "Name of second component",
                        },
                        "offset": {
                            "type": "number",
                            "description": "Offset distance in mm",
                        },
                        "element1": {"type": "string", "description": "Reference element on component1"},
                        "element2": {"type": "string", "description": "Reference element on component2"},
                    },
                    "required": ["component1", "component2", "offset"],
                },
            },
            {
                "name": "catia_angle_constraint",
                "description": "Create an Angle constraint between two components.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component1": {
                            "type": "string",
                            "description": "Name of first component",
                        },
                        "component2": {
                            "type": "string",
                            "description": "Name of second component",
                        },
                        "angle": {
                            "type": "number",
                            "description": "Angle in degrees",
                        },
                    },
                    "required": ["component1", "component2", "angle"],
                },
            },
            {
                "name": "catia_move_component",
                "description": (
                    "Move a component by translation and/or rotation. "
                    "Translation in mm, rotation in degrees."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component_name": {
                            "type": "string",
                            "description": "Name of the component to move",
                        },
                        "tx": {"type": "number", "description": "Translation X (mm)", "default": 0},
                        "ty": {"type": "number", "description": "Translation Y (mm)", "default": 0},
                        "tz": {"type": "number", "description": "Translation Z (mm)", "default": 0},
                        "rx": {"type": "number", "description": "Rotation around X (degrees)", "default": 0},
                        "ry": {"type": "number", "description": "Rotation around Y (degrees)", "default": 0},
                        "rz": {"type": "number", "description": "Rotation around Z (degrees)", "default": 0},
                    },
                    "required": ["component_name"],
                },
            },
            {
                "name": "catia_list_components",
                "description": "List all components in the active assembly/product with their names and positions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_list_constraints",
                "description": "List all assembly constraints in the active product.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        match tool_name:
            case "catia_split_bodies_to_product":
                return self._split_bodies_to_product(arguments)
            case "catia_add_component":
                return self._add_component(arguments["file_path"])
            case "catia_add_new_part":
                return self._add_new_part(arguments.get("name"))
            case "catia_fix_constraint":
                return self._fix_constraint(arguments["component_name"])
            case "catia_coincidence_constraint":
                return self._coincidence_constraint(arguments)
            case "catia_offset_constraint":
                return self._offset_constraint(arguments)
            case "catia_angle_constraint":
                return self._angle_constraint(arguments)
            case "catia_move_component":
                return self._move_component(arguments)
            case "catia_list_components":
                return self._list_components()
            case "catia_list_constraints":
                return self._list_constraints()
            case _:
                raise ValueError(f"Unknown assembly tool: {tool_name}")

    def _split_bodies_to_product(self, args: dict[str, Any]) -> str:
        """Create a result-solid CATPart per exact Body and assemble them at origin."""
        import os

        app = self.conn.app
        source_doc = app.ActiveDocument
        if not source_doc.Name.lower().endswith(".catpart"):
            raise ValueError("Active document must be a CATPart")
        source_part = source_doc.Part
        output_dir = os.path.abspath(args["output_directory"])
        os.makedirs(output_dir, exist_ok=True)

        requested = list(args["body_names"])
        if not requested:
            raise ValueError("body_names must not be empty")

        available = {source_part.Bodies.Item(i).Name: source_part.Bodies.Item(i)
                     for i in range(1, source_part.Bodies.Count + 1)}
        missing = [name for name in requested if name not in available]
        if missing:
            raise ValueError(f"Bodies not found: {missing}")

        created = []
        for body_name in requested:
            source_doc.Activate()
            source_sel = source_doc.Selection
            source_sel.Clear()
            source_sel.Add(available[body_name])
            source_sel.Copy()
            source_sel.Clear()

            part_doc = app.Documents.Add("Part")
            part = part_doc.Part
            part_doc.Product.PartNumber = body_name
            dest_body = part.MainBody
            dest_body.Name = body_name
            dest_sel = part_doc.Selection
            dest_sel.Clear()
            dest_sel.Add(dest_body)
            try:
                dest_sel.PasteSpecial("CATPrtResultWithOutLink")
            except Exception:
                dest_sel.PasteSpecial("CATPrtResult")
            dest_sel.Clear()
            part.Update()
            file_path = os.path.join(output_dir, f"{body_name}.CATPart")
            part_doc.SaveAs(file_path)
            created.append(file_path)
            part_doc.Close()

        product_doc = app.Documents.Add("Product")
        product = product_doc.Product
        product.PartNumber = args["product_name"]
        for file_path in created:
            product.Products.AddComponentsFromFiles([file_path], "All")
        product.Update()
        product_path = os.path.join(output_dir, f"{args['product_name']}.CATProduct")
        product_doc.SaveAs(product_path)
        self.conn.refresh_display()
        return json.dumps({
            "source": source_doc.FullName,
            "product": product_path,
            "component_count": len(created),
            "components": created,
        }, indent=2, ensure_ascii=False)

    def _add_component(self, file_path: str) -> str:
        product = self.conn.get_active_product()
        products = product.Products
        component = products.AddComponentsFromFiles(
            [file_path], "All"
        )
        self.conn.refresh_display()
        return f"Component added from: {file_path}"

    def _add_new_part(self, name: str | None = None) -> str:
        product = self.conn.get_active_product()
        products = product.Products
        new_product = products.AddNewProduct("Part")
        if name:
            new_product.Name = name
        self.conn.refresh_display()
        return f"New Part component created in assembly: '{new_product.Name}'"

    def _fix_constraint(self, component_name: str) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")
        component = product.Products.Item(component_name)
        ref = product.CreateReferenceFromName(f"{product.Name}/{component.Name}/!")
        cst = constraints.AddMonoEltCst(0, ref)  # catCstTypeReference
        cst.Name = f"Fix.{component_name}"

        self.conn.refresh_display()
        return f"Fix constraint applied to '{component_name}'"

    def _coincidence_constraint(self, args: dict[str, Any]) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")

        comp1 = product.Products.Item(args["component1"])
        comp2 = product.Products.Item(args["component2"])
        element1 = args.get("element1") or "xy 平面"
        element2 = args.get("element2") or "xy 平面"
        ref1 = product.CreateReferenceFromName(f"{product.Name}/{comp1.Name}/!{element1}")
        ref2 = product.CreateReferenceFromName(f"{product.Name}/{comp2.Name}/!{element2}")
        cst = constraints.AddBiEltCst(2, ref1, ref2)  # catCstTypeOn
        self.conn.refresh_display()
        return (
            f"Coincidence constraint created between "
            f"'{args['component1']}' and '{args['component2']}'"
        )

    def _offset_constraint(self, args: dict[str, Any]) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")

        comp1 = product.Products.Item(args["component1"])
        comp2 = product.Products.Item(args["component2"])
        element1 = args.get("element1") or "yz 平面"
        element2 = args.get("element2") or "yz 平面"
        ref1 = product.CreateReferenceFromName(f"{product.Name}/{comp1.Name}/!{element1}")
        ref2 = product.CreateReferenceFromName(f"{product.Name}/{comp2.Name}/!{element2}")
        cst = constraints.AddBiEltCst(1, ref1, ref2)  # catCstTypeDistance
        cst.Dimension.Value = args["offset"]

        self.conn.refresh_display()
        return (
            f"Offset constraint: {args['offset']} mm between "
            f"'{args['component1']}' and '{args['component2']}'"
        )

    def _angle_constraint(self, args: dict[str, Any]) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")

        comp1 = product.Products.Item(args["component1"])
        comp2 = product.Products.Item(args["component2"])

        cst = constraints.AddBiEltCst(2, comp1, comp2)  # Angle
        cst.Dimension.Value = args["angle"]

        self.conn.refresh_display()
        return (
            f"Angle constraint: {args['angle']}° between "
            f"'{args['component1']}' and '{args['component2']}'"
        )

    def _move_component(self, args: dict[str, Any]) -> str:
        import math
        product = self.conn.get_active_product()
        component = product.Products.Item(args["component_name"])

        # Product.Position is effectively read-only for component instances in
        # several CATIA V5 releases. Product.Move.Apply is the supported API for
        # applying a 3x4 incremental transformation matrix.
        matrix = [1.0, 0.0, 0.0,
                  0.0, 1.0, 0.0,
                  0.0, 0.0, 1.0,
                  float(args.get("tx", 0)),
                  float(args.get("ty", 0)),
                  float(args.get("tz", 0))]

        # Apply rotations if specified (simplified: sequential Euler rotations)
        rx = math.radians(args.get("rx", 0))
        ry = math.radians(args.get("ry", 0))
        rz = math.radians(args.get("rz", 0))

        if rx != 0 or ry != 0 or rz != 0:
            # Build rotation matrix (Rz * Ry * Rx convention)
            cx, sx = math.cos(rx), math.sin(rx)
            cy, sy = math.cos(ry), math.sin(ry)
            cz, sz = math.cos(rz), math.sin(rz)

            # Rotation matrix components
            r00 = cy * cz
            r01 = cz * sx * sy - cx * sz
            r02 = sx * sz + cx * cz * sy
            r10 = cy * sz
            r11 = cx * cz + sx * sy * sz
            r12 = cx * sy * sz - cz * sx
            r20 = -sy
            r21 = cy * sx
            r22 = cx * cy

            # Apply to current rotation (first 9 elements)
            matrix[:9] = [r00, r10, r20, r01, r11, r21, r02, r12, r22]

        component.Move.Apply(tuple(matrix))
        product.Update()
        self.conn.refresh_display()

        return (
            f"Component '{args['component_name']}' moved: "
            f"T=({args.get('tx', 0)}, {args.get('ty', 0)}, {args.get('tz', 0)}) mm, "
            f"R=({args.get('rx', 0)}, {args.get('ry', 0)}, {args.get('rz', 0)})°"
        )

    def _list_components(self) -> str:
        from array import array
        product = self.conn.get_active_product()
        products = product.Products

        components = []
        for i in range(1, products.Count + 1):
            comp = products.Item(i)
            pos = comp.Position
            matrix = [0.0] * 12
            try:
                values = array("d", matrix)
                pos.GetComponents(values)
                matrix = list(values)
            except Exception:
                pass
            components.append({
                "index": i,
                "name": comp.Name,
                "part_number": comp.PartNumber,
                "position": {
                    "x": round(matrix[9], 3),
                    "y": round(matrix[10], 3),
                    "z": round(matrix[11], 3),
                },
            })

        if not components:
            return "No components in the active assembly"
        return json.dumps(components, indent=2, ensure_ascii=False)

    def _list_constraints(self) -> str:
        product = self.conn.get_active_product()
        constraints = product.Connections("CATIAConstraints")

        cst_list = []
        for i in range(1, constraints.Count + 1):
            cst = constraints.Item(i)
            info = {
                "index": i,
                "name": cst.Name,
                "type": cst.Type if hasattr(cst, "Type") else "unknown",
            }
            try:
                info["status"] = "resolved" if cst.Status == 0 else "broken"
            except Exception:
                pass
            cst_list.append(info)

        if not cst_list:
            return "No constraints in the active assembly"
        return json.dumps(cst_list, indent=2, ensure_ascii=False)
