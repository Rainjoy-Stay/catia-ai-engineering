"""Export tools for CATIA V5.

Export to STEP, IGES, STL, 3DXML, and other formats.
Also includes screenshot capture.
"""

from __future__ import annotations

import json
import os
from typing import Any

from catia_mcp.connection import CATIAConnection

# CATIA export format identifiers
FORMAT_MAP = {
    "step": "stp",
    "stp": "stp",
    "iges": "igs",
    "igs": "igs",
    "stl": "stl",
    "3dxml": "3dxml",
    "wrl": "wrl",
    "vrml": "wrl",
    "pdf": "pdf",
    "cgr": "cgr",
}


class ExportTools:
    """Tools for exporting CATIA V5 data to external formats."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {'name':'catia_export_surface_batches','description':'Export exact indexed geometrical-set elements into owned temporary parts; preserve source and audit incomplete batches.',
             'inputSchema':{'type':'object','properties':{'source_name':{'type':'string'},'output_directory':{'type':'string'},'start_batch':{'type':'integer'},'verify_body_audit':{'type':'string'}},'required':['source_name','output_directory']}},
            {
                'name':'catia_capture_body_spatial_facts',
                'description':'Read exact Body centroid facts using explicitly typed COM output arrays. Non-mutating; unavailable output stays unverified.',
                'inputSchema':{'type':'object','properties':{'source_name':{'type':'string'},
                    'body_indices':{'type':'array','items':{'type':'integer'}},'output_path':{'type':'string'}},
                    'required':['source_name','body_indices','output_path']}
            },
            {
                'name':'catia_benchmark_batch_copy',
                'description':'Compare individual and single-batch result-without-link copying of an exact Body subset. Uses disposable owned CATParts, validates names and volume/area, exports separate STEP files. Never saves or modifies source.',
                'inputSchema':{'type':'object','properties':{
                    'source_name':{'type':'string'},
                    'body_indices':{'type':'array','items':{'type':'integer'}},
                    'output_directory':{'type':'string'},'copy_modes':{'type':'array','items':{'type':'string','enum':['individual','bulk']}}},
                    'required':['source_name','body_indices','output_directory']}
            },
            {
                'name': 'catia_export_scope_derivative',
                'description': 'Copy exact retained Bodies and top-level geometrical sets into an independent unsaved inspection derivative, then export STEP. Never delete, update or save the source. Exclusions are scope choices, not proof of failed geometry.',
                'inputSchema': {'type':'object','properties': {
                    'source_name': {'type':'string'},
                    'excluded_set_names': {'type':'array','items':{'type':'string'}},
                    'file_path': {'type':'string'},
                    'audit_path': {'type':'string'}},
                    'required':['source_name','excluded_set_names','file_path','audit_path']}
            },
            {
                "name": "catia_export",
                "description": (
                    "Export the active document to a file. "
                    "Supported formats: STEP (.stp), IGES (.igs), STL (.stl), "
                    "3DXML (.3dxml), VRML (.wrl), PDF (2D drawings)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": (
                                "Output file path. The format is determined by the extension. "
                                "Example: 'C:/export/my_part.stp'"
                            ),
                        },
                        "format": {
                            "type": "string",
                            "description": (
                                "Export format (optional if file extension is provided). "
                                "One of: step, iges, stl, 3dxml, vrml"
                            ),
                            "enum": ["step", "iges", "stl", "3dxml", "vrml"],
                        },
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "catia_screenshot",
                "description": (
                    "Capture a screenshot of the current 3D view and save as image file. "
                    "Supports JPG, BMP, and TIFF. CATIA V5 does not natively capture PNG."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Output image path (e.g., 'C:/screenshots/part.jpg')",
                        },
                        "width": {
                            "type": "integer",
                            "description": "Image width in pixels (default: 1920)",
                            "default": 1920,
                        },
                        "height": {
                            "type": "integer",
                            "description": "Image height in pixels (default: 1080)",
                            "default": 1080,
                        },
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "catia_set_view",
                "description": (
                    "Set the 3D view orientation. "
                    "Standard views: front, back, top, bottom, left, right, isometric."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "view": {
                            "type": "string",
                            "description": "View orientation",
                            "enum": [
                                "front", "back", "top", "bottom",
                                "left", "right", "isometric",
                            ],
                        },
                    },
                    "required": ["view"],
                },
            },
            {
                "name": "catia_fit_all",
                "description": "Fit all geometry in the current 3D view (zoom to fit).",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        match tool_name:
            case 'catia_export_surface_batches':
                from catia_mcp.tools.batch_copy_benchmark import export_surface_batches
                return export_surface_batches(self.conn, **arguments)
            case 'catia_capture_body_spatial_facts':
                from catia_mcp.tools.batch_copy_benchmark import capture_spatial_facts
                return capture_spatial_facts(self.conn, **arguments)
            case 'catia_benchmark_batch_copy':
                from catia_mcp.tools.batch_copy_benchmark import benchmark_batch_copy
                return benchmark_batch_copy(self.conn, **arguments)
            case 'catia_export_scope_derivative':
                from catia_mcp.tools.scope_derivative import export_scope_derivative
                return export_scope_derivative(self.conn, **arguments)
            case "catia_export":
                return self._export(arguments["file_path"], arguments.get("format"))
            case "catia_screenshot":
                return self._screenshot(
                    arguments["file_path"],
                    arguments.get("width", 1920),
                    arguments.get("height", 1080),
                )
            case "catia_set_view":
                return self._set_view(arguments["view"])
            case "catia_fit_all":
                return self._fit_all()
            case _:
                raise ValueError(f"Unknown export tool: {tool_name}")

    def _export(self, file_path: str, fmt: str | None = None) -> str:
        self.conn.ensure_connected()
        doc = self.conn.active_document

        # Determine format from extension if not specified
        if fmt is None:
            ext = os.path.splitext(file_path)[1].lstrip(".").lower()
            fmt = ext

        fmt_key = fmt.lower()
        if fmt_key not in FORMAT_MAP:
            supported = ", ".join(sorted(set(FORMAT_MAP.keys())))
            raise ValueError(
                f"Unsupported export format: '{fmt}'. Supported: {supported}"
            )

        # Ensure output directory exists
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # CATIA V5 export via SaveAs with format specification
        doc.ExportData(file_path, FORMAT_MAP[fmt_key])

        size_info = ""
        if os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)
            if size_bytes > 1024 * 1024:
                size_info = f" ({size_bytes / (1024*1024):.1f} MB)"
            elif size_bytes > 1024:
                size_info = f" ({size_bytes / 1024:.1f} KB)"
            else:
                size_info = f" ({size_bytes} bytes)"

        return f"Exported to {file_path}{size_info} (format: {fmt_key.upper()})"

    def _screenshot(self, file_path: str, width: int = 1920, height: int = 1080) -> str:
        self.conn.ensure_connected()

        # Ensure output directory exists
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Capture via the active viewer
        viewer = self.conn.active_editor.ActiveViewer
        extension = os.path.splitext(file_path)[1].lower()
        capture_formats = {
            ".tif": 2,
            ".tiff": 2,
            ".bmp": 4,
            ".jpg": 5,
            ".jpeg": 5,
        }
        if extension not in capture_formats:
            raise ValueError("CATIA CaptureToFile supports TIFF, BMP, and JPEG; PNG is not supported")
        viewer.CaptureToFile(capture_formats[extension], file_path)

        return f"Screenshot saved to {file_path} ({width}x{height})"

    def _set_view(self, view: str) -> str:
        self.conn.ensure_connected()
        viewer = self.conn.active_editor.ActiveViewer
        viewpoint = viewer.Viewpoint3D

        # Standard view direction vectors and up vectors
        views = {
            "front":     {"sight": (0, 0, -1), "up": (0, 1, 0)},
            "back":      {"sight": (0, 0, 1),  "up": (0, 1, 0)},
            "top":       {"sight": (0, -1, 0), "up": (0, 0, -1)},
            "bottom":    {"sight": (0, 1, 0),  "up": (0, 0, 1)},
            "left":      {"sight": (1, 0, 0),  "up": (0, 1, 0)},
            "right":     {"sight": (-1, 0, 0), "up": (0, 1, 0)},
            "isometric": {"sight": (-1, -1, -1), "up": (0, 1, 0)},
        }

        if view not in views:
            raise ValueError(f"Unknown view: '{view}'")

        v = views[view]
        sight = v["sight"]
        up = v["up"]

        # Set viewpoint sight and up directions
        viewpoint.PutSightDirection(list(sight))
        viewpoint.PutUpDirection(list(up))

        # Fit all in view
        viewer.Reframe()

        return f"View set to: {view}"

    def _fit_all(self) -> str:
        self.conn.ensure_connected()
        viewer = self.conn.active_editor.ActiveViewer
        viewer.Reframe()
        return "View fitted to all geometry"
