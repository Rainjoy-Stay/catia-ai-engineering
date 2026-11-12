"""Run exact OCCT Face distance and section checks on an original IGES file."""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from catia_checker.occt_brep import OCCTBRepModel, sweep_and_prune_pairs
from catia_checker.intersection_events import aggregate_intersection_events
from catia_checker.logical_components import (
    assemble_pipe_logical_components, recover_logical_components,
)
from catia_checker.engineering_roles import classify_tubular_roles
from catia_checker.semantic_interactions import enrich_intersection_events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iges", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-pairs", type=int, default=0,
                        help="Safety cap for exact candidates; 0 means no cap")
    parser.add_argument("--margin-mm", type=float, default=1e-5,
                        help="Geometric AABB overlap tolerance used by sweep-and-prune")
    parser.add_argument("--event-merge-tolerance-mm", type=float, default=25.0)
    args = parser.parse_args()
    model = OCCTBRepModel()
    manifest = model.load_iges(args.iges)
    faces = [item for item in manifest["shapes"] if item["shape_id"] != "IGES_ROOT"]
    broad_phase = sweep_and_prune_pairs(faces, margin_mm=args.margin_mm)
    candidates = broad_phase.pop("pairs")
    facts = []
    truncated = False
    for first, second in candidates:
        if args.max_pairs > 0 and len(facts) >= args.max_pairs:
            truncated = True
            break
        facts.append(model.surface_pair_fact(first, second,
            entity_a={"geometry_kind": "FACE", "capabilities": ["EXACT_BREP"]},
            entity_b={"geometry_kind": "FACE", "capabilities": ["EXACT_BREP"]}))
    events = aggregate_intersection_events(
        facts, merge_tolerance_mm=args.event_merge_tolerance_mm)
    logical_components = recover_logical_components(faces, facts)
    pipe_components = assemble_pipe_logical_components(logical_components, facts)
    engineering_roles = classify_tubular_roles(logical_components, facts)
    semantic_events = enrich_intersection_events(
        events, logical_components, engineering_roles, facts)
    payload = {**manifest, "pair_fact_count": len(facts), "pair_facts": facts,
               "intersection_events": events,
               "logical_components": logical_components,
               "pipe_logical_components": pipe_components,
               "engineering_roles": engineering_roles,
               "semantic_intersection_events": semantic_events,
               "broad_phase": broad_phase,
               "truncated": truncated,
               "geometry_authority": "ORIGINAL_IGES_OCCT_BREP", "mesh_used": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
