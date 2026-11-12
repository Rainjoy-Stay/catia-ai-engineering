"""Main-project adapter for the standalone opening-interface engine."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from standalone.opening_interface_analysis import (
    adapt_exact_geometry, analyze_opening_network, discover_adapter_payload,
)
from .models import CheckFinding, CheckStatus, Evidence, EvidenceKind, Severity


CODE_LABELS = {
    "AXIS_ANGLE_OUT_OF_TOLERANCE": "接管轴线与开孔法向夹角超差",
    "AXIS_OFFSET_OUT_OF_TOLERANCE": "接管轴线与开孔中心偏差超差",
    "OPENING_UNDERSIZED": "开孔小于接管外径要求",
    "OPENING_CLEARANCE_TOO_LARGE": "开孔与接管径向间隙过大",
    "NOZZLE_DOES_NOT_CROSS_OPENING_PLANE": "接管未穿过开孔所在平面",
    "NOZZLE_DOES_NOT_SPAN_HOST_WALL": "接管未跨越完整筒壁厚度",
    "NO_MATCHING_OPENING": "未找到可匹配的可靠开孔",
    "EXACT_BREP_EVIDENCE_REQUIRED": "缺少精确B-Rep证据",
    "COMPLETE_OPENING_BOUNDARY_REQUIRED": "缺少完整开孔边界",
    "HOST_WALL_DISCONTINUITY_REQUIRED": "尚未确认筒壁在开孔处中断",
    "HOST_WALL_THICKNESS_REQUIRED": "缺少局部筒壁厚度证据",
    "INNER_RADIUS_NOT_OBSERVED": "未识别接管内圆柱面",
    "MULTIPLE_CONCENTRIC_RADII": "发现多个同心半径，需要确认内外壁",
    "AMBIGUOUS_MATCH": "存在多个候选接口，无法唯一配对",
    "NO_RELIABLE_OPENING_EVIDENCE": "未发现具有完整边界和筒壁不连续依据的可靠开孔",
    "NO_ANALYTIC_CYLINDER_EVIDENCE": "未发现可用于接管识别的解析圆柱面",
}


def _explain_codes(codes: list[str]) -> str:
    return "；".join(CODE_LABELS.get(code, code) for code in codes)


def options_from_rules(rules: Mapping[str, Any] | None) -> dict[str, dict[str, float]]:
    """Translate the central ruleset into matching and exact-analysis options."""
    config = (rules or {}).get("opening_interface") or {}
    if not config:
        return {"matching_options": {}, "analysis_options": {}}
    return {
        "matching_options": {
            "search_margin_mm": float(config["candidate_search_margin_mm"]),
            "angle_candidate_limit_deg": float(config["candidate_angle_limit_deg"]),
            "offset_candidate_limit_mm": float(config["candidate_offset_limit_mm"]),
            "radius_candidate_limit_mm": float(config["candidate_radius_limit_mm"]),
            "axial_margin_mm": float(config["candidate_axial_margin_mm"]),
            "ambiguity_score_delta": float(config["ambiguity_score_delta"]),
        },
        "analysis_options": {
            "coaxial_tolerance_mm": float(config["coaxial_tolerance_mm"]),
            "angle_tolerance_deg": float(config["angle_tolerance_deg"]),
            "radial_clearance_min_mm": float(config["radial_clearance_min_mm"]),
            "radial_clearance_max_mm": float(config["radial_clearance_max_mm"]),
            "axial_tolerance_mm": float(config["axial_tolerance_mm"]),
        },
    }


def _finding(result: Mapping[str, Any], source: str, *, rules_approved: bool = True,
             threshold_status: str = "UNSPECIFIED") -> CheckFinding:
    opening_id = str(result.get("opening_id") or "NO_OPENING")
    nozzle_id = str(result.get("nozzle_id") or "NO_NOZZLE")
    disposition = str(result.get("disposition") or "REVIEW")
    geometry_status = {"PASS": CheckStatus.PASS, "FAIL": CheckStatus.FAIL}.get(
        disposition, CheckStatus.NOT_EVALUATED)
    status = geometry_status if rules_approved else CheckStatus.WARN
    codes = list(result.get("failure_codes") or result.get("review_codes") or [])
    identity_key = f"opening={opening_id}|nozzle={nozzle_id}"
    digest = hashlib.sha256(identity_key.encode()).hexdigest()[:12].upper()
    measurements = dict(result.get("measurements") or {})
    clearance = measurements.get("radial_clearance_mm")
    return CheckFinding(
        issue_id=f"OPENING-{digest}", rule_id="GEOMETRY.OPENING_INTERFACE",
        status=status, severity=Severity.S4 if status is CheckStatus.FAIL else Severity.S2,
        title={CheckStatus.PASS: "接管与开孔匹配",
               CheckStatus.FAIL: "接管开孔接口不合格"}.get(status, "接管开孔接口需复核"),
        message=(("规则尚未批准，仅保留几何预判：" if not rules_approved else "")
                 + (_explain_codes(codes) if codes else "接口几何及证据满足当前规则")),
        object_a=opening_id, object_b=nozzle_id,
        measured_value=float(clearance) if clearance is not None else None,
        unit="mm" if clearance is not None else None,
        recommendation=("核对接管轴线、孔径、筒壁贯通和接口设计；"
                        "修正未开孔、错位或证据不足后复检。"),
        evidence=(Evidence(kind=EvidenceKind.CATIA_MEASUREMENT, source=source,
                           description="精确接管—开孔几何判定",
                           object_paths=(opening_id, nozzle_id), data=dict(result)),),
        metadata={"disposition": disposition, "geometry_disposition": disposition,
                  "issue_identity": {"algorithm": "OPENING_NOZZLE_PAIR_V1",
                                     "key": identity_key},
                  "threshold_status": threshold_status,
                  "formal_adjudication_allowed": rules_approved,
                  "failure_codes": result.get("failure_codes", []),
                  "review_codes": result.get("review_codes", []),
                  "opening_interface": {
                      "opening_id": opening_id, "nozzle_id": nozzle_id,
                      "measurements": measurements,
                      "evidence": dict(result.get("evidence") or {}),
                      "source_locators": dict(result.get("source_locators") or {}),
                      "reason_labels": [CODE_LABELS.get(code, code) for code in codes],
                  },
                  "mesh_used": False})


def build_opening_interface_bundle(payload: Mapping[str, Any],
                                   rules: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Normalize exact facts, match interfaces, and create unified findings."""
    source = str(payload.get("source") or "")
    adapted = adapt_exact_geometry(
        source=source,
        opening_face_records=payload.get("opening_face_records") or [],
        cylindrical_surface_records=payload.get("cylindrical_surface_records") or [])
    configured = options_from_rules(rules)
    matching_options = {**dict(payload.get("matching_options") or {}),
                        **configured["matching_options"]}
    analysis_options = {**dict(payload.get("analysis_options") or {}),
                        **configured["analysis_options"]}
    network = analyze_opening_network(
        adapted["openings"], adapted["nozzles"],
        matching_options=matching_options,
        analysis_options=analysis_options)
    threshold_status = str(((rules or {}).get("routing") or {}).get(
        "threshold_status") or "UNSPECIFIED")
    rules_approved = threshold_status != "ASSUMED_PENDING_APPROVAL"
    findings = [_finding(item, source, rules_approved=rules_approved,
                         threshold_status=threshold_status)
                for item in network["results"]]
    effective_counts = {
        "PASS": sum(item.status is CheckStatus.PASS for item in findings),
        "FAIL": sum(item.status is CheckStatus.FAIL for item in findings),
        "REVIEW": sum(item.status in (CheckStatus.WARN, CheckStatus.NOT_EVALUATED)
                      for item in findings),
    }
    return {"schema_version": "opening-interface-main-bundle.v1.0",
            "source": source, "adapter": adapted, "network": network,
            "applied_options": {"matching_options": matching_options,
                                "analysis_options": analysis_options,
                                "source": "central_ruleset" if configured["analysis_options"] else "defaults"},
            "disposition_counts": effective_counts,
            "geometry_disposition_counts": network["disposition_counts"],
            "rule_approval": {"threshold_status": threshold_status,
                              "formal_adjudication_allowed": rules_approved},
            "findings": [item.to_dict() for item in findings],
            "mesh_used": False}


