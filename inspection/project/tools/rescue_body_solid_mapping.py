"""Resolve failed batch Body/Solid identities through disposable single-Body STEP probes."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parent
for value in (str(PROJECT), str(ROOT / "scripts")):
    if value not in sys.path:
        sys.path.insert(0, value)

from catia_checker.catia_body_batches import export_body_batches
from catia_checker.geometry_fingerprint import match_geometry_records
from catia_checker.occt_brep import OCCTBRepModel
from r18_connection import R18Connection


def build_rescue_plan(probe_payload: dict, replay_payload: dict) -> dict:
    shapes = (probe_payload.get("large_single_part_analysis") or {}).get("batch_plan", {}).get("shapes") or []
    replay = replay_payload.get("result") or replay_payload
    matched_sources = {str(item["source_id"]) for item in replay.get("matches") or []}
    matched_bodies = {int(item["target_id"]) for item in replay.get("matches") or []}
    body_count = int((probe_payload.get("source") or {}).get("source_body_count_before") or 0)
    return {
        "unresolved_shapes": [dict(item) for item in shapes if str(item.get("shape_id")) not in matched_sources],
        "body_indices": [index for index in range(1, body_count + 1) if index not in matched_bodies],
        "already_matched_count": len(matched_sources),
    }


def resolve_probe_manifests(unresolved_shapes: list[dict], probe_manifests: list[dict],
                            body_indices: list[int]) -> dict:
    probe_records = []
    probe_to_body = {}
    for body_index, manifest in zip(body_indices, probe_manifests):
        root = manifest.get("root_shape_id")
        for item in manifest.get("shapes") or []:
            if item.get("shape_id") == root:
                continue
            record = dict(item)
            qualified = f"BODY_{body_index:06d}::{record['shape_id']}"
            record["shape_id"] = qualified
            probe_to_body[qualified] = body_index
            probe_records.append(record)
    matched = match_geometry_records(
        probe_records, unresolved_shapes, source_id="shape_id", target_id="shape_id",
        tolerances={"relative_volume": 1e-4, "relative_area": 1e-4,
                    "centroid_mm": 1e-3, "bounds_mm": 1e-3})
    assignments = []
    for item in matched["matches"]:
        assignments.append({
            "shape_id": item["target_id"],
            "source_body_index": probe_to_body[item["source_id"]],
            "probe_shape_id": item["source_id"],
            "mapping_method": "SINGLE_BODY_STEP_MULTI_FEATURE_VERIFIED",
            "score": item["score"],
            "checks": item["checks"],
        })
    return {
        "assignments": assignments,
        "matched_count": len(assignments),
        "unresolved": matched["unresolved"],
        "probe_solid_count": len(probe_records),
        "is_complete": len(assignments) == len(unresolved_shapes),
        "sequence_fallback_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe_result", type=Path)
    parser.add_argument("identity_replay", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    probe_payload = json.loads(args.probe_result.read_text(encoding="utf-8"))
    replay_payload = json.loads(args.identity_replay.read_text(encoding="utf-8"))
    plan = build_rescue_plan(probe_payload, replay_payload)
    connection = R18Connection(); connection.connect()
    document = connection.active_document
    expected = str(probe_payload.get("document") or "")
    if expected and str(document.Name).casefold() != expected.casefold():
        raise RuntimeError(f"Active document mismatch: expected {expected}, got {document.Name}")
    temporary = Path(tempfile.mkdtemp(prefix="catia-single-body-rescue-"))
    before = (bool(document.Saved), int(document.Part.Bodies.Count))
    try:
        audit = export_body_batches(connection.app, document, temporary, batch_size=1,
                                    body_indices=plan["body_indices"],
                                    progress=lambda event: print(json.dumps(event, ensure_ascii=False), flush=True))
        manifests = []
        for path in audit["batch_files"]:
            model = OCCTBRepModel()
            manifests.append(model.load_step(path, lightweight=True))
        result = resolve_probe_manifests(plan["unresolved_shapes"], manifests, plan["body_indices"])
    finally:
        after = (bool(document.Saved), int(document.Part.Bodies.Count))
        shutil.rmtree(temporary, ignore_errors=True)
    if after != before:
        raise RuntimeError("Source CATPart state changed during rescue probing")
    output = {
        "schema_version": "body-solid-rescue.v1.0",
        "document": str(document.Name),
        "already_matched_count": plan["already_matched_count"],
        "probed_body_count": len(plan["body_indices"]),
        "unresolved_shape_count_before": len(plan["unresolved_shapes"]),
        "source_modified": False,
        "temporary_files_deleted": not temporary.exists(),
        **result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: output[key] for key in (
        "probed_body_count", "matched_count", "probe_solid_count", "is_complete")},
        ensure_ascii=False))
    return 0 if output["is_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
