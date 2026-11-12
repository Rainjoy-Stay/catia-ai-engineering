#!/usr/bin/env python3
"""Plan phase-one CATIA pipe centerline candidates from a JSON request."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from catia_checker.route_planning import (  # noqa: E402
    OrthogonalRoutePlanner,
    request_from_dict,
    result_to_dict,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="CATIA phase-one orthogonal pipe route planner")
    parser.add_argument("request", type=Path, help="Input request JSON")
    parser.add_argument("--output", type=Path, required=True, help="Output result JSON")
    args = parser.parse_args()

    try:
        payload = json.loads(args.request.read_text(encoding="utf-8"))
        request = request_from_dict(payload)
        result = result_to_dict(OrthogonalRoutePlanner().plan(request))
        for candidate in result["candidates"]:
            candidate["section_diameter_mm"] = request.pipe_outer_diameter_mm
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"规划失败：{exc}", file=sys.stderr)
        return 2
    print(f"规划结果已写入：{args.output}")
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
