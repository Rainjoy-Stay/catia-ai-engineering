"""Inspect a large multi-solid STEP/IGES as one exact single-Part source."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from catia_checker.large_single_part import (build_large_single_part_result,
                                              inspect_large_single_part_file)
from catia_checker.routing_rules import validate_rules


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--rules", type=Path, default=PROJECT / "config" / "rules-active.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    validate_rules(rules)
    def progress(event):
        print(json.dumps(event, ensure_ascii=False), flush=True)
    bundle = inspect_large_single_part_file(args.source, rules=rules, progress=progress)
    payload = build_large_single_part_result(
        bundle, document=args.source.name, rules=rules,
        run_id=f"SINGLEPART-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}",
        generated_at=datetime.now(timezone.utc).isoformat())
    source_path = args.source.resolve()
    digest = hashlib.sha256()
    with source_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    payload.setdefault("source", {}).update({
        "source_file": str(source_path),
        "source_sha256": digest.hexdigest(),
        "offline_import_required_for_screenshot": True,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
