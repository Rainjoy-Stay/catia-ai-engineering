"""Add exact opening-interface findings from a traceable face inventory to a report."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path: sys.path.insert(0,str(PROJECT))
from catia_checker.opening_interfaces import discover_opening_interface_bundle,record_auto_discovery_coverage

def augment(report:dict,inventory:dict,rules:dict)->dict:
    discovery=discover_opening_interface_bundle(inventory,source="OCCT_BREP",rules=rules); report["opening_interface_auto_discovery"]=discovery
    if discovery["analysis_executed"]:
        bundle=discovery["analysis"]; report["opening_interface_analysis"]=bundle; existing={x.get("issue_id") for x in report.get("findings",[])}
        for finding in bundle["findings"]:
            if finding.get("issue_id") not in existing: report.setdefault("findings",[]).append(finding)
    report.setdefault("confidence_budget",{}).setdefault("checked",[]); report["confidence_budget"].setdefault("not_checked",[]); record_auto_discovery_coverage(report,discovery,authority="逐Body OCCT精确Face清单")
    if not inventory.get("coverage_complete"):
        report["confidence_budget"].setdefault("degraded",[]).append("Face/开孔检查仅覆盖指定Body子集"); report["confidence_budget"]["is_complete"]=False
    counts={key:0 for key in ("PASS","WARN","FAIL","NOT_EVALUATED","EXEMPTED","ERROR")}
    for finding in report.get("findings",[]):
        status=str(finding.get("status") or "NOT_EVALUATED"); counts[status]=counts.get(status,0)+1
    report["counts"]=counts; report.setdefault("source",{})["active_body_face_inventory"]={"face_count":inventory.get("face_count",0),"body_count":inventory.get("body_count",0),"coverage_complete":inventory.get("coverage_complete",False),"geometry_authority":inventory.get("geometry_authority"),"mesh_used":False}; return report

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("report",type=Path); parser.add_argument("inventory",type=Path); parser.add_argument("--rules",type=Path,required=True); args=parser.parse_args()
    report=json.loads(args.report.read_text(encoding="utf-8")); inventory=json.loads(args.inventory.read_text(encoding="utf-8")); rules=json.loads(args.rules.read_text(encoding="utf-8")); augment(report,inventory,rules); args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); print(args.report); return 0
if __name__=="__main__": raise SystemExit(main())
