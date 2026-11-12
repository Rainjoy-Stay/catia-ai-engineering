"""Export the active CATPart temporarily and inspect it in an isolated process."""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, tempfile, threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

PROJECT = Path(__file__).resolve().parents[1]; ROOT = PROJECT.parent
for value in (str(PROJECT), str(ROOT / "scripts")):
    if value not in sys.path: sys.path.insert(0, value)
from catia_checker.routing_rules import validate_rules
from r18_connection import R18Connection

def run_child_command(command: list[str], result: Path, timeout: float, *,
                      popen_factory: Callable[..., Any] = subprocess.Popen,
                      progress: Callable[[dict[str, Any]], None] | None = None) -> None:
    process = popen_factory(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    def forward() -> None:
        for line in process.stdout or ():
            try: event = json.loads(line)
            except json.JSONDecodeError: event = {"stage": "CHILD_MESSAGE", "message": line}
            if progress: progress(event)
    reader = threading.Thread(target=forward, daemon=True); reader.start()
    try:
        try: process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(); reader.join(timeout=1)
            raise TimeoutError(f"OCCT exact inspection exceeded {timeout:g} seconds")
        reader.join(timeout=1)
        if process.returncode: raise RuntimeError(f"OCCT child exited with code {process.returncode}")
        if not result.is_file(): raise RuntimeError("OCCT child produced no result file")
    finally:
        if process.poll() is None: process.kill(); process.wait()

def emit_progress(event: dict[str, Any]) -> None:
    """Emit console-safe JSON even when Windows stdout still uses GBK."""
    print(json.dumps(event, ensure_ascii=True), flush=True)

def run_exact_child(source: Path, result: Path, rules: Path, timeout: float, *,
                    popen_factory: Callable[..., Any] = subprocess.Popen,
                    progress: Callable[[dict[str, Any]], None] | None = None) -> None:
    command = [sys.executable, str(PROJECT/"tools"/"inspect_large_single_part_exact.py"),
               str(source), "--rules", str(rules), "--output", str(result)]
    run_child_command(command,result,timeout,popen_factory=popen_factory,progress=progress)

def failure_payload(document: str, rules: dict[str, Any], error: Exception, before: tuple[bool,int],
                    after: tuple[bool,int], deleted: bool) -> dict[str, Any]:
    return {"schema_version":"1.1.0", "document":document, "ruleset_id":rules["ruleset_id"],
      "run_id":f"SINGLEPART-ERROR-{uuid4().hex[:8]}", "generated_at":datetime.now(timezone.utc).isoformat(),
      "source":{"method":"OCCT_EXACT_BREP_LARGE_SINGLE_PART", "temporary_step_export":True,
        "source_document_saved_before":before[0], "source_document_saved_after":after[0],
        "source_body_count_before":before[1], "source_body_count_after":after[1],
        "source_saved_by_tool":False, "cleanup_verified":deleted},
      "counts":{"PASS":0,"WARN":0,"FAIL":0,"NOT_EVALUATED":0,"EXEMPTED":0,"ERROR":1}, "findings":[],
      "confidence_budget":{"checked":[],"not_checked":["大型单CATPart内部Solid精确检查未完成"],
        "assumptions":[],"degraded":[str(error)],"is_complete":False},
      "audit":{"geometry_authority":"OCCT exact B-Rep","llm_role":"none","source_model_modified":False,
        "exceptions":[str(error)],"mesh_used":False,"temporary_file_deleted":deleted}}

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--rules",type=Path,default=PROJECT/"config"/"rules-active.json"); parser.add_argument("--output",type=Path,required=True); parser.add_argument("--timeout",type=float,help="One-run timeout override in seconds"); args=parser.parse_args()
    rules=json.loads(args.rules.read_text(encoding="utf-8")); validate_rules(rules)
    timeout=args.timeout if args.timeout is not None else float((rules.get("large_single_part") or {}).get("max_runtime_seconds",600))
    if timeout <= 0: raise ValueError("timeout must be greater than zero")
    connection=R18Connection(); connection.connect(); doc=connection.active_document
    if not str(doc.Name).lower().endswith(".catpart"): raise RuntimeError("Active document must be a CATPart")
    before=(bool(doc.Saved),int(doc.Part.Bodies.Count)); after=before; payload=None; error=None
    temp=Path(tempfile.mkdtemp(prefix="catia-singlepart-")); child=temp/"exact-result.json"
    try:
        step=temp/"active_part.stp"; print(json.dumps({"stage":"CATIA_EXPORT_START"}),flush=True); doc.ExportData(str(step),"stp")
        if not step.is_file() or step.stat().st_size<=0: raise RuntimeError("CATIA temporary STEP export produced no usable file")
        print(json.dumps({"stage":"CATIA_EXPORT_COMPLETE","size_bytes":step.stat().st_size}),flush=True)
        run_exact_child(step,child,args.rules.resolve(),timeout,progress=emit_progress)
        payload=json.loads(child.read_text(encoding="utf-8"))
    except Exception as exc: error=exc
    finally:
        after=(bool(doc.Saved),int(doc.Part.Bodies.Count)); shutil.rmtree(temp,ignore_errors=True)
    deleted=not temp.exists()
    if after!=before: error=RuntimeError("Source CATPart state changed during temporary export"); payload=None
    if error is not None or payload is None: payload=failure_payload(str(doc.Name),rules,error or RuntimeError("Unknown failure"),before,after,deleted)
    else:
        solids=int(payload["large_single_part_analysis"]["analysis"]["solid_count"])
        payload["document"]=str(doc.Name); payload["source"].update({"temporary_step_export":True,"source_document_saved_before":before[0],"source_document_saved_after":after[0],"source_body_count_before":before[1],"source_body_count_after":after[1],"exported_solid_count":solids,"cleanup_verified":deleted})
        payload["audit"]["temporary_export"]={"format":"STEP","temporary_file_deleted":deleted,"source_modified":False}
        if solids!=before[1]: payload["confidence_budget"]["degraded"].append(f"CATIA Body数量={before[1]}，STEP Solid数量={solids}，导出完整性需复核"); payload["confidence_budget"]["is_complete"]=False
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(args.output)
    return 1 if error is not None else 0
if __name__=="__main__": raise SystemExit(main())
