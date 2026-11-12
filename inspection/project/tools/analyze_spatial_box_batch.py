"""Bounded exact analysis for a virtual spatial-box sample."""
from __future__ import annotations
import concurrent.futures, itertools, json, subprocess, sys
from collections import Counter
from pathlib import Path

def pair_worker(request: Path, output: Path) -> None:
    from catia_checker.occt_brep import OCCTBRepModel
    from standalone.step_interference_filter import classify
    a, b = json.loads(request.read_text(encoding="utf-8"))
    model = OCCTBRepModel()
    for item in (a, b): model.load_brep(item["shape_id"], Path(item["cache_file"]))
    da, db = model.describe(a["shape_id"]), model.describe(b["shape_id"])
    da["body_key"], db["body_key"] = f"BODY_{a['index']}", f"BODY_{b['index']}"
    distance = model.distance(a["shape_id"], b["shape_id"])
    overlap = model.local_overlap_evidence(a["shape_id"], b["shape_id"])
    fact = {"minimum_distance_mm": distance["minimum_distance_mm"],
            "intersection_volume_mm3": max(0.0, overlap["volume_mm3"]), "exact_brep": True}
    output.write_text(json.dumps({"body_a": a["index"], "name_a": a["name"],
        "body_b": b["index"], "name_b": b["name"], "fact": fact,
        "distance_evidence": distance, "overlap_evidence": overlap,
        "decision": classify(fact, da, db)}, ensure_ascii=False, indent=2), encoding="utf-8")

def main() -> None:
    if len(sys.argv) == 3:
        pair_worker(Path(sys.argv[1]), Path(sys.argv[2])); return
    out = Path(sys.argv[1]); bodies = json.loads((out / "box_body_caches.json").read_text(encoding="utf-8"))
    pair_dir = out / "pairs"; pair_dir.mkdir(exist_ok=True); tasks = []
    for a, b in itertools.combinations(bodies, 2):
        stem = f"BODY_{a['index']}_{b['index']}"; req = pair_dir / f"{stem}.input.json"; target = pair_dir / f"{stem}.result.json"
        req.write_text(json.dumps([a, b], ensure_ascii=False), encoding="utf-8"); tasks.append((a, b, req, target))
    def run(task):
        a, b, req, target = task
        try:
            p = subprocess.run([sys.executable, __file__, str(req), str(target)], capture_output=True, text=True, timeout=20)
            if p.returncode: raise RuntimeError(p.stderr[-300:])
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"body_a": a["index"], "name_a": a["name"], "body_b": b["index"], "name_b": b["name"],
                "error": type(exc).__name__, "decision": {"status": "NOT_EVALUATED", "category": "UNDETERMINED", "reason": "BOUNDED_EXACT_PAIR_TIMEOUT_OR_ERROR"}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records = list(pool.map(run, tasks))
    selection = json.loads((out / "spatial_selection.json").read_text(encoding="utf-8"))
    result = {"schema_version": "spatial-box-analysis.v1", "scope": "ONE_EXACT_SPATIAL_BOX", "status": "NOT_EVALUATED",
        "box_bounds_mm": selection["box_bounds_mm"], "body_count": len(bodies),
        "body_records": [{"index": x["index"], "name": x["name"]} for x in bodies], "pair_count": len(records),
        "pair_errors": sum("error" in x for x in records),
        "decision_counts": dict(Counter(x["decision"]["status"] for x in records)),
        "category_counts": dict(Counter(x["decision"]["category"] for x in records)),
        "positive_volume_overlap_pairs": sum(x.get("fact", {}).get("intersection_volume_mm3", 0) > 0 for x in records),
        "records": records,
        "limitations": ["STEP has no confirmed cavity", "pipe-like exterior does not prove engineering pipe intent", "uncertain pairs remain NOT_EVALUATED"]}
    (out / "spatial_box_analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "records"}, ensure_ascii=False))

if __name__ == "__main__": main()
