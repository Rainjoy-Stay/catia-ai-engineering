"""Export active CATPart Bodies in temporary batches and inspect globally."""
from __future__ import annotations
import argparse,hashlib,json,shutil,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]; ROOT=PROJECT.parent
for value in (str(PROJECT),str(ROOT/"scripts"),str(PROJECT/"tools")): sys.path.insert(0,value)
from catia_checker.catia_body_batches import export_body_batches
from catia_checker.routing_rules import validate_rules
from inspect_active_large_single_part import emit_progress,failure_payload,run_child_command
from r18_connection import R18Connection

def main()->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--rules",type=Path,default=PROJECT/"config"/"rules-active.json"); p.add_argument("--output",type=Path,required=True); p.add_argument("--checkpoint",type=Path); p.add_argument("--checkpoint-directory",type=Path); p.add_argument("--batch-size",type=int); p.add_argument("--timeout",type=float); p.add_argument("--run-budget",type=float); p.add_argument("--pair-timeout",type=float); p.add_argument("--pair-retry-timeout",type=float); p.add_argument("--max-pair-retries",type=int); p.add_argument("--body-indices",type=int,nargs="+",help="Acceptance subset; omission checks all Bodies"); p.add_argument("--workers",type=int); a=p.parse_args()
    rules=json.loads(a.rules.read_text(encoding="utf-8")); validate_rules(rules); cfg=rules.get("large_single_part") or {}; size=a.batch_size or int(cfg.get("body_batch_size",40)); timeout=a.timeout or float(cfg.get("max_runtime_seconds",600))
    c=R18Connection(); c.connect(); doc=c.active_document
    if not str(doc.Name).lower().endswith(".catpart"): raise RuntimeError("Active document must be a CATPart")
    before=(bool(doc.Saved),int(doc.Part.Bodies.Count)); after=before; temp=Path(tempfile.mkdtemp(prefix="catia-body-batches-")); child=temp/"batched-result.json"; payload=None; error=None; audit=None
    emit=emit_progress
    try:
        audit=export_body_batches(c.app,doc,temp,batch_size=size,body_indices=a.body_indices,progress=emit)
        mapping_file=temp/"body-mapping.json"; mapping_file.write_text(json.dumps(audit["body_mapping"],ensure_ascii=False),encoding="utf-8")
        identity=str(getattr(doc,"FullName","") or doc.Name); key=hashlib.sha256(identity.casefold().encode("utf-8")).hexdigest()[:16]
        checkpoint=(a.checkpoint or ((a.checkpoint_directory/f"{key}.checkpoint.json") if a.checkpoint_directory else a.output.with_suffix(".checkpoint.json"))).resolve()
        command=[sys.executable,str(PROJECT/"tools"/"inspect_large_single_part_batches.py"),*[str(x) for x in audit["batch_files"]],"--rules",str(a.rules.resolve()),"--output",str(child),"--body-mapping",str(mapping_file),"--checkpoint",str(checkpoint),*(["--run-budget",str(a.run_budget)] if a.run_budget else []),*(["--pair-timeout",str(a.pair_timeout)] if a.pair_timeout else []),*(["--pair-retry-timeout",str(a.pair_retry_timeout)] if a.pair_retry_timeout else []),*(["--max-pair-retries",str(a.max_pair_retries)] if a.max_pair_retries is not None else []),*(["--workers",str(a.workers)] if a.workers is not None else [])]
        run_child_command(command,child,timeout,progress=emit); payload=json.loads(child.read_text(encoding="utf-8"))
    except Exception as exc: error=exc
    finally:
        after=(bool(doc.Saved),int(doc.Part.Bodies.Count))
        # Keep completed exports and their receipts on failure for verified recovery.
        if error is None and payload is not None: shutil.rmtree(temp,ignore_errors=True)
        else: emit({'stage':'CATIA_EXPORT_CACHE_RETAINED','directory':str(temp),'reuse_requires_source_verification':True})
    deleted=not temp.exists()
    if after!=before: error=RuntimeError("Source CATPart state changed during batched inspection"); payload=None
    if error is not None or payload is None: payload=failure_payload(str(doc.Name),rules,error or RuntimeError("Unknown failure"),before,after,deleted)
    else:
        payload["document"]=str(doc.Name); payload["source"].update({"temporary_step_export":True,"batched_export":True,"batch_size":size,"batch_count":len(audit["batch_files"]),"source_document_saved_before":before[0],"source_document_saved_after":after[0],"source_body_count_before":before[1],"source_body_count_after":after[1],"cleanup_verified":deleted}); payload["audit"]["temporary_export"]={"format":"STEP_BATCHES","temporary_file_deleted":deleted,"source_modified":False,"body_mapping_count":len(audit["body_mapping"])}
        if not audit["full_source_coverage"]: payload["confidence_budget"]["degraded"].append(f"验收子集仅覆盖{audit['exported_body_count']}/{before[1]}个Body"); payload["confidence_budget"]["is_complete"]=False; payload["source"]["acceptance_subset"]=True
    if not deleted: payload.setdefault('audit',{})['retained_export_directory']=str(temp)
    if audit:
        payload.setdefault('audit',{})['surface_export']={key:audit.get(key) for key in ('geometrical_sets_included','geometrical_set_element_count','surface_export_errors')}
        if audit.get('surface_export_errors'):
            payload['confidence_budget']['is_complete']=False
            payload['confidence_budget']['not_checked'].append('部分几何图形集导出失败；详见 audit.surface_export')
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(a.output); return 1 if error else 0
if __name__=="__main__": raise SystemExit(main())
