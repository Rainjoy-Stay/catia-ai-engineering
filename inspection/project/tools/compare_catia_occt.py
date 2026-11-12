"""Compare native CATIA clash facts with exact OCCT STEP B-Rep facts."""

import argparse
import json
from pathlib import Path


def _catia_state(conflict):
    kind = str(conflict.get("type", "")).upper()
    if kind == "CLASH":
        return "SOLID_INTERFERENCE"
    if kind == "CONTACT":
        return "CONTACT"
    if kind == "CLEARANCE":
        return "CLEARANCE"
    return "REVIEW"


def _occt_state(fact):
    if fact.get("intersection_volume_mm3", 0.0) > 0.0:
        return "SOLID_INTERFERENCE"
    if fact.get("intersects"):
        return "CONTACT"
    if abs(float(fact.get("minimum_distance_mm", 0.0))) <= 1e-6:
        return "CONTACT"
    return "CLEARANCE"


def compare(catia, occt):
    catia_conflicts = catia.get("pairs", catia.get("conflicts", []))
    catia_states = [_catia_state(item) for item in catia_conflicts]
    occt_facts = occt.get("pair_facts", [])
    occt_states = [_occt_state(item) for item in occt_facts]
    catia_counts = {state: catia_states.count(state) for state in sorted(set(catia_states))}
    occt_counts = {state: occt_states.count(state) for state in sorted(set(occt_states))}
    catia_signature = sorted(catia_states)
    occt_signature = sorted(occt_states)
    return {
        "schema_version": "catia-occt-agreement.v1.0",
        "document": catia.get("document"),
        "catia_method": catia.get("method"),
        "occt_method": "OCCT_EXACT_BREP_DISTANCE_SECTION_COMMON",
        "geometry_authority": ["CATIA_NATIVE_DMU", "ORIGINAL_STEP_OCCT_BREP"],
        "catia_counts": catia_counts,
        "occt_counts": occt_counts,
        "catia_signature": catia_signature,
        "occt_signature": occt_signature,
        "agreement": catia_signature == occt_signature,
        "status": "PASS" if catia_signature == occt_signature else "REVIEW_REQUIRED",
        "notes": [
            "CATIA and OCCT are compared by interaction-state multiset when component names are unavailable in STEP.",
            "OCCT exact B-Rep is not replaced by tessellation or mesh fallback.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("catia_json", type=Path)
    parser.add_argument("occt_json", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compare(json.loads(args.catia_json.read_text(encoding="utf-8")), json.loads(args.occt_json.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
