#!/usr/bin/env python3
"""Evaluate and write the V2.0 release acceptance record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catia_checker.model_understanding.productization.acceptance import (
    acceptance_markdown, evaluate_acceptance,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    args = parser.parse_args()
    package = json.loads(args.package.read_text(encoding="utf-8"))
    acceptance = evaluate_acceptance(package)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(acceptance_markdown(acceptance, package), encoding="utf-8")
    print(json.dumps(acceptance, ensure_ascii=False, indent=2))
    return 0 if acceptance["release_status"].startswith("ACCEPTED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
