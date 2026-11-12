"""Safely update the active rules or create a one-run rules file."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from catia_checker.routing_rules import validate_rules

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "project" / "config"
ACTIVE = CONFIG / "rules-active.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    radius = parser.add_mutually_exclusive_group()
    radius.add_argument("--bend-radius-mm", type=float)
    radius.add_argument("--bend-radius-ratio", type=float)
    parser.add_argument("--general-clearance-mm", type=float)
    parser.add_argument("--hot-zone-clearance-mm", type=float)
    parser.add_argument("--opening-coaxial-tolerance-mm", type=float)
    parser.add_argument("--opening-angle-tolerance-deg", type=float)
    parser.add_argument("--opening-radial-clearance-min-mm", type=float)
    parser.add_argument("--opening-radial-clearance-max-mm", type=float)
    parser.add_argument("--opening-axial-tolerance-mm", type=float)
    parser.add_argument("--status", choices=("APPROVED", "ASSUMED_PENDING_APPROVAL"))
    parser.add_argument("--source-title")
    parser.add_argument("--source-id")
    parser.add_argument("--source-revision")
    parser.add_argument("--for-this-run", action="store_true")
    parser.add_argument("--ruleset-id", required=True)
    args = parser.parse_args()

    rules = json.loads(ACTIVE.read_text(encoding="utf-8"))
    routing, source = rules["routing"], rules.setdefault("source", {})
    opening = rules.setdefault("opening_interface", {})
    if args.bend_radius_mm is not None:
        routing.update({"bend_radius_mode": "absolute_mm",
                        "minimum_bend_radius_mm": args.bend_radius_mm})
    if args.bend_radius_ratio is not None:
        routing.update({"bend_radius_mode": "ratio_r_over_d",
                        "minimum_bend_radius_ratio_r_over_d": args.bend_radius_ratio})
    if args.general_clearance_mm is not None:
        routing["minimum_general_clearance_mm"] = args.general_clearance_mm
    if args.hot_zone_clearance_mm is not None:
        routing["minimum_hot_zone_clearance_mm"] = args.hot_zone_clearance_mm
    for key, value in (
        ("coaxial_tolerance_mm", args.opening_coaxial_tolerance_mm),
        ("angle_tolerance_deg", args.opening_angle_tolerance_deg),
        ("radial_clearance_min_mm", args.opening_radial_clearance_min_mm),
        ("radial_clearance_max_mm", args.opening_radial_clearance_max_mm),
        ("axial_tolerance_mm", args.opening_axial_tolerance_mm),
    ):
        if value is not None:
            opening[key] = value
    if args.status:
        routing["threshold_status"] = args.status
    for key, value in (("title", args.source_title), ("document_id", args.source_id),
                       ("revision", args.source_revision)):
        if value is not None:
            source[key] = value
    rules["ruleset_id"] = args.ruleset_id
    rules["modified_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    validate_rules(rules)
    output = (CONFIG / f"rules-run-{datetime.now():%Y%m%d-%H%M%S}.json"
              if args.for_this_run else ACTIVE)
    output.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "rules_file": output.name,
                      "ruleset_id": rules["ruleset_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
