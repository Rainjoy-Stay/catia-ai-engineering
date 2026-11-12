"""Bounded read-only CATIA Automation collector, attach-only (never launches).

No Selection, Activate, Update, Save, Export, document opening or geometry creation.
No claimed exact geometry: this collector reads structure and rigid placements.
"""
from __future__ import annotations

from typing import Any, Callable

from .snapshot import matrix


def catia_position(values: Any) -> list[float]:
    """CATIA GetComponents: X/Y/Z axis columns then translation in millimetres."""
    v = list(values)
    if len(v) != 12:
        raise ValueError("CATIA Position.GetComponents must return 12 numbers")
    return matrix([v[0], v[3], v[6], v[9], v[1], v[4], v[7], v[10],
                   v[2], v[5], v[8], v[11], 0, 0, 0, 1])  # type: ignore[return-value]


def native_position(product: Any) -> list[float]:
    import pythoncom
    values = product.Position._oleobj_.InvokeTypes(
        1611005953, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_EMPTY, 0),
        ((pythoncom.VT_BYREF | pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, 3),),
        tuple(0.0 for _ in range(12)))
    return catia_position(values)


def read_active(app: Any, *, position_reader: Callable = native_position,
                max_occurrences: int = 20000, max_items: int = 20000,
                max_depth: int = 80) -> dict:
    """Injectable collector so coverage/error behavior can be tested without CATIA."""
    if min(max_occurrences, max_items, max_depth) < 1:
        raise ValueError("Read budgets must be positive")
    doc = app.ActiveDocument
    errors: list[dict] = []

    def attr(obj: Any, field: str, scope: str, default: Any = None) -> Any:
        try:
            value = getattr(obj, field)
            return value
        except Exception as exc:
            errors.append({"scope": scope, "field": field, "error": type(exc).__name__})
            return default

    name = str(doc.Name)
    kind = name.rsplit(".", 1)[-1].casefold()
    if kind not in ("catpart", "catproduct"):
        raise ValueError("Only active CATPart/CATProduct documents are supported")
    source_path = attr(doc, "FullName", "active_document")
    saved_before = attr(doc, "Saved", "active_document")
    definitions: dict[str, dict] = {}
    occurrences_seen = 0

    def items(collection: Any, scope: str) -> tuple[int | None, list[tuple[int, Any]], list[dict]]:
        local_errors: list[dict] = []
        try:
            count = int(collection.Count)
        except Exception as exc:
            return None, [], [{"scope": scope, "error": type(exc).__name__}]
        records = []
        for index in range(1, min(count, max_items)+1):
            try:
                records.append((index, collection.Item(index)))
            except Exception as exc:
                local_errors.append({"scope": scope, "index": index, "error": type(exc).__name__})
        if count > max_items:
            local_errors.append({"scope": scope, "error": "ITEM_BUDGET_EXCEEDED", "omitted": count-max_items})
        return count, records, local_errors

    def read_definition(part_doc: Any) -> str:
        error_count_before = len(errors)
        part_name = str(attr(part_doc, "Name", "definition", "UNNAMED"))
        # Path or session document name describes a reference in this observation,
        # not a persistent enterprise part identity.
        key = str(attr(part_doc, "FullName", part_name) or "SESSION/"+part_name)
        if key in definitions:
            return key
        record: dict = {"name": part_name, "method": "CATIA_AUTOMATION_PART_STRUCTURE",
                        "read_status": "PARTIAL", "bodies": [], "read_errors": [],
                        "geometry_scope": "STRUCTURE_ONLY_NO_NATIVE_TOPOLOGY"}
        definitions[key] = record
        try:
            part = part_doc.Part
            expected, bodies, failures = items(part.Bodies, key+"/Bodies")
            record["bodies_expected"] = expected
            record["read_errors"].extend(failures)
            for index, body in bodies:
                body_name = str(attr(body, "Name", key+f"/Bodies/{index}", "UNNAMED"))
                entry = {"collection_index": index, "name": body_name, "shape_names": [],
                         "read_errors": [], "topology_status": "NOT_READ",
                         "closure_status": "UNKNOWN"}
                try:
                    shape_count, shapes, shape_errors = items(body.Shapes, key+"/"+body_name+"/Shapes")
                    entry["shapes_expected"] = shape_count
                    entry["shape_names"] = [str(attr(s, "Name", key+"/"+body_name, "UNNAMED"))
                                            for _, s in shapes]
                    entry["read_errors"].extend(shape_errors)
                except Exception as exc:
                    entry["read_errors"].append({"error": type(exc).__name__})
                record["bodies"].append(entry)
            # Hybrid geometry is explicitly not inventoried in this first reader.
            # Count only; never label an unexamined surface as reference-only.
            record["hybrid_body_count"] = attr(attr(part, "HybridBodies", key), "Count", key)
            record["read_status"] = "READ" if len(errors) == error_count_before and expected is not None and expected == len(bodies) and not failures and not any(
                b["read_errors"] for b in record["bodies"]) else "PARTIAL"
        except Exception as exc:
            record["read_errors"].append({"error": type(exc).__name__})
        return key

    def visit(product: Any, index: int, depth: int) -> dict:
        nonlocal occurrences_seen
        occurrences_seen += 1
        local_errors: list[dict] = []
        node: dict = {"name": str(attr(product, "Name", f"occurrence/{occurrences_seen}", "UNNAMED")),
                      "collection_index": index, "part_number": attr(product, "PartNumber", "product"),
                      "method": "CATIA_AUTOMATION_PRODUCT", "children": [], "read_errors": local_errors}
        if depth:
            try:
                node["local_transform"] = position_reader(product)
            except Exception as exc:
                node["local_transform"] = None
                local_errors.append({"field": "Position.GetComponents", "error": type(exc).__name__})
        try:
            reference_doc = product.ReferenceProduct.Parent
            if str(reference_doc.Name).casefold().endswith(".catpart"):
                node["definition_key"] = read_definition(reference_doc)
        except Exception as exc:
            local_errors.append({"field": "ReferenceProduct.Parent", "error": type(exc).__name__})
        try:
            collection = product.Products
            count = int(collection.Count)
            node["children_expected"] = count
            for child_index in range(1, min(count, max_items)+1):
                if depth >= max_depth or occurrences_seen >= max_occurrences:
                    local_errors.append({"field": "Products", "error": "READ_BUDGET_EXCEEDED"})
                    break
                try:
                    node["children"].append(visit(collection.Item(child_index), child_index, depth+1))
                except Exception as exc:
                    local_errors.append({"field": "Products.Item", "index": child_index,
                                         "error": type(exc).__name__})
            if count > max_items:
                local_errors.append({"field": "Products", "error": "ITEM_BUDGET_EXCEEDED"})
        except Exception as exc:
            node["children"] = None
            node["children_expected"] = None
            local_errors.append({"field": "Products", "error": type(exc).__name__})
        return node

    if kind == "catpart":
        root = {"name": name, "definition_key": read_definition(doc), "children_expected": 0,
                "children": [], "method": "CATIA_AUTOMATION_ACTIVE_PART"}
    else:
        root = visit(doc.Product, 0, 0)
    active_after = app.ActiveDocument
    saved_after = attr(doc, "Saved", "active_document_after")
    same_active = (str(active_after.Name) == name and
                   attr(active_after, "FullName", "active_document_after") == source_path)
    if not same_active or saved_before != saved_after:
        raise RuntimeError("Source state changed during read; discard this observation and recapture")
    return {"schema_version": "catia-understanding.observation.v1", "length_unit": "mm",
            "source": {"document": name, "path": source_path, "method": "CATIA_AUTOMATION_READ_ONLY",
                       "runtime_version": str(attr(attr(app, "SystemConfiguration", "application"), "Release", "application", "UNKNOWN"))},
            "root": root, "definitions": definitions,
            "source_state": {"saved_before": saved_before, "saved_after": saved_after,
                             "saved_state_check": "UNCHANGED" if isinstance(saved_before, bool) and isinstance(saved_after, bool) else "UNKNOWN",
                             "active_document_unchanged": same_active, "source_saved_by_tool": False,
                             "selection_used": False, "errors": errors},
            "scope": {"bodies_and_shapes": True, "hybrid_geometry": "COUNT_ONLY",
                      "parameters": "NOT_READ", "constraints": "NOT_READ", "native_topology": "NOT_READ"}}


def attach_and_read(**budgets: int) -> dict:
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        # GetActiveObject must fail if no running, registered CATIA is available.
        app = win32com.client.GetActiveObject("CATIA.Application")
        return read_active(app, **budgets)
    finally:
        pythoncom.CoUninitialize()
