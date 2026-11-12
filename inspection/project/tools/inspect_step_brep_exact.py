"""Run exact OCCT B-Rep health and pair inspection on an original STEP file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from catia_checker.occt_brep import OCCTBRepModel, sweep_and_prune_pairs
from catia_checker.semantic_interactions import assess_solid_interactions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pairs", type=int, default=10000)
    parser.add_argument("--margin-mm", type=float, default=1e-5,
                        help="Geometric AABB overlap tolerance used by sweep-and-prune")
    args = parser.parse_args()
    model = OCCTBRepModel()
    manifest = model.load_step(args.step)
    shapes = [item for item in manifest["shapes"] if item["shape_id"] != "STEP_ROOT"]
    description_index = {item["shape_id"]: item for item in shapes}
    broad_phase = sweep_and_prune_pairs(shapes, margin_mm=args.margin_mm)
    candidate_pairs = broad_phase.pop("pairs")
    pairs = []
    truncated = False
    for first, second in candidate_pairs:
        if len(pairs) >= args.max_pairs:
            truncated = True
            break
        first_desc, second_desc = description_index[first], description_index[second]
        kind_a = "SOLID" if first_desc["solid_count"] else "SURFACE"
        kind_b = "SOLID" if second_desc["solid_count"] else "SURFACE"
        fact = model.pair_fact(first, second,
                 entity_a={"geometry_kind": kind_a, "capabilities": ["EXACT_BREP"]},
                 entity_b={"geometry_kind": kind_b, "capabilities": ["EXACT_BREP"]})
        fact["object_a_name"] = first_desc.get("source_name")
        fact["object_b_name"] = second_desc.get("source_name")
        pairs.append(fact)
    assessments = assess_solid_interactions(pairs)
    payload = {**manifest, "pair_fact_count": len(pairs), "pair_facts": pairs,
               "solid_interaction_assessments": assessments,
               "broad_phase": broad_phase, "truncated": truncated,
               "geometry_authority": "ORIGINAL_STEP_OCCT_BREP",
               "mesh_used": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
