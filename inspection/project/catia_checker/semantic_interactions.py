"""Attach engineering-object semantics to exact intersection events."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def assess_solid_interactions(pair_facts: Iterable[Mapping[str, Any]], *,
                              volume_tolerance_mm3: float = 1e-6) -> dict[str, Any]:
    """Turn exact solid-pair facts into conservative PASS/FAIL/REVIEW decisions.

    This layer intentionally does not guess component roles from STEP entity
    ordering. A positive common volume is material interference; a zero-volume
    section stays REVIEW; exact separation passes.
    """
    tolerance = max(0.0, float(volume_tolerance_mm3))
    assessments = []
    counts: dict[str, int] = {}
    for raw in pair_facts:
        fact = dict(raw)
        volume = max(0.0, float(fact.get("intersection_volume_mm3") or 0.0))
        intersects = fact.get("intersects") is True
        if volume > tolerance:
            disposition, category = "FAIL", "MATERIAL_INTERFERENCE"
            reason = "精确公共体积大于容差，确认两个实体发生材料干涉。"
        elif intersects:
            disposition, category = "REVIEW", "ZERO_VOLUME_SECTION"
            reason = "存在精确截交但公共体积为零，需区分接触、共边或薄片异常。"
        else:
            disposition, category = "PASS", "NO_MATERIAL_INTERFERENCE"
            reason = "精确B-Rep确认无公共体积和截交。"
        item = {
            "object_a": str(fact.get("object_a")),
            "object_b": str(fact.get("object_b")),
            "object_a_name": fact.get("object_a_name"),
            "object_b_name": fact.get("object_b_name"),
            "disposition": disposition,
            "error_category": category,
            "minimum_distance_mm": fact.get("minimum_distance_mm"),
            "intersection_volume_mm3": volume,
            "section_edge_count": int(fact.get("section_edge_count") or 0),
            "semantic_reason": reason,
            "exact_brep": fact.get("exact_brep") is True,
            "interface_evidence": (
                "MATERIAL_INTERFERENCE_CONFIRMED" if volume > tolerance else
                "ZERO_VOLUME_SECTION" if intersects else
                "MATERIAL_FREE_SEPARATION_CONFIRMED"),
        }
        assessments.append(item)
        counts[disposition] = counts.get(disposition, 0) + 1
    return {
        "schema_version": "solid-interaction-assessments.v1.0",
        "assessment_count": len(assessments),
        "disposition_counts": counts,
        "volume_tolerance_mm3": tolerance,
        "assessments": assessments,
        "engineering_roles_inferred": False,
        "mesh_used": False,
    }


def enrich_intersection_events(events: Mapping[str, Any], logical: Mapping[str, Any],
                               roles: Mapping[str, Any],
                               pair_facts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    face_map = dict(logical.get("face_to_component") or {})
    role_map = {item["logical_component_id"]: item for item in roles.get("candidates", [])}
    fact_index = {tuple(sorted((str(item.get("object_a")), str(item.get("object_b"))))): dict(item)
                  for item in pair_facts}
    enriched = []
    counts: dict[str, int] = {}
    for raw_event in events.get("events", []):
        event = dict(raw_event)
        component_ids = sorted({face_map.get(str(face)) for pair in event.get("face_pairs", [])
                                for face in (pair.get("object_a"), pair.get("object_b"))
                                if face_map.get(str(face))})
        role_names = sorted({role_map[item]["engineering_role"] for item in component_ids
                             if item in role_map})
        member_facts = [fact_index.get(tuple(sorted((str(pair.get("object_a")),
                                                     str(pair.get("object_b"))))), {})
                        for pair in event.get("face_pairs", [])]
        same_component = len(component_ids) == 1 and bool(component_ids)
        allowed = any(item.get("allowed_region") is True for item in member_facts)
        penetration = any(item.get("penetration_confirmed") is True for item in member_facts)
        role_set = set(role_names)
        if same_component:
            relation, disposition, category = (
                "INTRA_COMPONENT_SELF_INTERSECTION", "REVIEW", "CONVERSION_OR_TOPOLOGY_ERROR")
            reason = "同一逻辑组件内部发生相交，需检查坏面、重复面或格式转换重构问题。"
        elif {"NOZZLE", "VESSEL_SHELL"}.issubset(role_set):
            relation = "NOZZLE_TO_VESSEL"
            if allowed:
                disposition, category = "PASS", "EXPECTED_INTERFACE"
                reason = "相交位于已验证的接管开孔或允许接口区域。"
            elif penetration:
                disposition, category = "FAIL", "DESIGN_ERROR"
                reason = "接管跨越筒体边界，且不在允许接口区域。"
            else:
                disposition, category = "REVIEW", "INTERFACE_EVIDENCE_REQUIRED"
                reason = "几何符合接管—筒体关系，但尚未找到开孔或允许区域证据。"
        elif role_set.intersection({"PIPE", "PIPE_BEND"}) and "VESSEL_SHELL" in role_set:
            relation = "PIPE_TO_VESSEL"
            if allowed:
                disposition, category = "PASS", "EXPECTED_INTERFACE"
                reason = "管路交互位于已验证允许区域。"
            elif penetration:
                disposition, category = "FAIL", "DESIGN_ERROR"
                reason = "管路被精确确认跨越筒体边界。"
            else:
                disposition, category = "REVIEW", "PENETRATION_EVIDENCE_REQUIRED"
                reason = "发现管路—筒体截交，但缺少跨越方向或实体两侧证据。"
        else:
            relation = "UNEXPECTED_COMPONENT_INTERSECTION"
            disposition, category = "FAIL", "DESIGN_ERROR"
            reason = "不同逻辑组件发生非允许的精确曲面相交。"
        event.update({"logical_component_ids": component_ids,
                      "engineering_roles": role_names,
                      "engineering_relation": relation,
                      "disposition": disposition, "error_category": category,
                      "allowed_region_confirmed": allowed,
                      "penetration_confirmed": penetration,
                      "semantic_reason": reason})
        counts[disposition] = counts.get(disposition, 0) + 1
        enriched.append(event)
    return {"schema_version": "semantic-intersection-events.v1.0",
            "event_count": len(enriched), "disposition_counts": counts,
            "events": enriched,
            "policy": "NO_GLOBAL_RELATIONSHIP_EXEMPTION",
            "face_facts_preserved": True}
