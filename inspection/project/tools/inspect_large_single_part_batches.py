"""Inspect several STEP Body batches as one exact global model."""
from __future__ import annotations
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
PROJECT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(PROJECT))
from catia_checker.large_single_part import build_large_single_part_result,inspect_large_single_part_batches_isolated
from catia_checker.routing_rules import validate_rules
def main()->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("sources",nargs="+",type=Path); p.add_argument("--rules",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--body-mapping",type=Path); p.add_argument("--checkpoint",type=Path); p.add_argument("--run-budget",type=float); p.add_argument("--pair-timeout",type=float); p.add_argument("--pair-retry-timeout",type=float); p.add_argument("--max-pair-retries",type=int); p.add_argument("--workers",type=int); a=p.parse_args()
    rules=json.loads(a.rules.read_text(encoding="utf-8")); validate_rules(rules); progress=lambda e:print(json.dumps(e,ensure_ascii=False),flush=True)
    body_mapping=json.loads(a.body_mapping.read_text(encoding="utf-8")) if a.body_mapping else None
    bundle=inspect_large_single_part_batches_isolated(a.sources,rules=rules,progress=progress,pair_timeout_seconds=a.pair_timeout,pair_retry_timeout_seconds=a.pair_retry_timeout,max_pair_retries=a.max_pair_retries,checkpoint_path=a.checkpoint,run_budget_seconds=a.run_budget,body_mapping=body_mapping,max_pair_workers=a.workers)
    payload=build_large_single_part_result(bundle,document="ACTIVE_CATPART_BATCHES",rules=rules,run_id=f"SINGLEPART-BATCH-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}",generated_at=datetime.now(timezone.utc).isoformat())
    payload["source"]["batch_count"]=len(a.sources); payload["source"]["computation_type"]="BATCHED_STEP_GLOBAL_AABB_EXACT_CANDIDATES"
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(a.output); return 0
if __name__=="__main__": raise SystemExit(main())
