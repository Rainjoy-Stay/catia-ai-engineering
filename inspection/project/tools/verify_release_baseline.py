"""Verify that the V4.5 DEV delivery matches its frozen acceptance baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from catia_checker.release_baseline import load_and_validate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=PROJECT / "release_baseline_v4_5.json")
    parser.add_argument("--root", type=Path, default=PROJECT.parent)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = load_and_validate(args.baseline, args.root)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

