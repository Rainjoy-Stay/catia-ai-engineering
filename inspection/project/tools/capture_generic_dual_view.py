"""Capture reusable CATIA overview/detail evidence without fixed Body numbers.

The script operates on the active CATPart or the top level of an active
CATProduct.  Targets and optional context objects are selected at run time by
their exact CATIA tree names or one-based collection indices.  It snapshots
show/color/opacity/inheritance and the camera before changing display state,
then restores them in a finally block.  It never saves the CATIA document.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import win32com.client


VIEWS = {
    "front": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    "back": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "top": ((0.0, -1.0, 0.0), (0.0, 0.0, -1.0)),
    "bottom": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "left": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "right": ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "isometric": ((-1.0, -1.0, -1.0), (0.0, 1.0, 0.0)),
}
COLORS = {
    "yellow": (255, 230, 0),
    "red": (220, 40, 40),
    "green": (0, 190, 70),
    "blue": (35, 115, 220),
    "orange": (240, 130, 30),
    "magenta": (200, 50, 180),
    "cyan": (0, 170, 190),
}
DEFAULT_TARGET_COLORS = [(255, 161, 56), (31, 214, 224), COLORS["green"], COLORS["blue"]]
CAPTURE_FORMAT = {".jpg": 5, ".jpeg": 5, ".bmp": 4, ".tif": 2, ".tiff": 2}

# CATIA automation enums.  SetShow: 0=show, 1=hide.  Inheritance property
# kinds follow the CATIA V5 Automation VisPropertySet contract.
SHOW, HIDE = 0, 1
PROP_COLOR, PROP_OPACITY = 0, 1


@dataclass(frozen=True)
class Item:
    index: int
    name: str
    path: str
    kind: str
    tree_object: Any
    display_object: Any

    @property
    def key(self) -> str:
        return f"{self.kind}-index:{self.index}"


@dataclass
class DisplayState:
    show: int
    color: tuple[int, int, int]
    color_inheritance: int
    opacity: int
    opacity_inheritance: int


def _payload(result: Any) -> tuple[Any, ...]:
    """Normalize pywin32 multi-out return values to a tuple."""
    if isinstance(result, tuple):
        return result
    if isinstance(result, list):
        return tuple(result)
    return (result,)


def _out_values(result: Any, count: int, label: str) -> tuple[int, ...]:
    values = _payload(result)
    if len(values) == count + 1:  # status followed by output parameters
        values = values[1:]
    if len(values) != count:
        raise RuntimeError(f"CATIA {label} returned {values!r}; expected {count} output value(s)")
    return tuple(int(x) for x in values)


def _read_show(selection: Any, obj: Any) -> int:
    selection.Clear()
    selection.Add(obj)
    props = selection.VisProperties
    show, = _out_values(props.GetShow(), 1, "GetShow")
    selection.Clear()
    return show


def snapshot_display(selection: Any, item: Item) -> DisplayState:
    # Visibility belongs to the tree node; color/opacity are applied to the
    # first displayable shape for CATPart Bodies, exactly as in the old script.
    show = _read_show(selection, item.tree_object)
    selection.Clear()
    selection.Add(item.display_object)
    props = selection.VisProperties
    color = _out_values(props.GetRealColor(), 3, "GetRealColor")
    opacity, = _out_values(props.GetRealOpacity(), 1, "GetRealOpacity")
    color_inheritance, = _out_values(
        props.GetRealInheritance(PROP_COLOR), 1, "GetRealInheritance(color)")
    opacity_inheritance, = _out_values(
        props.GetRealInheritance(PROP_OPACITY), 1, "GetRealInheritance(opacity)")
    selection.Clear()
    return DisplayState(show, color, color_inheritance, opacity, opacity_inheritance)


def set_display(selection: Any, item: Item, *, show: int | None = None,
                color: tuple[int, int, int] | None = None,
                opacity: int | None = None, color_inheritance: int = 0,
                opacity_inheritance: int = 0) -> None:
    selection.Clear()
    if show is not None:
        selection.Add(item.tree_object)
        props = selection.VisProperties
        props.SetShow(int(show))
        selection.Clear()
    if color is not None or opacity is not None:
        selection.Add(item.display_object)
        props = selection.VisProperties
    if color is not None:
        props.SetRealColor(*(int(x) for x in color), int(color_inheritance))
    if opacity is not None:
        props.SetRealOpacity(int(opacity), int(opacity_inheritance))
    selection.Clear()


def restore_display(selection: Any, item: Item, state: DisplayState) -> None:
    set_display(
        selection, item, show=state.show, color=state.color, opacity=state.opacity,
        color_inheritance=state.color_inheritance,
        opacity_inheritance=state.opacity_inheritance,
    )


def display_object_for_body(body: Any) -> Any:
    """Match the historical script: style the first shape when one exists."""
    try:
        if int(body.Shapes.Count) > 0:
            return body.Shapes.Item(1)
    except Exception:
        pass
    return body


def inventory_active_document(document: Any) -> tuple[str, list[Item]]:
    name = str(document.Name)
    lower = name.casefold()
    items: list[Item] = []
    if lower.endswith(".catpart"):
        collection = document.Part.Bodies
        for index in range(1, int(collection.Count) + 1):
            body = collection.Item(index)
            name = str(body.Name)
            items.append(Item(index, name, name, "body", body, display_object_for_body(body)))
        return "CATPart", items
    if lower.endswith(".catproduct"):
        def walk(collection: Any, parent_path: str = "") -> None:
            for child_index in range(1, int(collection.Count) + 1):
                product = collection.Item(child_index)
                name = str(product.Name)
                path = f"{parent_path}/{name}" if parent_path else name
                items.append(Item(len(items) + 1, name, path, "component", product, product))
                try:
                    walk(product.Products, path)
                except Exception:
                    pass
        walk(document.Product.Products)
        return "CATProduct", items
    raise RuntimeError(f"Active document must be CATPart or CATProduct, got {name!r}")


def resolve_selector(selector: str, items: list[Item]) -> Item:
    """Resolve exact tree name or explicit 1-based index; never guess duplicates."""
    raw = selector.strip()
    match = re.fullmatch(r"(?:(?:body|component)-)?index:(\d+)", raw, re.I)
    if match or raw.isdigit():
        index = int(match.group(1) if match else raw)
        candidates = [item for item in items if item.index == index]
    else:
        name = raw.split(":", 1)[1] if re.match(r"^(body|component):", raw, re.I) else raw
        path_matches = [item for item in items if item.path == name]
        candidates = path_matches or [item for item in items if item.name == name]
    if not candidates:
        raise ValueError(f"Selector {selector!r} did not match an active-document tree object")
    if len(candidates) != 1:
        choices = ", ".join(item.key for item in candidates)
        raise ValueError(f"Selector {selector!r} is ambiguous; use one of: {choices}")
    return candidates[0]


def resolve_many(selectors: Iterable[str], items: list[Item]) -> list[Item]:
    resolved: list[Item] = []
    seen: set[str] = set()
    for selector in selectors:
        item = resolve_selector(selector, items)
        if item.key not in seen:
            resolved.append(item)
            seen.add(item.key)
    return resolved


def parse_color(value: str) -> tuple[int, int, int]:
    key = value.strip().casefold()
    if key in COLORS:
        return COLORS[key]
    parts = value.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("color must be a name or R,G,B")
    try:
        rgb = tuple(int(x.strip()) for x in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("color channels must be integers") from exc
    if not all(0 <= x <= 255 for x in rgb):
        raise argparse.ArgumentTypeError("color channels must be between 0 and 255")
    return rgb  # type: ignore[return-value]


def _camera_vector(app: Any, viewpoint: Any, method: str) -> list[float]:
    try:
        return [float(x) for x in getattr(viewpoint, method)()]
    except Exception:
        # CATSafeArrayVariant output parameters are not handled consistently by
        # every pywin32 binding.  CATIA's SystemService can marshal the array.
        function = "read_" + method.casefold()
        vba = f"""
