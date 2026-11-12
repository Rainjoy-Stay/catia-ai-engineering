"""Resolve stable inspection findings back to exact CATIA Body indexes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _find_issue(report: dict[str, Any], issue_id: str) -> dict[str, Any]:
    matches = [x for x in report.get("findings", []) if str(x.get("issue_id")) == issue_id]
    if not matches:
        raise ValueError(f"Issue ID not found: {issue_id}")
    if len(matches) != 1:
        raise ValueError(f"Issue ID is not unique: {issue_id}")
    return matches[0]


def location_capability(finding: dict[str, Any]) -> dict[str, str]:
    metadata = finding.get("metadata") or {}
    if metadata.get("source_body_a") or metadata.get("source_body_b"):
        return {"kind": "CATPART_BODY", "reason": "CATIA Body索引和名称映射完整"}
    if str(finding.get("rule_id") or "").startswith("DMU.") and (
        finding.get("object_a") or finding.get("object_b")
    ):
        return {"kind": "CATPRODUCT_COMPONENT", "reason": "CATIA DMU组件实例名称"}
    interface = metadata.get("opening_interface") or {}
    locators = (interface.get("source_locators") or {}).values()
    if any(isinstance(x, dict) and x.get("source_body_index") and x.get("source_body_name") for x in locators):
        return {"kind": "CATPART_BODY_CONTEXT", "reason": "精确面引用不可复现；定位到校验后的承载Body"}
    return {"kind": "UNAVAILABLE", "reason": "该问题没有可验证的CATIA对象映射，已禁止猜测定位"}


def resolve_issue_bodies(report: dict[str, Any], issue_id: str) -> dict[str, Any]:
    finding = _find_issue(report, issue_id)
    metadata = finding.get("metadata") or {}
    bodies = []
    for side in ("a", "b"):
        record = metadata.get(f"source_body_{side}")
        if not record:
            continue
        index = record.get("source_body_index")
        name = record.get("source_body_name")
        if not isinstance(index, int) or index < 1 or not isinstance(name, str) or not name:
            raise ValueError(f"Issue {issue_id} has an invalid source_body_{side} mapping")
        bodies.append({"side": side, "index": index, "name": name})
    if not bodies:
        raise ValueError(f"Issue {issue_id} has no CATIA Body mapping")
    return {
        "issue_id": issue_id,
        "document": str(report.get("document") or ""),
        "bodies": bodies,
    }


def resolve_issue_target(report: dict[str, Any], issue_id: str) -> dict[str, Any]:
    finding = _find_issue(report, issue_id)
    capability = location_capability(finding)
    if capability["kind"] == "CATPART_BODY":
        result = resolve_issue_bodies(report, issue_id)
        result["kind"] = capability["kind"]
        return result
    if capability["kind"] == "CATPRODUCT_COMPONENT":
        names = list(dict.fromkeys(str(x) for x in (finding.get("object_a"), finding.get("object_b")) if x))
        return {"issue_id": issue_id, "document": str(report.get("document") or ""),
                "kind": capability["kind"], "components": names}
    if capability["kind"] == "CATPART_BODY_CONTEXT":
        interface = (finding.get("metadata") or {}).get("opening_interface") or {}
        locators = (interface.get("source_locators") or {}).values()
        bodies = []
        for locator in locators:
            if not isinstance(locator, dict): continue
            index, name = locator.get("source_body_index"), locator.get("source_body_name")
            if isinstance(index, int) and index > 0 and isinstance(name, str) and name:
                key = (index, name)
                if not any((x["index"], x["name"]) == key for x in bodies):
                    bodies.append({"index": index, "name": name, "face_id": locator.get("face_id"),
                                   "face_centroid_mm": locator.get("face_centroid_mm"),
                                   "face_area_mm2": locator.get("face_area_mm2")})
        return {"issue_id": issue_id, "document": str(report.get("document") or ""),
                "kind": capability["kind"], "bodies": bodies}
    raise ValueError(capability["reason"])


def load_issue_bodies(report_path: str | Path, issue_id: str) -> dict[str, Any]:
    path = Path(report_path).expanduser().resolve()
    report = json.loads(path.read_text(encoding="utf-8"))
    result = resolve_issue_bodies(report, issue_id)
    result["report_path"] = str(path)
    return result


def load_issue_target(report_path: str | Path, issue_id: str) -> dict[str, Any]:
    path = Path(report_path).expanduser().resolve()
    report = json.loads(path.read_text(encoding="utf-8"))
    result = resolve_issue_target(report, issue_id)
    result["report_path"] = str(path)
    return result


def select_issue_bodies(document: Any, resolved: dict[str, Any]) -> dict[str, Any]:
    expected_document = resolved.get("document")
    if expected_document and str(document.Name).casefold() != str(expected_document).casefold():
        raise ValueError(
            f"Active CATIA document is {document.Name!s}, but report belongs to {expected_document}"
        )
    bodies = document.Part.Bodies
    saved_before = bool(getattr(document, "Saved", False)) if hasattr(document, "Saved") else None
    body_count_before = int(bodies.Count)
    selected = []
    values = []
    for record in resolved["bodies"]:
        index = int(record["index"])
        if index > int(bodies.Count):
            raise ValueError(f"Body index {index} exceeds active CATPart Body count {bodies.Count}")
        body = bodies.Item(index)
        actual_name = str(body.Name)
        if actual_name != record["name"]:
            raise ValueError(
                f"Body #{index} name mismatch: report={record['name']!r}, CATIA={actual_name!r}"
            )
        visual_values = []
        try:
            visual_values = [body.Shapes.Item(i) for i in range(1, int(body.Shapes.Count) + 1)]
        except Exception:
            pass
        values.extend(visual_values or [body])
        selected.append({"index": index, "name": actual_name,
                         "selected_geometry_count": len(visual_values) or 1,
                         "selection_level": "BODY_SHAPES" if visual_values else "BODY_CONTAINER"})
    selection = document.Selection
    try:
        document.Activate()
    except Exception:
        pass
    selection.Clear()
    for value in values:
        selection.Add(value)
    try:
        viewer = document.Application.ActiveWindow.ActiveViewer
        viewer.Update()
    except Exception:
        pass
    saved_after = bool(getattr(document, "Saved", False)) if hasattr(document, "Saved") else None
    return {
        "issue_id": resolved["issue_id"],
        "document": str(document.Name),
        "selected_count": len(selected), "selected_geometry_count": int(selection.Count),
        "selected_bodies": selected,
        "source_saved_before": saved_before, "source_saved_after": saved_after,
        "source_body_count_before": body_count_before, "source_body_count_after": int(bodies.Count),
        "source_modified": (saved_before != saved_after or body_count_before != int(bodies.Count)),
    }


def _walk_products(product: Any) -> list[Any]:
    result = []
    children = product.Products
    for index in range(1, int(children.Count) + 1):
        child = children.Item(index)
        result.append(child)
        result.extend(_walk_products(child))
    return result


def select_issue_target(document: Any, resolved: dict[str, Any]) -> dict[str, Any]:
    if resolved.get("kind") in {"CATPART_BODY", "CATPART_BODY_CONTEXT"} or "bodies" in resolved:
        result = select_issue_bodies(document, resolved)
        result["location_kind"] = resolved.get("kind") or "CATPART_BODY"
        if result["location_kind"] == "CATPART_BODY_CONTEXT":
            result["precision"] = "BODY_CONTEXT_ONLY"
            result["note"] = "CATIA未提供可复现Face引用；已定位承载Body，面级事实仍来自精确SPA/OCCT记录"
        return result
    expected_document = resolved.get("document")
    if expected_document and str(document.Name).casefold() != str(expected_document).casefold():
        raise ValueError(f"Active CATIA document is {document.Name!s}, but report belongs to {expected_document}")
    saved_before = bool(getattr(document, "Saved", False)) if hasattr(document, "Saved") else None
    products = _walk_products(document.Product)
    values, selected = [], []
    for name in resolved.get("components", []):
        matches = [x for x in products if str(x.Name) == name]
        if not matches:
            raise ValueError(f"CATIA component instance not found: {name}")
        if len(matches) != 1:
            raise ValueError(f"CATIA component instance name is ambiguous: {name} ({len(matches)} matches)")
        value = matches[0]
        values.append(value)
        selected.append({"name": str(value.Name), "part_number": str(getattr(value, "PartNumber", ""))})
    selection = document.Selection
    selection.Clear()
    for value in values:
        selection.Add(value)
    saved_after = bool(getattr(document, "Saved", False)) if hasattr(document, "Saved") else None
    return {"issue_id": resolved["issue_id"], "document": str(document.Name),
            "location_kind": "CATPRODUCT_COMPONENT", "selected_count": int(selection.Count),
            "selected_components": selected, "source_saved_before": saved_before,
            "source_saved_after": saved_after, "source_modified": saved_before != saved_after}
