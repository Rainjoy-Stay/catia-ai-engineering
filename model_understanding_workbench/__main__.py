"""python -m model_understanding_workbench --help"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .snapshot import build_snapshot, describe, find_objects, transform_point, compare_snapshots


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="CATIA 只读理解基线：结构、实例位姿、覆盖率和证据查询")
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture", help="读取当前 CATIA；不启动、不切换、不保存")
    capture.add_argument("--output", required=True)
    capture.add_argument("--max-occurrences", type=int, default=20000)
    capture.add_argument("--max-items", type=int, default=20000)
    capture.add_argument("--max-depth", type=int, default=80)
    build = sub.add_parser("build", help="从显式观察输入建立快照；不把旧 manifest 当成完整读取")
    build.add_argument("observation")
    build.add_argument("--output", required=True)
    query = sub.add_parser("query", help="按名称/零件号找候选；重复名称返回歧义")
    query.add_argument("snapshot")
    query.add_argument("text")
    detail = sub.add_parser("describe", help="读取对象与事实证据")
    detail.add_argument("snapshot")
    detail.add_argument("object_id")
    point = sub.add_parser("point", help="将实例局部点变换到根装配坐标系，单位 mm")
    point.add_argument("snapshot")
    point.add_argument("object_id")
    point.add_argument("xyz", nargs=3, type=float)
    compare = sub.add_parser("compare", help="检测快照变化；不猜测跨版本对象对应")
    compare.add_argument("before")
    compare.add_argument("after")
    args = parser.parse_args()
    if args.command in ("capture", "build"):
        target = Path(args.output)
        if target.exists():
            parser.error("输出目录已存在；请为本轮选择新目录")
        if args.command == "capture":
            from .catia_reader import attach_and_read
            try:
                observation = attach_and_read(max_occurrences=args.max_occurrences,
                                              max_items=args.max_items, max_depth=args.max_depth)
            except Exception as exc:
                write_new(target/"capture_failure.json", {"status": "CAPTURE_FAILED",
                          "error_type": type(exc).__name__, "detail": str(exc),
                          "source_saved_by_tool": False, "snapshot_created": False})
                raise SystemExit("CATIA 读取失败，诊断已保存；未建立模型快照")
        else:
            observation = load(args.observation)
        snapshot = build_snapshot(observation)
        write_new(target/"observation.json", observation)
        write_new(target/"snapshot.json", snapshot)
        result = {"snapshot_id": snapshot["snapshot_id"], "coverage": snapshot["coverage"],
                  "limitations": snapshot["limitations"], "output": str(target.resolve())}
    elif args.command == "query":
        result = find_objects(load(args.snapshot), args.text)
    elif args.command == "describe":
        result = describe(load(args.snapshot), args.object_id)
    elif args.command == "point":
        result = transform_point(load(args.snapshot), args.object_id, args.xyz)
    else:
        result = compare_snapshots(load(args.before), load(args.after))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
