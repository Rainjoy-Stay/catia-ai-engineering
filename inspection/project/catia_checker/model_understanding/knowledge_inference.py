"""Knowledge-first semantic inference for scarce engine models."""
from __future__ import annotations
from collections import Counter, defaultdict
import json, re
from pathlib import Path
from typing import Any, Iterable, Mapping

KB_VERSION = "engine-knowledge-base.v1"

def _norm(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").casefold())

def _values(value: Any) -> list[str]:
    if value is None: return []
    return [str(v) for v in value] if isinstance(value, (list, tuple, set)) else [str(value)]

def compile_knowledge_base(config: Mapping[str, Any], cases: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    systems = {}
    for name, spec in (config.get("systems") or {}).items():
        systems[str(name).upper()] = {key: sorted({_norm(v) for v in values if _norm(v)}) for key, values in {
            "aliases": [name, *spec.get("aliases", [])], "line_prefixes": spec.get("line_prefixes", []),
            "equipment_keywords": spec.get("equipment_keywords", []), "port_keywords": spec.get("port_keywords", []),
            "specification_keywords": spec.get("specification_keywords", [])}.items()}
    index, library = defaultdict(list), []
    for case in cases:
        f, labels = case.get("features") or {}, case.get("labels") or {}
        entry = {"object_id": str(case.get("object_id", "")), "part_number": str(f.get("part_number", "")),
                 "object_type": str(labels.get("object_type", "UNKNOWN")).upper(),
                 "system_type": str(labels.get("system_type", "UNKNOWN")).upper(),
                 "label_source": str(case.get("label_source", "")), "source_revision": str(case.get("source_revision", ""))}
        library.append(entry)
        if _norm(entry["part_number"]): index[_norm(entry["part_number"])].append(entry)
    return {"kb_version": KB_VERSION, "systems": systems, "part_number_index": dict(index),
            "case_library": library, "policy": {"minimum_accept_score": 80, "minimum_margin": 25,
            "geometry_cannot_establish_system": True, "graph_propagation_requires_fluid_continuity": True}}

def infer_object(kb: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    f, scores, evidence, object_votes = record.get("features") or {}, Counter(), defaultdict(list), Counter()
    def add(system, points, source, detail):
        scores[system] += points; evidence[system].append({"source": source, "score": points, "detail": detail})
    pn = _norm(f.get("part_number"))
    for case in (kb.get("part_number_index") or {}).get(pn, []) if pn else []:
        if case["system_type"] != "UNKNOWN": add(case["system_type"], 120, "PART_NUMBER_EXACT", case["object_id"])
        if case["object_type"] != "UNKNOWN": object_votes[case["object_type"]] += 120
    normalized = {field: [_norm(v) for v in _values(f.get(field))] for field in
                  ("system_tag", "line_id", "connected_equipment", "connected_port_names", "specification")}
    for system, spec in (kb.get("systems") or {}).items():
        if any(a in v for v in normalized["system_tag"] for a in spec["aliases"]): add(system, 110, "SYSTEM_TAG", str(f.get("system_tag")))
        if any(v.startswith(p) for v in normalized["line_id"] for p in spec["line_prefixes"]): add(system, 100, "LINE_ID_PREFIX", str(f.get("line_id")))
        for field, key, points in (("connected_equipment", "equipment_keywords", 45),
                                   ("connected_port_names", "port_keywords", 35),
                                   ("specification", "specification_keywords", 55)):
            hits = {w for v in normalized[field] for w in spec[key] if w in v}
            if hits: add(system, points * min(len(hits), 2), field.upper(), ",".join(sorted(hits)))
    ranked = scores.most_common(); top, top_score = ranked[0] if ranked else ("UNKNOWN", 0)
    second = ranked[1][1] if len(ranked) > 1 else 0
    accepted = top_score >= kb["policy"]["minimum_accept_score"] and top_score-second >= kb["policy"]["minimum_margin"]
    object_type = object_votes.most_common(1)[0][0] if object_votes else str(f.get("geometry_object_type") or "UNKNOWN").upper()
    reason = None if accepted else ("NO_ENTERPRISE_SYSTEM_EVIDENCE" if not ranked else "CONFLICTING_OR_WEAK_EVIDENCE")
    return {"result_version": "engine-knowledge-inference.v1", "object_id": record.get("object_id"),
            "object_type": {"label": object_type, "source": "APPROVED_PART_NUMBER" if object_votes else "GEOMETRY_CANDIDATE"},
            "system_type": {"label": top if accepted else "UNKNOWN", "candidate_label": top, "score": top_score,
            "margin": top_score-second, "status": "ACCEPTED" if accepted else "REVIEW", "evidence": evidence.get(top, []),
            "alternatives": [{"label": k, "score": v} for k, v in ranked[:3]]},
            "requires_human_review": not accepted, "review_reasons": [] if accepted else [reason]}

def propagate_over_graph(results: Iterable[Mapping[str, Any]], edges: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = {str(v["object_id"]): json.loads(json.dumps(v)) for v in results}; graph = defaultdict(set)
    for edge in edges:
        if edge.get("fluid_continuity_proven"):
            a, b = str(edge["source_object_id"]), str(edge["target_object_id"]); graph[a].add(b); graph[b].add(a)
    changed = True
    while changed:
        changed = False
        for oid, item in out.items():
            if item["system_type"]["label"] != "UNKNOWN": continue
            labels = {out[n]["system_type"]["label"] for n in graph[oid] if n in out and out[n]["system_type"]["label"] != "UNKNOWN"}
            if len(labels) == 1:
                label = next(iter(labels)); item["system_type"].update({"label": label, "candidate_label": label,
                    "status": "ACCEPTED_BY_GRAPH", "evidence": [{"source": "PROVEN_FLUID_CONTINUITY", "detail": sorted(graph[oid])}]})
                item["requires_human_review"] = False; item["review_reasons"] = []; changed = True
    return list(out.values())

def save_knowledge_base(kb: Mapping[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
def load_knowledge_base(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if value.get("kb_version") != KB_VERSION: raise ValueError("Unsupported knowledge base")
    return value