Public Function {function}(viewpoint)
  Dim values(2)
  viewpoint.{method} values
  {function} = values
End Function
"""
        values = app.SystemService.Evaluate(vba, 0, function, [viewpoint])
        return [float(x) for x in values]


def snapshot_camera(app: Any, viewpoint: Any) -> dict[str, Any]:
    try:
        zoom = float(viewpoint.Zoom)
    except Exception:
        zoom = None
    return {
        "origin": _camera_vector(app, viewpoint, "GetOrigin"),
        "sight": _camera_vector(app, viewpoint, "GetSightDirection"),
        "up": _camera_vector(app, viewpoint, "GetUpDirection"),
        "focus_distance": float(viewpoint.FocusDistance),
        "projection_mode": int(viewpoint.ProjectionMode),
        "zoom": zoom,
    }


def restore_camera(viewpoint: Any, state: dict[str, Any]) -> None:
    viewpoint.PutOrigin(state["origin"])
    viewpoint.PutSightDirection(state["sight"])
    viewpoint.PutUpDirection(state["up"])
    viewpoint.FocusDistance = state["focus_distance"]
    viewpoint.ProjectionMode = state["projection_mode"]
    try:
        if state["zoom"] is None:
            return
        viewpoint.Zoom = state["zoom"]
    except Exception:
        pass  # Zoom is only available in parallel projection mode.


def set_view(viewer: Any, view: str) -> None:
    sight, up = VIEWS[view]
    viewpoint = viewer.Viewpoint3D
    viewpoint.PutSightDirection(sight)
    viewpoint.PutUpDirection(up)


def capture(viewer: Any, path: Path, settle_seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    viewer.Update()
    if settle_seconds:
        time.sleep(settle_seconds)
    viewer.CaptureToFile(CAPTURE_FORMAT[path.suffix.casefold()], str(path))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Capture CATIA context/detail screenshots with runtime-selected objects")
    result.add_argument("--list", action="store_true", help="List available active-document objects and exit")
    result.add_argument("--target", action="append", default=[],
                        help="Target exact tree name or 1-based index; repeat for multiple targets")
    result.add_argument("--context", action="append", default=[],
                        help="Context exact tree name/index; omit to use all non-target objects")
    result.add_argument("--output-dir", type=Path, help="Output directory (required unless --list)")
    result.add_argument("--prefix", default="issue", help="Safe filename prefix")
    result.add_argument("--context-opacity", type=int, default=52,
                        help="Background opacity 0..255; default 52 (~20%% opaque)")
    result.add_argument("--context-color", type=parse_color, default=(185, 190, 198))
    result.add_argument("--target-color", action="append", type=parse_color, default=[],
                        help="Target color name or R,G,B; repeated values follow target order")
    result.add_argument("--context-view", choices=VIEWS, default="isometric")
    result.add_argument("--detail-view", choices=VIEWS, default="front")
    result.add_argument("--settle-seconds", type=float, default=1.0)
    result.add_argument("--format", choices=("jpg", "bmp", "tif"), default="jpg")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not 0 <= args.context_opacity <= 255:
        raise SystemExit("--context-opacity must be between 0 and 255")
    if args.settle_seconds < 0:
        raise SystemExit("--settle-seconds cannot be negative")
    safe_prefix = re.sub(r"[^0-9A-Za-z_.-]+", "_", args.prefix).strip("._") or "issue"

    app = win32com.client.GetActiveObject("CATIA.Application")
    document = app.ActiveDocument
    document_name = str(document.Name)
    document_path = str(getattr(document, "FullName", "") or "")
    document_saved_before = bool(document.Saved)
    document_kind, items = inventory_active_document(document)

    if args.list:
        print(json.dumps({
            "document": document_name, "document_path": document_path,
            "document_kind": document_kind,
            "objects": [{"index": x.index, "name": x.name, "path": x.path, "kind": x.kind,
                         "selector": x.key} for x in items],
        }, ensure_ascii=False, indent=2))
        return 0
    if not args.target:
        raise SystemExit("At least one --target is required (run with --list first)")
    if args.output_dir is None:
        raise SystemExit("--output-dir is required")

    targets = resolve_many(args.target, items)
    target_keys = {item.key for item in targets}
    context = resolve_many(args.context, items) if args.context else [
        item for item in items if item.key not in target_keys]
    context = [item for item in context if item.key not in target_keys]
    colors = list(args.target_color)
    while len(colors) < len(targets):
        colors.append(DEFAULT_TARGET_COLORS[len(colors) % len(DEFAULT_TARGET_COLORS)])

    selection = document.Selection
    viewer = app.ActiveWindow.ActiveViewer
    viewpoint = viewer.Viewpoint3D
    # Snapshot every object because the detail image hides all non-targets.
    display_states = {item.key: snapshot_display(selection, item) for item in items}
    camera_state = snapshot_camera(app, viewpoint)
    output = args.output_dir.resolve()
    extension = "." + args.format
    context_path = output / f"{safe_prefix}_context{extension}"
    detail_path = output / f"{safe_prefix}_detail{extension}"
    audit_path = output / f"{safe_prefix}_capture.json"
    audit: dict[str, Any] = {
        "schema_version": "catia-dual-view-capture.v1",
        "document": document_name, "document_path": document_path,
        "document_kind": document_kind, "saved_before": document_saved_before,
        "targets": [{"selector": item.key, "name": item.name, "path": item.path,
                     "color": list(color)}
                    for item, color in zip(targets, colors)],
        "context": [{"selector": item.key, "name": item.name, "path": item.path}
                    for item in context],
        "context_opacity": args.context_opacity,
        "context_color": list(args.context_color),
        "context_view": args.context_view, "detail_view": args.detail_view,
        "context_image": str(context_path), "detail_image": str(detail_path),
        "restoration": {"attempted": False, "verified": False, "errors": []},
    }

    error: BaseException | None = None
    try:
        # Overall/context image: transparent grey surroundings, opaque targets.
        for item in items:
            set_display(selection, item, show=SHOW)
        for item in context:
            set_display(selection, item, show=SHOW,
                        color=args.context_color, opacity=args.context_opacity)
        for item, color in zip(targets, colors):
            set_display(selection, item, show=SHOW, color=color, opacity=255)
        set_view(viewer, args.context_view)
        viewer.Reframe()
        capture(viewer, context_path, args.settle_seconds)

        # Local/detail image: hide every non-target object, keep targets opaque.
        for item in items:
            set_display(selection, item, show=HIDE)
        # A hidden assembly parent can hide its selected child.  Keep only the
        # ancestor chain visible; sibling components remain explicitly hidden.
        target_paths = {item.path for item in targets}
        ancestors = [item for item in items if any(
            target_path.startswith(item.path + "/") for target_path in target_paths)]
        for item in ancestors:
            set_display(selection, item, show=SHOW)
        for item, color in zip(targets, colors):
            set_display(selection, item, show=SHOW, color=color, opacity=255)
        set_view(viewer, args.detail_view)
        viewer.Reframe()
        capture(viewer, detail_path, args.settle_seconds)
    except BaseException as exc:
        error = exc
        audit["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        audit["restoration"]["attempted"] = True
        for item in reversed(items):
            try:
                restore_display(selection, item, display_states[item.key])
            except Exception as exc:
                audit["restoration"]["errors"].append(
                    f"{item.key}/{item.name}: {type(exc).__name__}: {exc}")
        try:
            restore_camera(viewpoint, camera_state)
            viewer.Update()
        except Exception as exc:
            audit["restoration"]["errors"].append(f"camera: {type(exc).__name__}: {exc}")
        try:
            selection.Clear()
        except Exception:
            pass
        audit["saved_after"] = bool(document.Saved)
        audit["restoration"]["verified"] = not audit["restoration"]["errors"]
        output.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    if audit["restoration"]["errors"]:
        raise RuntimeError(
            "CATIA screenshots may have been created, but display/camera restoration was incomplete; "
            f"see {audit_path}") from error
    if error is not None:
        raise error
    if not context_path.is_file() or not detail_path.is_file():
        raise RuntimeError("CATIA did not create both expected screenshot files")
    print(json.dumps({
        "status": "PASS", "context_image": str(context_path),
        "detail_image": str(detail_path), "audit": str(audit_path),
        "saved_state_unchanged": document_saved_before == bool(document.Saved),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
