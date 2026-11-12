"""Component-pair relationship reasoning between geometry and clearance rules.

CATIA remains authoritative for distances and interference.  This module only
decides whether a close pair is a credible normal connection, needs ordinary
clearance evaluation, or lacks enough evidence for automatic disposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class RelationshipDecision(str, Enum):
    PASS_NORMAL_CONNECTION = "PASS_NORMAL_CONNECTION"
    CHECK_CLEARANCE = "CHECK_CLEARANCE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class RelationshipAssessment:
    decision: RelationshipDecision
    confidence: float
    reason: str
    key_evidence: tuple[str, ...] = ()
    source: str = "CONSERVATIVE_FALLBACK"
    relation_type: str = "UNKNOWN"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("relationship confidence must be between 0 and 1")
        if not self.reason.strip():
            raise ValueError("relationship reason must not be empty")
        object.__setattr__(self, "key_evidence", tuple(self.key_evidence))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "confidence": round(float(self.confidence), 6),
            "reason": self.reason,
            "key_evidence": list(self.key_evidence),
            "source": self.source,
            "relation_type": self.relation_type,
            "metadata": dict(self.metadata),
        }


def build_pair_context(conflict: Mapping[str, Any], *, model_type: str,
                       component_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a fact-only, serializable input for deterministic or AI judgment."""
    first = str(conflict.get("first_product", "UNKNOWN"))
    second = str(conflict.get("second_product", "UNKNOWN"))
    components = dict(component_context or {})
    return {
        "pair_id": "|".join(sorted((first, second))),
        "model_type": model_type.upper(),
        "component_a": components.get(first, {
            "name": first, "part_number": conflict.get("first_part_number")}),
        "component_b": components.get(second, {
            "name": second, "part_number": conflict.get("second_part_number")}),
        "geometric_relation": {
            "dmu_type": str(conflict.get("type", "UNKNOWN")).upper(),
            "signed_surface_clearance_mm": conflict.get("value_mm"),
            "interference_depth_mm": conflict.get("interference_depth_mm", 0.0),
            "closest_points_mm": conflict.get("closest_points_mm"),
            "contact_region": conflict.get("contact_region"),
            "interface_alignment": conflict.get("interface_alignment"),
            "axis_relation": conflict.get("axis_relation"),
            "topology_continuity": conflict.get("topology_continuity"),
        },
        "assembly_relation": conflict.get("assembly_relation", {}),
        "neighborhood": conflict.get("neighborhood", {}),
        "limitations": list(conflict.get("relationship_limitations", ())),
    }


