"""Convert native CATIA DMU clash output into stable checker findings."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Mapping

from .models import (
    RESULT_SCHEMA_VERSION, CheckFinding, CheckStatus, ConfidenceBudget,
    Evidence, EvidenceKind, Severity,
)
from .component_relationships import RelationshipDecision


@dataclass(frozen=True)
class DmuResultBundle:
    document: str
    findings: tuple[CheckFinding, ...]
    confidence_budget: ConfidenceBudget
    source: Mapping[str, Any]
    ruleset_id: str

    def to_dict(self) -> dict[str, Any]:
        counts = {status.value: 0 for status in CheckStatus}
        for finding in self.findings:
            counts[finding.status.value] += 1
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "document": self.document,
            "ruleset_id": self.ruleset_id,
            "source": dict(self.source),
            "counts": counts,
            "findings": [finding.to_dict() for finding in self.findings],
            "confidence_budget": self.confidence_budget.to_dict(),
        }


def _stable_issue_id(conflict: Mapping[str, Any]) -> str:
    conflict_type = str(conflict.get("type", "UNKNOWN")).upper()
    pair = sorted((str(conflict.get("first_product", "UNKNOWN")),
                   str(conflict.get("second_product", "UNKNOWN"))))
    digest = hashlib.sha256("|".join((conflict_type, *pair)).encode("utf-8")).hexdigest()[:10].upper()
    return f"DMU-{conflict_type}-{digest}"


def _decision(conflict: Mapping[str, Any], dmu_rules: Mapping[str, Any]) -> tuple[CheckStatus, Severity, str]:
    conflict_type = str(conflict.get("type", "UNKNOWN")).upper()
    rule_status = str(conflict.get("rule_status", "UNFILTERED")).upper()
    relationship = conflict.get("relationship_assessment") or {}
    relationship_decision = str(relationship.get("decision", "")).upper()
    disposition = str((conflict.get("inspection_disposition") or {}).get("disposition", "")).upper()
    if disposition == "INTERFERENCE_FAIL":
        return CheckStatus.FAIL, Severity.S4, "CATIA DMU 检测到实体穿透，检查语义安全门禁止豁免。"
    if disposition == "CONNECTION_CHECK":
        return CheckStatus.PASS, Severity.S1, "组件对通过高置信直接连接检查。"
    if disposition == "SUPPORT_CHECK":
        return CheckStatus.PASS, Severity.S1, "组件对通过高置信支撑关系检查。"
    if disposition == "STANDARD_SPACING":
        return CheckStatus.WARN, Severity.S2, "组件对继续执行普通间距阈值检查。"
    if disposition == "CONSERVATIVE_FALLBACK":
        return CheckStatus.NOT_EVALUATED, Severity.S2, "检查语义证据不足，保持人工复核。"
    if relationship_decision == RelationshipDecision.PASS_NORMAL_CONNECTION.value:
        return CheckStatus.PASS, Severity.S1, "组件对被确认为正常设计连接或合理装配接触。"
    if relationship_decision == RelationshipDecision.REVIEW_REQUIRED.value and conflict_type != "CLASH":
        return CheckStatus.NOT_EVALUATED, Severity.S2, "组件关系证据不足，需人工复核后才能评价间距。"
    # allowed_contact_pairs may exempt CONTACT only. A physical CLASH on the
    # same component pair remains a failure unless a separate approved
    # interference rule is introduced explicitly.
    if (rule_status == "EXEMPTED" and conflict_type == "CONTACT") or conflict_type == "EXEMPTED":
        return CheckStatus.EXEMPTED, Severity.S1, "组件对已由显式豁免规则登记。"
    if conflict_type == "CLASH":
        if bool(dmu_rules.get("clash_is_failure", True)):
            return CheckStatus.FAIL, Severity.S4, "CATIA DMU 检测到实体穿透。"
        return CheckStatus.WARN, Severity.S3, "检测到实体穿透，但当前规则未授权自动判定失败。"
    if conflict_type == "CONTACT":
        if bool(dmu_rules.get("contact_is_failure", False)):
            return CheckStatus.FAIL, Severity.S3, "CATIA DMU 检测到零距离接触。"
        return CheckStatus.WARN, Severity.S2, "零距离接触需要结合接口、夹持或支撑语义复核。"
    if conflict_type == "CLEARANCE":
        return CheckStatus.WARN, Severity.S2, "组件间距小于本次 DMU 扫描阈值。"
    return CheckStatus.ERROR, Severity.S3, f"无法识别 CATIA DMU 冲突类型：{conflict_type}。"


def _title(conflict_type: str) -> str:
    return {"CLASH": "组件实体干涉", "CONTACT": "组件零距离接触",
            "CLEARANCE": "组件间距不足", "EXEMPTED": "组件冲突已豁免"}.get(
        conflict_type, "未知 DMU 冲突")


def convert_dmu_conflict(conflict: Mapping[str, Any], dmu_rules: Mapping[str, Any], *,
                         method: str, clearance_mm: float) -> CheckFinding:
    """Convert one raw DMU conflict without changing its measured value."""
    conflict_type = str(conflict.get("type", "UNKNOWN")).upper()
    status, severity, message = _decision(conflict, dmu_rules)
    first = str(conflict.get("first_product", "UNKNOWN"))
    second = str(conflict.get("second_product", "UNKNOWN"))
    measured = conflict.get("value_mm")
    measured_value = float(measured) if measured is not None else None
    raw_data = dict(conflict)
    raw_data["scan_clearance_mm"] = clearance_mm
    return CheckFinding(
        issue_id=_stable_issue_id(conflict), rule_id=f"DMU.{conflict_type}",
        status=status, severity=severity, title=_title(conflict_type), message=message,
        object_a=first, object_b=second, measured_value=measured_value,
        limit_value=clearance_mm if conflict_type == "CLEARANCE" else 0.0,
        unit="mm" if measured_value is not None else None,
        recommendation=("在 CATIA 中定位该组件对，确认装配意图和允许接触关系；"
                        "若非设计接触，调整布置或几何后重新执行 DMU 扫描。"),
        evidence=(Evidence(kind=EvidenceKind.CATIA_CLASH, source=method,
                           description=str(conflict.get("name", "CATIA DMU conflict")),
                           object_paths=(first, second), data=raw_data),),
        metadata={"first_part_number": conflict.get("first_part_number"),
                  "second_part_number": conflict.get("second_part_number"),
                  "raw_rule_status": conflict.get("rule_status"),
                  "relationship_assessment": conflict.get("relationship_assessment")},
    )


def _missing_context(required_context: Mapping[str, Any]) -> Iterable[str]:
    labels = {"hot_zone_classification": "热区分类",
              "pressure_and_temperature_metadata": "压力和温度元数据",
              "motion_envelopes": "运动包络",
              "support_and_clamp_metadata": "支撑与夹具语义",
              "maintenance_removal_envelopes": "维护拆装包络"}
    for key, label in labels.items():
        if not bool(required_context.get(key, False)):
            yield label


def convert_dmu_scan(raw_scan: Mapping[str, Any], rules: Mapping[str, Any]) -> DmuResultBundle:
    """Convert a complete native Between-All response into a result bundle."""
    dmu_rules = dict(rules.get("dmu_clash", {}))
    method = str(raw_scan.get("method", "CATIA_DMU_SPACE_ANALYSIS"))
    clearance_mm = float(raw_scan.get("clearance_mm", dmu_rules.get("clearance_mm", 0.0)))
    conflicts = raw_scan.get("conflicts", ())
    if not isinstance(conflicts, (list, tuple)):
        raise ValueError("DMU scan conflicts must be a list")
    findings = tuple(convert_dmu_conflict(item, dmu_rules, method=method,
                                          clearance_mm=clearance_mm) for item in conflicts)
    degraded: list[str] = []
    if bool(raw_scan.get("truncated", False)):
        degraded.append("DMU 返回结果达到 max_conflicts 上限，结果已截断")
    if raw_scan.get("cleanup_verified") is not True:
        degraded.append("一次性 DMU 产品清理状态未得到确认")
    assumptions: list[str] = []
    if rules.get("routing", {}).get("threshold_status") == "ASSUMED_PENDING_APPROVAL":
        assumptions.append("试运行阈值尚未完成项目批准，不作为正式符合性依据")
    source_keys = ("root_product", "method", "computation_type", "interference_type",
                   "clearance_mm", "top_level_component_count", "scope_component_count",
                   "raw_conflict_count", "returned_conflict_count", "truncated",
                   "temporary_product_used", "cleanup_verified", "source_document_saved_before",
                   "source_document_saved_after", "source_saved_by_tool",
                   "direct_transient_step_fallback", "accuracy_note")
    return DmuResultBundle(
        document=str(raw_scan.get("document", "UNKNOWN")), findings=findings,
        confidence_budget=ConfidenceBudget(
            checked=("CATIA DMU Between All 全装配干涉/接触/扫描间距",),
            not_checked=tuple(_missing_context(rules.get("required_context", {}))),
            assumptions=tuple(assumptions), degraded=tuple(degraded)),
        source={key: raw_scan.get(key) for key in source_keys},
        ruleset_id=str(rules.get("ruleset_id", "UNKNOWN")),
    )
