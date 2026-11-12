"""One-command, read-only CATIA V5 inspection and Word-report workflow."""
from __future__ import annotations

import argparse
import atexit
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "project") not in sys.path:
    sys.path.insert(0, str(ROOT / "project"))
PYTHON = ROOT / "runtime" / "python.exe"
VALIDATION = ROOT / "validation"
OUTPUT = ROOT / "project" / "output" / "runs"
RUN_ID = "RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
RUN_DIR = OUTPUT / RUN_ID
RESULT = RUN_DIR / "check.json"
DOCX = RUN_DIR / "report.docx"
FACE_INVENTORY = RUN_DIR / "face-inventory.json"
STATE = VALIDATION / "last-run.json"
CHECKPOINT_DIR = OUTPUT / "checkpoints" / "active-large-single-part"
DIALOG_LOG = RUN_DIR / "catia-dialogs.jsonl"


def start_dialog_guard() -> subprocess.Popen:
    process = subprocess.Popen(
        [str(PYTHON), str(ROOT / "scripts" / "catia_dialog_guard.py"),
         "--parent-pid", str(os.getpid()), "--log", str(DIALOG_LOG)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    atexit.register(lambda: process.poll() is None and process.terminate())
    return process


def record(stage: str, status: str, detail: str = "") -> None:
    VALIDATION.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({
        "time": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "status": status,
        "detail": detail,
        "result": str(RESULT),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{stage}] {status}: {detail}", flush=True)


def run(stage: str, args: list[str]) -> None:
    record(stage, "RUNNING")
    completed = subprocess.run([str(PYTHON), *args], cwd=ROOT)
    if completed.returncode:
        record(stage, "FAILED", f"exit_code={completed.returncode}")
        raise SystemExit(completed.returncode)
    record(stage, "PASS")


def run_evidence(args: list[str]) -> None:
    """Screenshot evidence is required, but failure must still produce an incomplete Word report."""
    record("CATIA定位截图", "RUNNING")
    completed = subprocess.run([str(PYTHON), *args], cwd=ROOT)
    if completed.returncode == 0:
        record("CATIA定位截图", "PASS")
        return
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    audit = payload.setdefault("audit", {})
    audit["screenshot_required_failure"] = f"exit_code={completed.returncode}"
    budget = payload.setdefault("confidence_budget", {})
    degraded = budget.setdefault("degraded", [])
    message = "必需的CATIA定位截图未生成，报告不得作为完整验收结果"
    if message not in degraded:
        degraded.append(message)
    budget["is_complete"] = False
    RESULT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    record("CATIA定位截图", "PARTIAL", message)


def attach_dialog_audit() -> None:
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    events = []
    if DIALOG_LOG.is_file():
        for line in DIALOG_LOG.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    payload.setdefault("audit", {})["catia_dialog_guard"] = {
        "log": str(DIALOG_LOG), "event_count": len(events),
        "auto_handled_count": sum(bool(item.get("clicked")) for item in events),
        "blocked_count": sum((item.get("decision") or {}).get("action") == "BLOCK" for item in events),
    }
    RESULT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def update_progress_metrics(metrics: dict, event: dict) -> dict:
    name=str(event.get("stage") or ""); metrics["current_stage"]=name
    if name=="CATIA_BATCH_EXPORT_COMPLETE": metrics.update({"exported_batches":event.get("batch_number"),"last_batch_body_count":event.get("body_count")})
    elif name=="CHECKPOINT_LOADED": metrics["resumed_pairs"]=int(event.get("resumed_pair_count") or 0)
    elif name=="CHECKPOINT_RESUME_PLAN": metrics.update({"total_candidate_pairs":event.get("total_pairs"),"pending_pairs_at_start":event.get("pending_pairs")})
    elif name.endswith("_COMPLETE") and name.startswith("EXACT_PAIR_"):
        metrics["pair_attempts_completed"]=int(metrics.get("pair_attempts_completed",0))+1
        status=event.get("status")
        if status=="TIMEOUT": metrics["pair_timeouts"]=int(metrics.get("pair_timeouts",0))+1
        elif status=="DEFERRED": metrics["pair_deferred_by_budget"]=int(metrics.get("pair_deferred_by_budget",0))+1
        elif status=="ERROR": metrics["pair_errors"]=int(metrics.get("pair_errors",0))+1
        elif status=="COMPLETE": metrics["pair_successes"]=int(metrics.get("pair_successes",0))+1
    elif name=="EXACT_PAIR_RETRY_PLAN": metrics.update({"retry_count":event.get("retry_count"),"retry_timeout_seconds":event.get("retry_timeout_seconds")})
    return metrics

def run_streaming(stage: str, args: list[str]) -> None:
    """Forward tool output while publishing machine-readable progress to last-run.json."""
    record(stage,"RUNNING")
    process=subprocess.Popen([str(PYTHON),*args],cwd=ROOT,stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",bufsize=1)
    latest={}
    for line in process.stdout or ():
        encoding = sys.stdout.encoding or "utf-8"
        print(line.encode(encoding, errors="replace").decode(encoding), end="", flush=True)
        try: event=json.loads(line)
        except json.JSONDecodeError: continue
        update_progress_metrics(latest,event)
        STATE.write_text(json.dumps({"time":datetime.now().isoformat(timespec="seconds"),
          "stage":stage,"status":"RUNNING","detail":event.get("stage",""),"progress":latest,
          "result":str(RESULT),"checkpoint_directory":str(CHECKPOINT_DIR)},ensure_ascii=False,indent=2),encoding="utf-8")
    code=process.wait()
    if code:
        record(stage,"FAILED",f"exit_code={code}; 可使用断点继续")
        raise SystemExit(code)
    resume=json.loads(RESULT.read_text(encoding="utf-8")).get("resume_status") or {}
    status="PARTIAL" if resume.get("needs_resume") else "PASS"
    record(stage,status,f"完成{resume.get('completed_pairs',0)}/{resume.get('total_candidate_pairs',0)}；断点复用{resume.get('resumed_pairs',0)}；待处理{resume.get('pending_pairs',0)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, default=ROOT / "project" / "config" / "rules-active.json")
    parser.add_argument("--skip-tubing", action="store_true")
    parser.add_argument("--geometry-source", type=Path,
                        help="STEP/IGES源文件，用于哑模型精确B-Rep、拓扑和管路几何检查")
    parser.add_argument("--large-single-part-source", type=Path,
                        help="大型多Body单CATPart对应的STEP/IGES源文件；跳过组件级DMU，执行OCCT精确内部检查")
    parser.add_argument("--large-single-part-active", action="store_true",
                        help="将当前CATPart按Body临时分批导出STEP，执行全局精确检查后自动清理")
    parser.add_argument("--large-single-part-batch-size",type=int,
                        help="活动大型CATPart每批Body数；默认读取规则配置")
    parser.add_argument("--large-single-part-time-budget-minutes",type=float,
                        help="精确候选本次运行时间预算；到时保存部分结果和断点")
    parser.add_argument("--large-single-part-face-body-indices",type=int,nargs="+",
                        help="逐Body提取精确Face并执行开孔/圆柱检查；指定Body索引")
    parser.add_argument("--large-single-part-face-auto",action="store_true",
                        help="根据高风险穿模/接触结果自动选择Body做精确Face与开孔分析")
    parser.add_argument("--large-single-part-face-max-bodies",type=int,default=20,
                        help="自动Face分析最多选择的Body数，默认20")
    parser.add_argument("--opening-interface-facts", type=Path,
                        help="预提取的CATIA SPA/OCCT开孔与圆柱解析事实JSON")
    args = parser.parse_args()
    RUN_DIR.mkdir(parents=True, exist_ok=False)
    start_dialog_guard()
    if args.large_single_part_active and args.large_single_part_source:
        parser.error("--large-single-part-active and --large-single-part-source are mutually exclusive")
    if args.large_single_part_face_auto and args.large_single_part_face_body_indices:
        parser.error("automatic and explicit Face Body selection are mutually exclusive")
    if args.large_single_part_active:
        run_streaming("当前大型单CATPart分批精确检查", [
            str(ROOT / "project" / "tools" / "inspect_active_large_single_part_batched.py"),
            "--rules", str(args.rules), "--output", str(RESULT), "--checkpoint-directory",str(CHECKPOINT_DIR),
            *(["--batch-size",str(args.large_single_part_batch_size)] if args.large_single_part_batch_size else []),
            *(["--run-budget",str(args.large_single_part_time_budget_minutes*60),"--timeout",str(args.large_single_part_time_budget_minutes*60+120)] if args.large_single_part_time_budget_minutes else [])])
        face_indices=args.large_single_part_face_body_indices
        selection={"method":"EXPLICIT_BODY_INDICES","body_indices":face_indices or [],
                   "selected_count":len(face_indices or []),"truncated":False}
        if args.large_single_part_face_auto:
            from catia_checker.face_candidates import select_face_body_indices
            selection=select_face_body_indices(json.loads(RESULT.read_text(encoding="utf-8")),args.large_single_part_face_max_bodies)
            face_indices=selection["body_indices"]
            record("自动选择Face分析Body","PARTIAL" if selection["truncated"] else "PASS",
                   f"已选择{selection['selected_count']}/{selection['candidate_body_count']}个高风险Body：{face_indices}")
        if face_indices:
            report=json.loads(RESULT.read_text(encoding="utf-8")); report.setdefault("source",{})["face_body_selection"]=selection
            RESULT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            run("逐Body精确Face清单", [
                str(ROOT / "project" / "tools" / "extract_active_body_face_inventory.py"),
                "--output", str(FACE_INVENTORY), "--body-indices",
                *[str(x) for x in face_indices],
            ])
            run("开孔与圆柱精确分析并入主报告", [
                str(ROOT / "project" / "tools" / "augment_report_with_opening_inventory.py"),
                str(RESULT), str(FACE_INVENTORY), "--rules", str(args.rules),
            ])
        run_evidence([str(ROOT / "scripts" / "capture_finding_evidence.py"), str(RESULT)])
        attach_dialog_audit()
        run("Word报告生成", [str(ROOT / "project" / "tools" / "generate_check_report.py"),
                            str(RESULT), "--docx", str(DOCX)])
        final_report=json.loads(RESULT.read_text(encoding="utf-8")); resume=(final_report.get("resume_status") or {})
        incomplete=resume.get("needs_resume") or final_report.get("confidence_budget",{}).get("is_complete") is False
        record("完成", "PARTIAL" if incomplete else "PASS",
               f"本次独立运行目录：{RUN_DIR}；待处理候选={resume.get('pending_pairs',0)}")
        return 0
    if args.large_single_part_source:
        run("大型单CATPart精确检查", [
            str(ROOT / "project" / "tools" / "inspect_large_single_part_exact.py"),
            str(args.large_single_part_source), "--rules", str(args.rules),
            "--output", str(RESULT)])
        run_evidence([str(ROOT / "scripts" / "capture_finding_evidence.py"), str(RESULT),
                      "--source-file", str(args.large_single_part_source)])
        attach_dialog_audit()
        run("Word报告生成", [str(ROOT / "project" / "tools" / "generate_check_report.py"),
                            str(RESULT), "--docx", str(DOCX)])
        final_report=json.loads(RESULT.read_text(encoding="utf-8"))
        incomplete=final_report.get("confidence_budget",{}).get("is_complete") is False
        record("完成", "PARTIAL" if incomplete else "PASS", f"本次独立运行目录：{RUN_DIR}")
        return 0
    run("CATIA连接与版本检查", [str(ROOT / "scripts" / "self_check.py"), "--catia"])
    run("CATIA DMU全装配扫描", [
        str(ROOT / "project" / "tools" / "audit_all_component_clashes.py"),
        "--output", str(RESULT), "--rules", str(args.rules),
        *(["--geometry-source", str(args.geometry_source)] if args.geometry_source else []),
        *(["--opening-interface-facts", str(args.opening_interface_facts)]
          if args.opening_interface_facts else []),
        *(["--skip-tubing"] if args.skip_tubing else []),
    ])
    run_evidence([
        str(ROOT / "scripts" / "capture_finding_evidence.py"), str(RESULT),
    ])
    evidence_state = json.loads(RESULT.read_text(encoding="utf-8")).get("audit", {})
    missing = evidence_state.get("screenshot_evidence_missing") or []
    if missing:
        record("截图定位与红框标注", "PARTIAL",
               f"已保留有效截图；{len(missing)}项/视角因数量上限或定位失败未生成，详见check.json audit")
    attach_dialog_audit()
    run("Word报告生成", [
        str(ROOT / "project" / "tools" / "generate_check_report.py"),
        str(RESULT), "--docx", str(DOCX),
    ])
    final_report=json.loads(RESULT.read_text(encoding="utf-8"))
    incomplete=final_report.get("confidence_budget",{}).get("is_complete") is False
    record("完成", "PARTIAL" if incomplete else "PASS", f"本次独立运行目录：{RUN_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
