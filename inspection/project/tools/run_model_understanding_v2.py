#!/usr/bin/env python3
"""Run the complete V2.0 model-understanding delivery workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="对 CATIA 当前打开的 STEP/IGES 导入模型执行检查，并生成 V2.0 审查包与验收报告。")
    parser.add_argument("geometry_source", type=Path, help="用于哑模型精确几何检查的 STEP/STP/IGES/IGS 文件")
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--previous-report", type=Path, help="可选：用于增量复检对比的上一版完整报告")
    args = parser.parse_args()
    if not args.geometry_source.is_file():
        parser.error(f"几何源文件不存在：{args.geometry_source}")
    if args.geometry_source.suffix.lower() not in {".step", ".stp", ".iges", ".igs"}:
        parser.error("几何源文件必须是 STEP/STP/IGES/IGS")

    tools = Path(__file__).resolve().parent
    output = args.output_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    full_report = output / "full-check.json"
    review_package = output / "review-package.json"
    acceptance_json = output / "acceptance.json"
    acceptance_md = output / "acceptance-report.md"

    subprocess.run([
        sys.executable, str(tools / "audit_all_component_clashes.py"),
        "--geometry-source", str(args.geometry_source.resolve()),
        "--output", str(full_report), "--skip-tubing",
    ], check=True, stdout=subprocess.DEVNULL)
    package_command = [
        sys.executable, str(tools / "build_model_understanding_review_package.py"),
        str(full_report), "--output", str(review_package),
    ]
    if args.previous_report:
        package_command.extend(["--previous", str(args.previous_report.resolve())])
    subprocess.run(package_command, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([
        sys.executable, str(tools / "accept_model_understanding_release.py"),
        str(review_package), "--json-output", str(acceptance_json),
        "--markdown-output", str(acceptance_md),
    ], check=True, stdout=subprocess.DEVNULL)

    result = {"status": "COMPLETE", "full_report": str(full_report),
              "review_package": str(review_package), "acceptance": str(acceptance_json),
              "acceptance_report": str(acceptance_md)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