def conservative_assessment(context: Mapping[str, Any]) -> RelationshipAssessment:
    """Fail closed when no qualified semantic judge is available."""
    geometry = context.get("geometric_relation", {})
    conflict_type = str(geometry.get("dmu_type", "UNKNOWN")).upper()
    model_type = str(context.get("model_type", "UNKNOWN")).upper()
    assembly = context.get("assembly_relation", {})
    if conflict_type == "CLASH":
        return RelationshipAssessment(
            RelationshipDecision.REVIEW_REQUIRED, 1.0,
            "检测到实体穿透；在设计关系得到可靠证明前禁止自动按正常连接放行。",
            ("CATIA DMU=CLASH",), relation_type="POSSIBLE_INTERFERENCE")
    if (conflict_type == "CONTACT" and
            assembly.get("relationship_type") == "DIRECT_INTERFACE" and
            assembly.get("evidence") == "COINCIDENT_CIRCULAR_INTERFACE" and
            assembly.get("unique_interface_match") is True):
        return RelationshipAssessment(
            RelationshipDecision.PASS_NORMAL_CONNECTION, 0.95,
            "接触组件对具有唯一的端点圆心重合及接口法向一致证据，按正常直接连接处理。",
            ("CATIA DMU=CONTACT", "唯一重合圆形接口"),
            source="DETERMINISTIC_GEOMETRY_V0.4", relation_type="DIRECT_INTERFACE",
            metadata={"inspection_profile": assembly.get("inspection_profile", "GENERIC_DIRECT_INTERFACE"),
                      "endpoint_object_types": assembly.get("endpoint_object_types", [])})
    if (conflict_type == "CONTACT" and assembly.get("relationship_type") == "SUPPORTED" and
            assembly.get("evidence") == "COAXIAL_RADIUS_MATCHED_MIDSPAN_ENCLOSURE" and
            float(assembly.get("confidence", 0.0)) >= 0.85):
        return RelationshipAssessment(
            RelationshipDecision.PASS_NORMAL_CONNECTION, 0.95,
            "管路中部存在同轴、半径匹配的包覆支撑，当前零距离接触符合卡箍支撑关系。",
            ("CATIA DMU=CONTACT", "同轴半径匹配的中部包覆", "两路确定性证据交叉验证"),
            source="DETERMINISTIC_GEOMETRY_V0.5", relation_type="SUPPORTED")
    if conflict_type == "CLEARANCE":
        return RelationshipAssessment(
            RelationshipDecision.CHECK_CLEARANCE, 0.95,
            "当前几何为正间隙，未取得足以证明设计连接的接口或装配证据，按普通净距规则评价。",
            ("CATIA DMU=CLEARANCE",), relation_type="NO_PROVEN_CONNECTION")
    suffix = "；STEP缺少原生装配语义" if model_type in {"STEP", "STP"} else ""
    return RelationshipAssessment(
        RelationshipDecision.REVIEW_REQUIRED, 0.25,
        f"零距离接触可能是正常连接，也可能是异常接触，现有证据不足{suffix}。",
        (f"CATIA DMU={conflict_type}",), relation_type="AMBIGUOUS_CONTACT")


def validate_ai_assessment(context: Mapping[str, Any], value: Mapping[str, Any], *,
                           minimum_pass_confidence: float = 0.85) -> RelationshipAssessment:
    """Validate an AI decision and enforce non-bypassable safety gates."""
    try:
        decision = RelationshipDecision(str(value["decision"]).upper())
        confidence = float(value["confidence"])
        reason = str(value["reason"])
    except (KeyError, TypeError, ValueError):
        return conservative_assessment(context)
    evidence = tuple(str(item) for item in value.get("key_evidence", ()))
    conflict_type = str(context.get("geometric_relation", {}).get("dmu_type", "UNKNOWN")).upper()
    if decision is RelationshipDecision.PASS_NORMAL_CONNECTION:
        if conflict_type == "CLASH" or confidence < minimum_pass_confidence or not evidence:
            return RelationshipAssessment(
                RelationshipDecision.REVIEW_REQUIRED, min(max(confidence, 0.0), 1.0),
                "AI建议正常连接，但穿透安全门、置信度或可追溯证据不满足自动放行条件。",
                evidence, source="AI_VALIDATED", relation_type=str(value.get("relation_type", "UNKNOWN")))
    declared_source = str(value.get("source", ""))
    source = (declared_source if declared_source.startswith("DETERMINISTIC_") else "AI_VALIDATED")
    return RelationshipAssessment(
        decision, confidence, reason, evidence, source=source,
        relation_type=str(value.get("relation_type", "UNKNOWN")),
        metadata={"raw_ai_metadata": value.get("metadata", {})})


def assess_pairs(contexts: Iterable[Mapping[str, Any]], judge: Any | None = None, *,
                 minimum_pass_confidence: float = 0.85) -> list[RelationshipAssessment]:
    items = list(contexts)
    if judge is None:
        return [conservative_assessment(item) for item in items]
    try:
        raw = judge(items)
        if not isinstance(raw, list) or len(raw) != len(items):
            raise ValueError("relationship judge returned an invalid result count")
        return [validate_ai_assessment(context, value,
                    minimum_pass_confidence=minimum_pass_confidence)
                for context, value in zip(items, raw)]
    except Exception:
        return [conservative_assessment(item) for item in items]
