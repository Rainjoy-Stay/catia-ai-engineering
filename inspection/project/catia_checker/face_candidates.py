"""Choose a bounded, deterministic Body subset for expensive exact Face analysis."""
from __future__ import annotations
from typing import Any

PRIORITY={"FAIL":0,"ERROR":1,"WARN":2,"NOT_EVALUATED":3,"REVIEW":3}

def select_face_body_indices(report:dict[str,Any],max_bodies:int=20)->dict[str,Any]:
    if max_bodies<1: raise ValueError("max_bodies must be positive")
    ranked=sorted((x for x in report.get("findings",[]) if str(x.get("status")) in PRIORITY),key=lambda x:(PRIORITY[str(x.get("status"))],str(x.get("issue_id") or "")))
    selected=[]; sources={}
    for finding in ranked:
        metadata=finding.get("metadata") or {}
        for side in ("a","b"):
            record=metadata.get(f"source_body_{side}")
            if not isinstance(record,dict): continue
            index=record.get("source_body_index")
            if not isinstance(index,int) or index<1: continue
            if index not in selected:
                if len(selected)>=max_bodies: continue
                selected.append(index); sources[index]=[]
            if index in sources: sources[index].append(str(finding.get("issue_id") or ""))
    total_candidates=len({int(record["source_body_index"])
        for finding in ranked for record in [(finding.get("metadata") or {}).get("source_body_a"),(finding.get("metadata") or {}).get("source_body_b")]
        if isinstance(record,dict) and isinstance(record.get("source_body_index"),int) and record["source_body_index"]>0})
    return {"body_indices":selected,"selected_count":len(selected),"candidate_body_count":total_candidates,"truncated":total_candidates>len(selected),"max_bodies":max_bodies,"source_issue_ids":sources,"method":"RISK_FINDING_SOURCE_BODY_PRIORITY"}
