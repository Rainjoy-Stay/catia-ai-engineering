"""Build the pipe-candidate review consumed by the main audit and Word report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from catia_checker.pipe_candidate_review import review_pipe_candidates


def _records(payload):
    records = payload if isinstance(payload, list) else payload.get("records", [])
    flattened = []
    for record in records:
        children = record.get("records") if isinstance(record, dict) else None
        if children:
            for child in children:
                merged = dict(child)
                for key in ("source_body_index", "source_body_name", "name"):
                    if key in record and key not in merged:
                        merged[key] = record[key]
                flattened.append(merged)
        else:
            flattened.append(record)
    return flattened


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path,
                        help="Exterior-scan JSON or a JSON list of candidate records")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-map", type=Path,
                        help="Optional JSON keyed by Body index with context_image/detail_image")
    args = parser.parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    records = _records(payload)
    if args.evidence_map:
        evidence = json.loads(args.evidence_map.read_text(encoding="utf-8"))
        for record in records:
            key = str(record.get("source_body_index", record.get("body_index", "")))
            record.update(evidence.get(key, {}))
    review = review_pipe_candidates(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
