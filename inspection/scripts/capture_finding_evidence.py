"""Capture two CATIA views per actionable finding and add red component-location boxes."""
from __future__ import annotations

import argparse
import atexit
import ctypes
import hashlib
import json
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageGrab
import win32com.client
import win32con
import win32gui
import win32ui

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "project") not in sys.path:
    sys.path.insert(0, str(ROOT / "project"))

from catia_checker.result_locator import resolve_issue_target, select_issue_target
from catia_checker.geometry_fingerprint import (
    canonical_geometry_features, geometry_fingerprint, match_geometry_records_with_labels,
)
from catia_mcp import dev_extensions
from r18_connection import V5Connection
from catia_session_manager import CATIASessionManager

VIEWS = {
    "front": ((0, 0, -1), (0, 1, 0)),
    "isometric": ((-1, -1, -1), (0, 1, 0)),
    "right": ((-1, 0, 0), (0, 0, 1)),
    "top": ((0, -1, 0), (0, 0, 1)),
    "left": ((1, 0, 0), (0, 0, 1)),
}


def is_screenshot_candidate(finding: dict) -> bool:
    """Capture unresolved/review findings as well as explicit failures."""
    return str(finding.get("status") or "") in {"FAIL", "WARN", "ERROR", "NOT_EVALUATED"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def offline_shape_ids(payload: dict) -> list[str]:
    """Return the exact ordered solid ids recorded during offline inspection."""
    bundle = payload.get("large_single_part_analysis") or {}
    manifest = bundle.get("manifest") or {}
    root_shape_id = manifest.get("root_shape_id")
    return [str(item["shape_id"]) for item in (manifest.get("shapes") or [])
            if item.get("shape_id") and item.get("shape_id") != root_shape_id]


def offline_solid_records(payload: dict) -> list[dict]:
    """Return OCCT Solid records with the exact features used by inspection."""
    bundle = payload.get("large_single_part_analysis") or {}
    manifest = bundle.get("manifest") or {}
    root_shape_id = manifest.get("root_shape_id")
    return [dict(item) for item in (manifest.get("shapes") or [])
            if item.get("shape_id") and item.get("shape_id") != root_shape_id]


def offline_finding_shape_ids(finding: dict) -> list[str]:
    metadata = finding.get("metadata") or {}
    values = [str(metadata.get("geometry_object_a") or ""), str(metadata.get("geometry_object_b") or "")]
    if not all(values):
        raise ValueError("Offline finding has no exact solid identifiers")
    return values


def _catia_cog(measurable) -> list[float]:
    """Read SPA COG across the two pywin32 calling conventions used by CATIA."""
    try:
        value = measurable.GetCOG()
        if value is not None:
            return [float(value[index]) for index in range(3)]
    except TypeError:
        pass
    coordinates = [0.0, 0.0, 0.0]
    result = measurable.GetCOG(coordinates)
    value = result if result is not None else coordinates
    return [float(value[index]) for index in range(3)]


def measure_catia_bodies(document) -> list[dict]:
    """Measure imported Bodies through SPA without modifying or saving the part."""
    spa = document.GetWorkbench("SPAWorkbench")
    bodies = document.Part.Bodies
    records = []
    for index in range(1, int(bodies.Count) + 1):
        body = bodies.Item(index)
        reference = document.Part.CreateReferenceFromObject(body)
        measurable = spa.GetMeasurable(reference)
        record = {
            "body_index": index,
            "body_name": str(body.Name),
            "volume_mm3": float(measurable.Volume) * 1e9,
            "surface_area_mm2": float(measurable.Area) * 1e6,
            "centroid_mm": _catia_cog(measurable),
        }
        record["geometry_fingerprint"] = geometry_fingerprint(record)
        records.append(record)
    return records


def measure_catia_product_bodies(document) -> tuple[list[dict], dict[str, object]]:
    """Measure every Body referenced by a neutral-import CATProduct."""
    records, body_objects = [], {}
    products = document.Product.Products
    for component_index in range(1, int(products.Count) + 1):
        component = products.Item(component_index)
        parent = component.ReferenceProduct.Parent
        try:
            part = parent.Part
            bodies = part.Bodies
            spa = parent.GetWorkbench("SPAWorkbench")
        except Exception:
            continue
        for body_index in range(1, int(bodies.Count) + 1):
            body = bodies.Item(body_index)
            reference = part.CreateReferenceFromObject(body)
            measurable = spa.GetMeasurable(reference)
            key = f"{component_index}:{body_index}"
            record = {
                "body_index": key,
                "body_name": f"{component.Name}/{body.Name}",
                "volume_mm3": float(measurable.Volume) * 1e9,
                "surface_area_mm2": float(measurable.Area) * 1e6,
            }
            try:
                record["centroid_mm"] = _catia_cog(measurable)
            except Exception:
                pass
            record["geometry_fingerprint"] = geometry_fingerprint(record)
            records.append(record); body_objects[key] = body
    return records, body_objects


def build_offline_body_mapping(solid_records: list[dict], body_records: list[dict],
                               body_objects: dict[str, object]) -> tuple[dict, dict]:
    """Map Solid ids to Bodies only when geometry proves a unique assignment."""
    readiness = {
        "occt": all(len(canonical_geometry_features(item)) >= 2 for item in solid_records),
        "catia_spa": all(len(canonical_geometry_features(item)) >= 2 for item in body_records),
    }
    if not all(readiness.values()):
        unresolved = [{"source_id": str(item.get("shape_id")),
                       "candidate_target_ids": [], "reason": "INSUFFICIENT_GEOMETRY_FEATURES"}
                      for item in solid_records]
        result = {"matches": [], "unresolved": unresolved, "is_complete": False,
                  "source_count": len(solid_records), "target_count": len(body_records),
                  "matched_count": 0}
    else:
        result = match_geometry_records_with_labels(
            solid_records, body_records, source_id="shape_id", target_id="body_index",
            source_label="source_name", target_label="body_name",
            tolerances={"relative_volume": 1e-4, "relative_area": 1e-4,
                        "centroid_mm": 1e-3, "bounds_mm": 1e-3})
        if not result["matches"] and len(solid_records) == len(body_records):
            # CATIA imported-product Bodies can expose volume and area through
            # SPA while refusing Body COG.  Accept only an exact one-to-one
            # volume+area assignment; never fall back to STEP/body sequence.
            candidates = {}
            for source in solid_records:
                options = []
                for target in body_records:
                    vd = abs(float(source["volume_mm3"]) - float(target["volume_mm3"])) / max(abs(float(source["volume_mm3"])), 1e-12)
                    ad = abs(float(source["surface_area_mm2"]) - float(target["surface_area_mm2"])) / max(abs(float(source["surface_area_mm2"])), 1e-12)
                    if vd <= 1e-4 and ad <= 1e-4:
                        options.append((str(target["body_index"]), vd + ad))
                candidates[str(source["shape_id"])] = options
            reverse = {}
            for sid, options in candidates.items():
                for tid, score in options:
                    reverse.setdefault(tid, []).append((sid, score))
            matches = []
            for sid, options in candidates.items():
                if len(options) == 1 and len(reverse.get(options[0][0], [])) == 1:
                    matches.append({"source_id": sid, "target_id": options[0][0],
                                    "score": options[0][1], "checks": [
                                        {"feature": "volume_mm3", "match": True},
                                        {"feature": "area_mm2", "match": True}],
                                    "mapping_method": "UNIQUE_VOLUME_AREA_NO_SEQUENCE"})
            if len(matches) == len(solid_records):
                result = {"matches": matches, "unresolved": [], "is_complete": True,
                          "source_count": len(solid_records), "target_count": len(body_records),
                          "matched_count": len(matches),
                          "target_records": {str(x["body_index"]): x for x in body_records}}
    mapping = {item["source_id"]: body_objects[item["target_id"]]
               for item in result["matches"] if item["target_id"] in body_objects}
    audit = {
        "method": "MULTI_FEATURE_EXACT_ONE_TO_ONE",
        "sequence_fallback_used": False,
        "feature_readiness": readiness,
        "source_count": result["source_count"],
        "target_count": result["target_count"],
        "matched_count": len(mapping),
        "is_complete": bool(result["is_complete"] and len(mapping) == len(solid_records)),
        "matches": result["matches"],
        "unresolved": result["unresolved"],
        "catia_body_records": body_records,
    }
    return mapping, audit


def import_offline_catia_part(app, payload: dict, source_file: Path):
    """Import through CATIA and prove Solid-to-Body identity by geometry."""
    solid_records = offline_solid_records(payload)
    connection = V5Connection()
    connection.connect()
    transaction = json.loads(dev_extensions.dispatch(connection, "import_neutral_for_inspection", {
        "source_file": str(source_file), "timeout_s": 90, "activate": True,
    }))
    document = app.Documents.Item(transaction["imported"]["name"])
    if transaction["imported"].get("type") == "CATProduct":
        body_records, body_objects = measure_catia_product_bodies(document)
    else:
        bodies = document.Part.Bodies
        body_records = measure_catia_bodies(document)
        body_objects = {str(index): bodies.Item(index) for index in range(1, int(bodies.Count) + 1)}
    if len(body_records) != len(solid_records):
        document.Close()
        raise ValueError(
            f"CATIA native-import Body count {len(body_records)} != inspected solid count {len(solid_records)}")
    mapping, mapping_audit = build_offline_body_mapping(
        solid_records, body_records, body_objects)
    return document, mapping, transaction, mapping_audit


def highlight_bounds(before_path: Path, selected_path: Path) -> tuple[int, int, int, int] | None:
    """Locate CATIA selection pixels by comparing the same view before/after selection."""
    with Image.open(before_path) as source:
        before = source.convert("RGB")
    with Image.open(selected_path) as source:
        image = source.convert("RGB")
    if before.size != image.size:
        return None
    base_pixels, pixels = before.load(), image.load()
    strict, sensitive = ([], []), ([], [])
    # Keep the tree in the evidence, but exclude it and the window chrome from
    # red-box detection.  Reframe centers geometry in the remaining viewport.
    x_start, x_end = int(image.width * 0.26), int(image.width * 0.92)
    # CATIA's menu/toolbars occupy the upper strip and can repaint when the
    # selection changes; exclude them from both strict and fallback detection.
    y_start, y_end = int(image.height * 0.15), int(image.height * 0.94)
    for y in range(y_start, y_end, 2):
        for x in range(x_start, x_end, 2):
            r, g, b = pixels[x, y]
            br, bg, bb = base_pixels[x, y]
            changed = abs(r - br) + abs(g - bg) + abs(b - bb)
            # The before/after delta prevents naturally colourful model geometry
            # from being mistaken for CATIA selection highlighting.
            if changed > 100 and max(r, g, b) - min(r, g, b) > 70:
                strict[0].append(x); strict[1].append(y)
            # Some CATIA render modes highlight by brightness rather than hue.
            # This fallback still requires a same-view before/after delta and
            # uses a higher sample threshold to reject antialiasing noise.
            if changed > 45:
                sensitive[0].append(x); sensitive[1].append(y)
    xs, ys = strict if len(strict[0]) >= 20 else sensitive
    if len(xs) < 60:
        return None
    margin = max(12, min(image.size) // 50)
    return (max(0, min(xs) - margin), max(0, min(ys) - margin),
            min(image.width - 1, max(xs) + margin), min(image.height - 1, max(ys) + margin))


def mark(source: Path, output: Path, box: tuple[int, int, int, int], label: str) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    draw = ImageDraw.Draw(image); font = ImageFont.load_default()
    stroke = max(5, min(image.size) // 150)
    draw.rectangle(box, outline=(230, 0, 0), width=stroke)
    x, y = box[:2]
    text_box = draw.textbbox((x, y), label, font=font)
    w, h = text_box[2] - text_box[0] + 12, text_box[3] - text_box[1] + 8
    top = max(0, y - h)
    draw.rectangle((x, top, min(image.width, x + w), y), fill=(230, 0, 0))
    draw.text((x + 6, top + 3), label, fill="white", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=94)


def capture_catia_window(hwnd: int, path: Path) -> None:
    """Capture CATIA's complete top-level window, including chrome and tree."""
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    if right <= left or bottom <= top:
        raise RuntimeError("CATIA window has invalid bounds")
    width, height = right - left, bottom - top
    window_dc = win32gui.GetWindowDC(hwnd)
    source_dc = win32ui.CreateDCFromHandle(window_dc)
    memory_dc = source_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source_dc, width, height)
    memory_dc.SelectObject(bitmap)
    try:
        # PW_RENDERFULLCONTENT renders an occluded/background CATIA window.
        rendered = ctypes.windll.user32.PrintWindow(hwnd, memory_dc.GetSafeHdc(), 2)
        if rendered != 1:
            raise RuntimeError("Windows PrintWindow failed for CATIA")
        info = bitmap.GetInfo()
        bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]),
                                 bits, "raw", "BGRX", 0, 1)
        image.save(path, quality=94)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        memory_dc.DeleteDC()
        source_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)


