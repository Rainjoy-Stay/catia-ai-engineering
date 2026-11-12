"""Document management tools for CATIA V5.

Create, open, save, close, and list documents (Part, Product, Drawing).
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from catia_mcp.connection import CATIAConnection


class DocumentTools:
    """Tools for managing CATIA V5 documents."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_send_to_directory",
                "description": (
                    "Package the active CATProduct and every referenced CATPart/CATProduct into "
                    "one directory using CATIA SaveAs, then verify that every assembly reference "
                    "resolves inside that directory. This creates an independent editable copy."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "output_directory": {
                            "type": "string",
                            "description": "Absolute destination directory",
                        },
                        "product_filename": {
                            "type": "string",
                            "description": "Optional destination CATProduct filename",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Allow replacing existing destination files",
                            "default": False,
                        },
                    },
                    "required": ["output_directory"],
                },
            },
            {
                "name": "catia_handle_duplicate_document_dialog",
                "description": (
                    "Detect and acknowledge CATIA's duplicate-document-identifier Open dialog. "
                    "Matches the exact diagnostic text and clicks only the OK button; returns "
                    "the captured dialog text for audit."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "catia_handle_save_as_referenced_documents_dialog",
                "description": (
                    "Detect CATIA's Save As confirmation asking to activate other referenced "
                    "documents for saving, and click only Yes after exact text matching."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "catia_close_documents_exact",
                "description": "Close exact named CATIA documents, optionally saving first.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "names": {"type": "array", "items": {"type": "string"}},
                        "save": {"type": "boolean", "default": False},
                    },
                    "required": ["names"],
                },
            },
            {
                "name": "catia_close_documents_by_path_prefix",
                "description": "Close all open CATIA documents whose absolute paths start with an exact directory prefix.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path_prefixes": {"type": "array", "items": {"type": "string"}},
                        "save": {"type": "boolean", "default": False},
                    },
                    "required": ["path_prefixes"],
                },
            },
            {
                "name": "catia_connect",
                "description": (
                    "Connect to CATIA V5. Attaches to a running instance or launches a new one. "
                    "Must be called before any other CATIA tool."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_disconnect",
                "description": "Disconnect from CATIA V5 (does not close CATIA).",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_new_part",
                "description": (
                    "Create a new empty Part document in CATIA V5. "
                    "A Part is used for single-body 3D modeling (sketches + features)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Optional name for the part",
                        },
                    },
                },
            },
            {
                "name": "catia_new_product",
                "description": (
                    "Create a new empty Product (assembly) document in CATIA V5. "
                    "A Product is used to assemble multiple Parts together."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Optional name for the product/assembly",
                        },
                    },
                },
            },
            {
                "name": "catia_open_document",
                "description": "Open an existing CATIA document from a file path (.CATPart, .CATProduct, .CATDrawing).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Full path to the CATIA document to open",
                        },
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "catia_save_document",
                "description": "Save the active CATIA document. Optionally save to a new path (Save As).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Optional new file path for Save As",
                        },
                    },
                },
            },
            {
                "name": "catia_close_document",
                "description": "Close the active CATIA document.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "save": {
                            "type": "boolean",
                            "description": "Whether to save before closing (default: false)",
                            "default": False,
                        },
                    },
                },
            },
            {
                "name": "catia_list_documents",
                "description": "List all open documents in CATIA V5 with their types and paths.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_get_active_document_info",
                "description": (
                    "Get detailed info about the active CATIA document: "
                    "name, type, path, part bodies, features, etc."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_activate_document",
                "description": (
                    "Activate one exact open CATIA document by name and verify that it "
                    "became the active document. Does not modify or save it."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
            {
                "name": "catia_activate_component",
                "description": (
                    "Resolve one exact component instance in the active CATProduct, "
                    "activate its referenced document, and verify the result."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"instance_name": {"type": "string"}},
                    "required": ["instance_name"],
                },
            },
            {
                "name": "catia_delete_bodies",
                "description": (
                    "Delete one or more named Body objects from the active CATPart. "
                    "The main body is protected unless explicitly included and allow_main_body is true."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Exact Body names to delete",
                        },
                        "allow_main_body": {
                            "type": "boolean",
                            "description": "Allow deleting the CATPart main body (default: false)",
                            "default": False,
                        },
                    },
                    "required": ["names"],
                },
            },
            {
                "name": "catia_clear_main_body",
                "description": (
                    "Delete all features and sketches from the active CATPart main body, "
                    "while preserving the main Body itself and the origin planes."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        match tool_name:
            case "catia_send_to_directory":
                return self._send_to_directory(
                    arguments["output_directory"],
                    arguments.get("product_filename"),
                    arguments.get("overwrite", False),
                )
            case "catia_handle_duplicate_document_dialog":
                return self._handle_duplicate_document_dialog()
            case "catia_handle_save_as_referenced_documents_dialog":
                return self._handle_save_as_referenced_documents_dialog()
            case "catia_close_documents_exact":
                return self._close_documents_exact(arguments["names"], arguments.get("save", False))
            case "catia_close_documents_by_path_prefix":
                return self._close_documents_by_path_prefix(
                    arguments["path_prefixes"], arguments.get("save", False)
                )
            case "catia_connect":
                return self.conn.connect()
            case "catia_disconnect":
                return self.conn.disconnect()
            case "catia_new_part":
                return self._new_part(arguments.get("name"))
            case "catia_new_product":
                return self._new_product(arguments.get("name"))
            case "catia_open_document":
                return self._open_document(arguments["file_path"])
            case "catia_activate_document":
                return self._activate_document(arguments["name"])
            case "catia_activate_component":
                return self._activate_component(arguments["instance_name"])
            case "catia_save_document":
                return self._save_document(arguments.get("file_path"))
            case "catia_close_document":
                return self._close_document(arguments.get("save", False))
            case "catia_list_documents":
                return self._list_documents()
            case "catia_get_active_document_info":
                return self._get_active_document_info()
            case "catia_delete_bodies":
                return self._delete_bodies(
                    arguments["names"], arguments.get("allow_main_body", False)
                )
            case "catia_clear_main_body":
                return self._clear_main_body()
            case _:
                raise ValueError(f"Unknown document tool: {tool_name}")

    @staticmethod
    def _click_referenced_save_as_prompt(stop: threading.Event, audit: dict[str, Any]) -> None:
        """Click only CATIA's exact referenced-document Save As confirmation."""
        import win32con
        import win32gui

        deadline = time.monotonic() + 30.0
        while not stop.is_set() and time.monotonic() < deadline:
            candidates: list[tuple[int, str, list[tuple[int, str, str]]]] = []

            def enum_window(hwnd: int, _: object) -> None:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd)
                if title not in ("另存为", "Save As"):
                    return
                children: list[tuple[int, str, str]] = []

                def enum_child(child: int, __: object) -> None:
                    children.append(
                        (child, win32gui.GetClassName(child), win32gui.GetWindowText(child))
                    )

                win32gui.EnumChildWindows(hwnd, enum_child, None)
                full_text = "\n".join(text for _, _, text in children if text)
                chinese = "激活其他文档保存操作" in full_text and "想要继续吗" in full_text
                english = (
                    "activate other documents" in full_text.lower()
                    and "continue" in full_text.lower()
                )
                if chinese or english:
                    candidates.append((hwnd, title, children))

            win32gui.EnumWindows(enum_window, None)
            if len(candidates) == 1:
                _, title, children = candidates[0]
                buttons = [
                    (child, text)
                    for child, class_name, text in children
                    if class_name == "Button" and text in ("是(&Y)", "Yes", "&Yes")
                ]
                if len(buttons) == 1:
                    captured = "\n".join(text for _, _, text in children if text)
                    win32gui.SendMessage(buttons[0][0], win32con.BM_CLICK, 0, 0)
                    audit.update({"handled": True, "title": title, "text": captured})
                    return
            stop.wait(0.2)

    def _send_to_directory(
        self,
        output_directory: str,
        product_filename: str | None = None,
        overwrite: bool = False,
    ) -> str:
        """Save an assembly and all referenced documents into an independent directory."""
        self.conn.ensure_connected()
        root_doc = self.conn.active_document
        try:
            root_product = root_doc.Product
        except Exception as exc:
            raise RuntimeError("Active document must be a CATProduct") from exc

        target_dir = os.path.abspath(output_directory)
        os.makedirs(target_dir, exist_ok=True)
        root_name = product_filename or root_doc.Name
        if not root_name.lower().endswith(".catproduct"):
            root_name += ".CATProduct"

        referenced: dict[str, Any] = {}

        def walk(product: Any) -> None:
            products = product.Products
            for index in range(1, products.Count + 1):
                child = products.Item(index)
                try:
                    doc = child.ReferenceProduct.Parent
                    full_name = os.path.abspath(doc.FullName)
                    referenced[os.path.normcase(full_name)] = doc
                except Exception as exc:
                    raise RuntimeError(
                        f"Referenced document is unavailable for component '{child.Name}'"
                    ) from exc
                try:
                    walk(child)
                except AttributeError:
                    pass

        walk(root_product)
        root_source = os.path.normcase(os.path.abspath(root_doc.FullName))
        referenced.pop(root_source, None)

        basename_sources: dict[str, str] = {}
        plan: list[tuple[Any, str, str]] = []
        for source_key, doc in sorted(referenced.items()):
            basename = os.path.basename(doc.FullName)
            folded = basename.casefold()
            prior = basename_sources.get(folded)
            if prior and os.path.normcase(prior) != source_key:
                raise ValueError(
                    f"Cannot package two different referenced documents with the same filename: {basename}"
                )
            basename_sources[folded] = source_key
            plan.append((doc, os.path.abspath(doc.FullName), os.path.join(target_dir, basename)))

        root_target = os.path.join(target_dir, root_name)
        targets = [target for _, _, target in plan] + [root_target]
        existing = [path for path in targets if os.path.exists(path)]
        if existing and not overwrite:
            raise FileExistsError(
                "Destination files already exist; set overwrite=true to replace them: "
                + ", ".join(existing)
            )

        saved: list[dict[str, str]] = []
        try:
            for doc, source, target in plan:
                # CATIA can block on a referenced-document activation prompt when
                # SaveAs is invoked on a non-active document. Explicit activation
                # makes the operation deterministic and mirrors Send To Directory.
                doc.Activate()
                doc.SaveAs(target)
                saved.append({"source": source, "target": target})

            root_doc.Activate()
            stop = threading.Event()
            dialog_audit: dict[str, Any] = {"handled": False}
            watcher = threading.Thread(
                target=self._click_referenced_save_as_prompt,
                args=(stop, dialog_audit),
                daemon=True,
            )
            watcher.start()
            try:
                root_doc.SaveAs(root_target)
            finally:
                stop.set()
                watcher.join(timeout=1.0)
        except Exception as exc:
            raise RuntimeError(
                f"Send to directory failed after {len(saved)} referenced documents were saved: {exc}"
            ) from exc

        verified: list[dict[str, str]] = []
        outside: list[dict[str, str]] = []
        target_prefix = os.path.normcase(target_dir + os.sep)

        def verify(product: Any) -> None:
            products = product.Products
            for index in range(1, products.Count + 1):
                child = products.Item(index)
                doc = child.ReferenceProduct.Parent
                full_name = os.path.abspath(doc.FullName)
                record = {"component": child.Name, "path": full_name}
                verified.append(record)
                normalized = os.path.normcase(full_name)
                if not (normalized.startswith(target_prefix) or normalized == os.path.normcase(target_dir)):
                    outside.append(record)
                try:
                    verify(child)
                except AttributeError:
                    pass

        verify(root_doc.Product)
        if outside:
            raise RuntimeError(
                "Packaging completed but reference verification found paths outside destination: "
                + json.dumps(outside, ensure_ascii=False)
            )

        return json.dumps(
            {
                "sent": True,
                "source_product": root_source,
                "target_product": root_target,
                "output_directory": target_dir,
                "unique_referenced_documents": len(plan),
                "component_references_verified": len(verified),
                "all_references_inside_output_directory": True,
                "saved_documents": saved,
                "save_as_dialog": dialog_audit,
            },
            ensure_ascii=False,
            indent=2,
        )

    def _handle_duplicate_document_dialog(self) -> str:
        """Acknowledge only CATIA's known duplicate-identifier Open diagnostic."""
        import win32con
        import win32gui

        candidates: list[tuple[int, str, list[tuple[int, str, str]]]] = []

        def enum_window(hwnd: int, _: object) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if title not in ("打开", "Open"):
                return
            children: list[tuple[int, str, str]] = []
            def enum_child(ch: int, __: object) -> None:
                children.append((ch, win32gui.GetClassName(ch), win32gui.GetWindowText(ch)))
            win32gui.EnumChildWindows(hwnd, enum_child, None)
            full_text = "\n".join(text for _, _, text in children if text)
            if ("相同标识" in full_text and "无法加载" in full_text) or (
                "same identifier" in full_text.lower() and "cannot" in full_text.lower()
            ):
                candidates.append((hwnd, title, children))

        win32gui.EnumWindows(enum_window, None)
        if not candidates:
            return json.dumps({"handled": False, "reason": "matching dialog not found"}, ensure_ascii=False)
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one duplicate-identifier dialog, found {len(candidates)}")

        hwnd, title, children = candidates[0]
        buttons = [(ch, text) for ch, cls, text in children
                   if cls == "Button" and text in ("确定", "OK", "&OK")]
        if len(buttons) != 1:
            raise RuntimeError(f"Expected one OK button, found {len(buttons)}")
        captured = "\n".join(text for _, _, text in children if text)
        win32gui.SendMessage(buttons[0][0], win32con.BM_CLICK, 0, 0)
        return json.dumps({"handled": True, "title": title, "text": captured}, ensure_ascii=False)

    def _handle_save_as_referenced_documents_dialog(self) -> str:
        """Confirm only the known CATIA Save As referenced-document prompt."""
        import win32con
        import win32gui

        candidates = []
        def enum_window(hwnd: int, _: object) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if title not in ("另存为", "Save As"):
                return
            children = []
            def enum_child(ch: int, __: object) -> None:
                children.append((ch, win32gui.GetClassName(ch), win32gui.GetWindowText(ch)))
            win32gui.EnumChildWindows(hwnd, enum_child, None)
            full_text = "\n".join(text for _, _, text in children if text)
            chinese = "激活其他文档保存操作" in full_text and "想要继续吗" in full_text
            english = "activate other documents" in full_text.lower() and "continue" in full_text.lower()
            if chinese or english:
                candidates.append((hwnd, title, children))
        win32gui.EnumWindows(enum_window, None)
        if not candidates:
            return json.dumps({"handled": False, "reason": "matching dialog not found"}, ensure_ascii=False)
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one Save As referenced-document dialog, found {len(candidates)}")
        _, title, children = candidates[0]
        yes = [(ch, text) for ch, cls, text in children
               if cls == "Button" and text in ("是(Y)", "是(&Y)", "是", "Yes", "&Yes")]
        if len(yes) != 1:
            raise RuntimeError(f"Expected one Yes button, found {len(yes)}")
        captured = "\n".join(text for _, _, text in children if text)
        win32gui.SendMessage(yes[0][0], win32con.BM_CLICK, 0, 0)
        return json.dumps({"handled": True, "title": title, "text": captured}, ensure_ascii=False)

    def _close_documents_exact(self, names: list[str], save: bool = False) -> str:
        self.conn.ensure_connected()
        docs = self.conn.documents
        available = [docs.Item(i).Name for i in range(1, docs.Count + 1)]
        missing = [name for name in names if name not in available]
        if missing:
            raise ValueError(f"Documents not found: {missing}")
        closed = []
        for name in names:
            doc = docs.Item(name)
            if save:
                doc.Save()
            doc.Close()
            closed.append(name)
        return json.dumps({"closed": closed, "saved": save}, ensure_ascii=False)

    def _close_documents_by_path_prefix(self, path_prefixes: list[str], save: bool = False) -> str:
        import os
        self.conn.ensure_connected()
        prefixes = [os.path.normcase(os.path.abspath(p)) for p in path_prefixes]
        docs = self.conn.documents
        targets = []
        for i in range(1, docs.Count + 1):
            doc = docs.Item(i)
            try:
                full_name = os.path.normcase(os.path.abspath(doc.FullName))
            except Exception:
                continue
            if any(full_name.startswith(prefix + os.sep) or full_name == prefix for prefix in prefixes):
                targets.append((doc, doc.FullName))
        closed = []
        for doc, full_name in reversed(targets):
            if save:
                doc.Save()
            doc.Close()
            closed.append(full_name)
        return json.dumps({"closed": closed, "saved": save}, ensure_ascii=False)

    def _new_part(self, name: str | None = None) -> str:
        self.conn.ensure_connected()
        docs = self.conn.documents
        doc = docs.Add("Part")
        part_name = doc.Part.Name
        if name:
            # Part.Name is read-only in some CATIA V5 releases/localizations.
            # Product.PartNumber is the supported user-facing identifier.
            try:
                doc.Product.PartNumber = name
                part_name = name
            except Exception:
                try:
                    doc.Part.Name = name
                    part_name = name
                except Exception:
                    pass
        self.conn.refresh_display()
        return f"Created new Part document: '{part_name}'"

    def _new_product(self, name: str | None = None) -> str:
        self.conn.ensure_connected()
        docs = self.conn.documents
        doc = docs.Add("Product")
        if name:
            doc.Product.Name = name
        product_name = doc.Product.Name
        self.conn.refresh_display()
        return f"Created new Product (assembly) document: '{product_name}'"

    def _open_document(self, file_path: str) -> str:
        self.conn.ensure_connected()
        docs = self.conn.documents
        doc = docs.Open(file_path)
        return f"Opened document: '{doc.Name}' from {file_path}"

    def _activate_document(self, name: str) -> str:
        self.conn.ensure_connected()
        docs = self.conn.documents
        matches = [docs.Item(index) for index in range(1, docs.Count + 1)
                   if docs.Item(index).Name == name]
        if not matches:
            raise ValueError(f"Open document not found: '{name}'")
        if len(matches) > 1:
            raise ValueError(f"Document name is ambiguous: '{name}' ({len(matches)} matches)")
        target = matches[0]
        target.Activate()
        active = self.conn.app.ActiveDocument
        if active.Name != name:
            raise RuntimeError(
                f"Activation verification failed: requested '{name}', active '{active.Name}'"
            )
        return json.dumps({
            "activated": True,
            "name": active.Name,
            "path": getattr(active, "FullName", ""),
        }, ensure_ascii=False, indent=2)

    def _activate_component(self, instance_name: str) -> str:
        root_doc = self.conn.active_document
        try:
            root = root_doc.Product
        except Exception as exc:
            raise RuntimeError("Active document must be a CATProduct") from exc

        matches: list[Any] = []
        def walk(product: Any) -> None:
            products = product.Products
            for index in range(1, products.Count + 1):
                child = products.Item(index)
                if child.Name == instance_name:
                    matches.append(child)
                try:
                    walk(child)
                except Exception:
                    pass
        walk(root)
        if not matches:
            raise ValueError(f"Component instance not found: '{instance_name}'")
        if len(matches) > 1:
            raise ValueError(
                f"Component instance name is ambiguous: '{instance_name}' ({len(matches)} matches)"
            )
        component = matches[0]
        try:
            referenced_doc = component.ReferenceProduct.Parent
            referenced_doc.Activate()
        except Exception as exc:
            raise RuntimeError(
                f"Referenced document for '{instance_name}' is unavailable or not loaded"
            ) from exc
        active = self.conn.app.ActiveDocument
        if active.Name != referenced_doc.Name:
            raise RuntimeError(
                f"Component activation verification failed: expected '{referenced_doc.Name}', "
                f"active '{active.Name}'"
            )
        return json.dumps({
            "activated": True,
            "instance_name": instance_name,
            "document": active.Name,
            "path": getattr(active, "FullName", ""),
        }, ensure_ascii=False, indent=2)

    def _save_document(self, file_path: str | None = None) -> str:
        doc = self.conn.active_document
        if file_path:
            doc.SaveAs(file_path)
            return f"Document saved as: {file_path}"
        else:
            doc.Save()
            return f"Document '{doc.Name}' saved"

    def _close_document(self, save: bool = False) -> str:
        doc = self.conn.active_document
        name = doc.Name
        if save:
            doc.Save()
        doc.Close()
        return f"Document '{name}' closed" + (" (saved)" if save else "")

    def _list_documents(self) -> str:
        self.conn.ensure_connected()
        docs = self.conn.documents
        result = []
        for i in range(1, docs.Count + 1):
            doc = docs.Item(i)
            doc_info = {
                "name": doc.Name,
                "path": doc.FullName if hasattr(doc, "FullName") else "unsaved",
            }
            # Detect document type
            try:
                _ = doc.Part
                doc_info["type"] = "CATPart"
            except Exception:
                try:
                    _ = doc.Product
                    doc_info["type"] = "CATProduct"
                except Exception:
                    doc_info["type"] = "Other"
            result.append(doc_info)

        if not result:
            return "No documents open in CATIA"
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _get_active_document_info(self) -> str:
        doc = self.conn.active_document
        info: dict[str, Any] = {
            "name": doc.Name,
            "path": doc.FullName if hasattr(doc, "FullName") else "unsaved",
        }

        # Try Part document
        try:
            part = doc.Part
            info["type"] = "CATPart"
            info["part_name"] = part.Name

            # List bodies
            bodies = part.Bodies
            body_list = []
            for i in range(1, bodies.Count + 1):
                body = bodies.Item(i)
                shapes = []
                for j in range(1, body.Shapes.Count + 1):
                    shapes.append(body.Shapes.Item(j).Name)
                body_list.append({
                    "name": body.Name,
                    "features": shapes,
                })
            info["bodies"] = body_list

            # List geometrical sets (hybrid bodies)
            try:
                hbs = part.HybridBodies
                geo_sets = []
                for i in range(1, hbs.Count + 1):
                    geo_sets.append(hbs.Item(i).Name)
                info["geometrical_sets"] = geo_sets
            except Exception:
                pass

            # Parameters count
            try:
                info["parameters_count"] = part.Parameters.Count
            except Exception:
                pass

            return json.dumps(info, indent=2, ensure_ascii=False)
        except Exception:
            pass

        # Try Product document
        try:
            product = doc.Product
            info["type"] = "CATProduct"
            info["product_name"] = product.Name
            info["part_number"] = product.PartNumber

            # List sub-products
            prods = product.Products
            children = []
            for i in range(1, prods.Count + 1):
                child = prods.Item(i)
                children.append({
                    "name": child.Name,
                    "part_number": child.PartNumber,
                })
            info["components"] = children
            return json.dumps(info, indent=2, ensure_ascii=False)
        except Exception:
            pass

        info["type"] = "Unknown"
        return json.dumps(info, indent=2, ensure_ascii=False)

    def _delete_bodies(self, names: list[str], allow_main_body: bool = False) -> str:
        if not names:
            raise ValueError("names must contain at least one Body name")

        doc = self.conn.active_document
        part = self.conn.get_active_part()
        bodies = part.Bodies
        main_body_name = part.MainBody.Name

        requested = list(dict.fromkeys(names))
        if main_body_name in requested and not allow_main_body:
            raise ValueError(f"Refusing to delete protected main body: {main_body_name}")

        available = {bodies.Item(i).Name for i in range(1, bodies.Count + 1)}
        missing = [name for name in requested if name not in available]
        if missing:
            raise ValueError(f"Body names not found: {missing}")

        selection = doc.Selection
        selection.Clear()
        for name in requested:
            selection.Add(bodies.Item(name))
        selection.Delete()
        selection.Clear()
        part.Update()
        self.conn.refresh_display()

        remaining = [bodies.Item(i).Name for i in range(1, bodies.Count + 1)]
        return json.dumps(
            {"deleted": requested, "remaining_bodies": remaining},
            indent=2,
            ensure_ascii=False,
        )

    def _clear_main_body(self) -> str:
        doc = self.conn.active_document
        part = self.conn.get_active_part()
        body = part.MainBody
        selection = doc.Selection

        feature_names = [body.Shapes.Item(i).Name for i in range(1, body.Shapes.Count + 1)]
        sketch_names = [body.Sketches.Item(i).Name for i in range(1, body.Sketches.Count + 1)]

        selection.Clear()
        for i in range(body.Shapes.Count, 0, -1):
            selection.Add(body.Shapes.Item(i))
        for i in range(body.Sketches.Count, 0, -1):
            selection.Add(body.Sketches.Item(i))
        if selection.Count > 0:
            selection.Delete()
        selection.Clear()
        part.Update()
        self.conn.refresh_display()

        return json.dumps(
            {
                "deleted_features": feature_names,
                "deleted_sketches": sketch_names,
                "remaining_features": body.Shapes.Count,
                "remaining_sketches": body.Sketches.Count,
            },
            indent=2,
            ensure_ascii=False,
        )
