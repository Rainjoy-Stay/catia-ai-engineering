#!/usr/bin/env python3
"""Build one product-facing model-understanding review package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catia_checker.model_understanding.productization import build_review_package


def _read(path: Path | None):
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--verifications", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package = build_review_package(_read(args.report), previous_report=_read(args.previous),
                                   verifications=_read(args.verifications))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "overview": package["overview"],
                      "pending_review": package["review_queue"]["pending_count"],
                      "safety_gate": package["safety"]["semantic_regression_gate"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