def fit_model_with_margin(viewer) -> None:
    """Fit the full model to the viewport without shrinking large assemblies excessively."""
    viewer.Reframe()
    viewer.Update()


def exact_locator_points(payload: dict, finding: dict) -> list[list[float]]:
    """Return STEP-exact public-volume or closest-point coordinates."""
    metadata = finding.get("metadata") or {}
    a = str(metadata.get("geometry_object_a") or "")
    b = str(metadata.get("geometry_object_b") or "")
    manifest = (payload.get("large_single_part_analysis") or {}).get("manifest") or {}
    for fact in manifest.get("pair_facts") or []:
        if {str(fact.get("object_a")), str(fact.get("object_b"))} != {a, b}:
            continue
        if finding.get("status") == "FAIL":
            center = fact.get("section_center_mm")
            if center:
                return [[float(value) for value in center]]
            samples = fact.get("section_sample_points_mm") or []
            if samples:
                return [[sum(float(point[index]) for point in samples) / len(samples)
                         for index in range(3)]]
        return [[float(value) for value in point]
                for point in (fact.get("closest_point_a_mm"), fact.get("closest_point_b_mm")) if point]
    return []


def create_temporary_locator_points(body_object: object,
                                    coordinates: list[list[float]]) -> list[object]:
    """Create unsaved datum points only in the temporary imported STEP part."""
    if not coordinates:
        return []
    part = body_object.Parent.Parent
    container = part.HybridBodies.Add()
    container.Name = "STEP_CHECK_TEMP_LOCATORS"
    factory = part.HybridShapeFactory
    result = []
    for index, xyz in enumerate(coordinates, 1):
        point = factory.AddNewPointCoord(float(xyz[0]), float(xyz[1]), float(xyz[2]))
        point.Name = f"LOCATOR_{index}"
        container.AppendHybridShape(point)
        result.append(point)
    part.Update()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--source-file", type=Path,
                        help="Offline STEP/IGES source to import temporarily for verified screenshot capture")
    parser.add_argument("--max-findings", type=int, default=20,
                        help="Maximum actionable findings to capture, prioritized ERROR/FAIL/WARN")
    args = parser.parse_args()
    args.result = args.result.resolve()
    payload = json.loads(args.result.read_text(encoding="utf-8"))
    app = win32com.client.GetActiveObject("CATIA.Application")
    original_doc = app.ActiveDocument
    session = CATIASessionManager(app)
    atexit.register(session.restore)
    offline_components = None
    import_transaction = None
    offline_mapping_audit = None
    if args.source_file:
        source_file = args.source_file.resolve()
        recorded_path = Path(str((payload.get("source") or {}).get("source_file") or "")).resolve()
        if source_file != recorded_path:
            raise RuntimeError(f"Offline screenshot source path mismatch: {source_file} != {recorded_path}")
        recorded_hash = str((payload.get("source") or {}).get("source_sha256") or "")
        if not recorded_hash or _sha256(source_file) != recorded_hash:
            raise RuntimeError("Offline screenshot source fingerprint mismatch")
        doc, offline_components, import_transaction, offline_mapping_audit = import_offline_catia_part(
            app, payload, source_file)
        session.register_temporary_document(doc)
    else:
        doc = original_doc
        expected_document = str(payload.get("document") or "")
        if expected_document and str(doc.Name).casefold() != expected_document.casefold():
            raise RuntimeError(
                f"Active CATIA document changed before screenshot capture: expected {expected_document}, got {doc.Name}")
    catia_hwnd = session.maximize()
    selection = doc.Selection; viewer = app.ActiveWindow.ActiveViewer
    evidence_dir = (args.result.parent / "evidence").resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    priority = {"ERROR": 0, "FAIL": 1, "WARN": 2}
    candidates = sorted(payload.get("findings", []), key=lambda item: (priority.get(item.get("status"), 9), item.get("issue_id", "")))
    actionable = [item for item in candidates if is_screenshot_candidate(item)]
    capture_limit = max(0, args.max_findings)
    missing.extend(f"{item.get('issue_id')}:capture_limit" for item in actionable[capture_limit:])
    for finding in actionable[:capture_limit]:
        finding["evidence"] = [item for item in finding.get("evidence", [])
                               if item.get("kind") != "SCREENSHOT"]
        selection.Clear()
        try:
            if args.source_file:
                shape_ids = offline_finding_shape_ids(finding)
                missing_shapes = [value for value in shape_ids if value not in offline_components]
                if missing_shapes:
                    raise ValueError(f"Offline component mapping missing: {missing_shapes}")
                for shape_id in shape_ids:
                    selection.Add(offline_components[shape_id])
                located = {"location_kind": "OFFLINE_OCCT_SOLID_COMPONENT"}
            else:
                target = resolve_issue_target(payload, str(finding.get("issue_id")))
                located = select_issue_target(doc, target)
            resolved_objects = [selection.Item(i).Value for i in range(1, int(selection.Count) + 1)]
            resolved = [str(x) for x in (finding.get("object_a"), finding.get("object_b")) if x]
            locator_points = (create_temporary_locator_points(
                resolved_objects[0], exact_locator_points(payload, finding)) if args.source_file else [])
        except Exception as exc:
            missing.append(f"{finding.get('issue_id')}:{type(exc).__name__}")
            selection.Clear()
            continue
        if not resolved_objects:
            missing.append(f"{finding.get('issue_id')}:empty_selection"); selection.Clear(); continue
        # Fit the whole imported model, not the current selection.  CATIA may
        # otherwise zoom to specification-tree nodes for imported Bodies.
        selection.Clear()
        fit_model_with_margin(viewer)
        for view_name, (sight, up) in VIEWS.items():
            viewpoint = viewer.Viewpoint3D
            viewpoint.PutSightDirection(sight); viewpoint.PutUpDirection(up)
            selection.Clear(); fit_model_with_margin(viewer)
            before = evidence_dir / f"{finding['issue_id']}_{view_name}_unselected.jpg"
            raw = evidence_dir / f"{finding['issue_id']}_{view_name}_raw.jpg"
            marked = evidence_dir / f"{finding['issue_id']}_{view_name}_marked.jpg"
            selection.Clear(); viewer.Update(); capture_catia_window(catia_hwnd, before)
            for point in locator_points:
                selection.Add(point)
            viewer.Update()
            capture_catia_window(catia_hwnd, raw)
            box = highlight_bounds(before, raw)
            if box is None:
                missing.append(f"{finding.get('issue_id')}:{view_name}"); continue
            mark(raw, marked, box, str(finding["issue_id"]))
            finding.setdefault("evidence", []).append({
                "kind": "SCREENSHOT", "source": "CATIA exact-coordinate locator view + deterministic color bounds",
                "description": f"{view_name}定位图：红框由STEP精确公共体积中心或最近点坐标在CATIA中的临时定位点生成",
                "path": str(marked), "object_paths": resolved,
                "data": {"view": view_name, "pixel_box": list(box), "raw_path": str(raw),
                         "unselected_path": str(before), "location_method": "CATIA temporary exact-coordinate locator + same-view selection delta",
                         "location_kind": located.get("location_kind")},
            })
        selection.Clear()
    session.restore()
    # The reporting contract requires two useful views per finding, not every
    # attempted camera direction.  Keep a finding incomplete only when fewer
    # than two deterministic red-box views succeeded.
    insufficient = []
    for finding in actionable[:capture_limit]:
        count = sum(1 for item in finding.get("evidence", []) if item.get("kind") == "SCREENSHOT")
        if count < 2:
            insufficient.append(f"{finding.get('issue_id')}:only_{count}_views")
    missing = [item for item in missing if item.endswith(":capture_limit")] + insufficient
    payload.setdefault("audit", {})["screenshot_evidence_missing"] = missing
    payload["audit"]["catia_window_capture"] = {
        "maximized": True,
        "entire_window": True,
        "specification_tree_included": True,
        "specification_tree_excluded_from_red_box_detection": True,
    }
    payload["audit"]["catia_session_transaction"] = session.audit()
    if import_transaction:
        payload["audit"]["catia_native_neutral_import"] = import_transaction
    if offline_mapping_audit:
        payload["audit"]["offline_catia_body_mapping"] = offline_mapping_audit
    payload["audit"]["screenshot_capture_limit"] = args.max_findings
    payload.setdefault("confidence_budget", {}).setdefault("degraded", [])
    if missing:
        payload["confidence_budget"]["degraded"].append("部分问题因截图数量上限或定位失败，未能生成可靠红框截图；清单已写入audit")
        payload["confidence_budget"]["is_complete"] = False
    args.result.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS" if not missing else "PARTIAL", "missing": missing}, ensure_ascii=False))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