def discover_opening_interface_bundle(inventory: Mapping[str, Any], *, source: str,
                                      rules: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Auto-discover and analyze when both exact openings and cylinders exist."""
    discovery = discover_adapter_payload(inventory, source=source)
    bundle = (build_opening_interface_bundle(discovery["adapter_payload"], rules=rules)
              if discovery["ready_for_adapter"] else None)
    codes = list(discovery.get("readiness_codes") or [])
    return {"schema_version": "opening-interface-auto-discovery.v1.0",
            "discovery": discovery, "analysis": bundle,
            "analysis_executed": bundle is not None,
            "coverage": {
                "status": "CHECKED" if bundle is not None else "NOT_CHECKED",
                "reason_codes": codes,
                "reason_labels": [CODE_LABELS.get(code, code) for code in codes],
            },
            "mesh_used": False}


def record_auto_discovery_coverage(payload: dict[str, Any], result: Mapping[str, Any],
                                   *, authority: str) -> None:
    """Make skipped interface discovery visible to completeness and reporting."""
    if result.get("analysis_executed"):
        payload["confidence_budget"]["not_checked"] = [
            item for item in payload["confidence_budget"]["not_checked"]
            if not str(item).startswith("接管—开孔接口自动检查未执行")]
        payload["confidence_budget"]["checked"].append(
            f"从{authority}自动发现并检查接管—开孔接口")
        return
    coverage = result.get("coverage") or {}
    labels = list(coverage.get("reason_labels") or ["自动发现条件不足"])
    payload["confidence_budget"]["not_checked"].append(
        f"接管—开孔接口自动检查未执行（{authority}）：{'；'.join(labels)}")
