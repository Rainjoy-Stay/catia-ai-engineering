"""Deterministic routing-rule evaluation for measured CATIA tube geometry."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .models import CheckFinding, CheckStatus, Evidence, EvidenceKind, Severity


VALID_THRESHOLD_STATUSES = {"APPROVED", "ASSUMED_PENDING_APPROVAL"}
VALID_BEND_MODES = {"absolute_mm", "ratio_r_over_d", "standard_profile"}
CONFIG_DIRECTORY = Path(__file__).resolve().parents[1] / "config"


def load_bend_radius_profile(routing: Mapping[str, Any]) -> Mapping[str, Any]:
    """Load an editable bend-radius standard profile referenced by active rules."""
    relative = str(routing.get("bend_radius_profile_file") or "").strip()
    if not relative:
        raise ValueError("routing.bend_radius_profile_file is required for standard_profile mode")
    candidate = (CONFIG_DIRECTORY / relative).resolve()
    if CONFIG_DIRECTORY.resolve() not in candidate.parents:
        raise ValueError("bend_radius_profile_file must stay under project/config")
    if not candidate.is_file():
        raise ValueError(f"Bend-radius profile not found: {candidate}")
    profile = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(profile, Mapping):
        raise ValueError("Bend-radius profile must be a JSON object")
    return profile


def validate_rules(rules: Mapping[str, Any]) -> None:
    """Fail closed when a ruleset could silently turn missing data into PASS."""
    if str(rules.get("schema_version", "")) != "1.1.0":
        raise ValueError("rules.schema_version must be 1.1.0")
    if not str(rules.get("ruleset_id", "")).strip():
        raise ValueError("rules.ruleset_id is required")
    routing = rules.get("routing")
    dmu = rules.get("dmu_clash")
    if not isinstance(routing, Mapping) or not isinstance(dmu, Mapping):
        raise ValueError("rules.routing and rules.dmu_clash are required objects")
    status = str(routing.get("threshold_status", ""))
    if status not in VALID_THRESHOLD_STATUSES:
        raise ValueError(f"Unsupported routing.threshold_status: {status or 'missing'}")
    bend_status = str(routing.get("bend_radius_standard_status", status))
    if bend_status not in VALID_THRESHOLD_STATUSES:
        raise ValueError(f"Unsupported routing.bend_radius_standard_status: {bend_status or 'missing'}")
    mode = str(routing.get("bend_radius_mode", ""))
    if mode not in VALID_BEND_MODES:
        raise ValueError(f"Unsupported routing.bend_radius_mode: {mode or 'missing'}")
    required = ("minimum_general_clearance_mm", "minimum_hot_zone_clearance_mm")
    for key in required:
        _positive_number(routing.get(key), f"routing.{key}", allow_zero=True)
    if mode == "standard_profile":
        profile = load_bend_radius_profile(routing)
        _positive_number(profile.get("minimum_bend_radius_ratio_r_over_d"),
                         "bend profile.minimum_bend_radius_ratio_r_over_d")
        preferred = profile.get("preferred_bend_radius_ratios_r_over_d")
        if not isinstance(preferred, list) or not preferred:
            raise ValueError("bend profile.preferred_bend_radius_ratios_r_over_d must be a non-empty list")
        for index, value in enumerate(preferred):
            _positive_number(value, f"bend profile.preferred_bend_radius_ratios_r_over_d[{index}]")
    elif mode == "absolute_mm":
        _positive_number(routing.get("minimum_bend_radius_mm"), "routing.minimum_bend_radius_mm")
    else:
        _positive_number(routing.get("minimum_bend_radius_ratio_r_over_d"),
                         "routing.minimum_bend_radius_ratio_r_over_d")
    _positive_number(dmu.get("clearance_mm"), "dmu_clash.clearance_mm", allow_zero=True)
    max_conflicts = dmu.get("max_conflicts")
    if isinstance(max_conflicts, bool) or not isinstance(max_conflicts, int) or max_conflicts <= 0:
        raise ValueError("dmu_clash.max_conflicts must be a positive integer")
    relationship = rules.get("component_relationship", {})
    for key in ("minimum_pass_confidence", "step_minimum_pass_confidence"):
        value = relationship.get(key)
        if value is not None:
            number = _positive_number(value, f"component_relationship.{key}")
            if number > 1:
                raise ValueError(f"component_relationship.{key} must not exceed 1")
    opening = rules.get("opening_interface")
    if opening is not None:
        if not isinstance(opening, Mapping):
            raise ValueError("rules.opening_interface must be an object")
        opening_fields = (
            "candidate_search_margin_mm", "candidate_angle_limit_deg",
            "candidate_offset_limit_mm", "candidate_radius_limit_mm",
            "candidate_axial_margin_mm", "ambiguity_score_delta",
            "coaxial_tolerance_mm", "angle_tolerance_deg",
            "radial_clearance_min_mm", "radial_clearance_max_mm", "axial_tolerance_mm",
        )
        for key in opening_fields:
            _positive_number(opening.get(key), f"opening_interface.{key}", allow_zero=True)
        if float(opening["radial_clearance_max_mm"]) < float(opening["radial_clearance_min_mm"]):
            raise ValueError("opening_interface.radial_clearance_max_mm must be >= minimum")


def _positive_number(value: Any, field: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{field} must be a finite {relation} number")
    return number


def general_clearance_mm(rules: Mapping[str, Any]) -> float:
    """Return the configured general routing clearance, with DMU fallback."""
    routing = rules.get("routing", {})
    dmu = rules.get("dmu_clash", {})
    value = float(routing.get("minimum_general_clearance_mm", dmu.get("clearance_mm", 0.1)))
    if value < 0:
        raise ValueError("minimum_general_clearance_mm must be non-negative")
    return value


def _issue_id(route_name: str) -> str:
    digest = hashlib.sha256(route_name.encode("utf-8")).hexdigest()[:10].upper()
    return f"ROUTING-BEND-RADIUS-{digest}"


def evaluate_bend_radius(
    route: Mapping[str, Any], rules: Mapping[str, Any]
) -> CheckFinding:
    """Compare the minimum measured bend R/D against the configured limit."""
    route_name = str(route.get("name") or route.get("route_name") or "UNKNOWN")
    routing = rules.get("routing", {})
    absolute_limit = routing.get("minimum_bend_radius_mm")
    ratio_limit = routing.get("minimum_bend_radius_ratio_r_over_d")
    mode = str(routing.get("bend_radius_mode") or
               ("ratio_r_over_d" if ratio_limit is not None else ""))
    if mode not in VALID_BEND_MODES:
        raise ValueError(f"Unsupported or missing bend_radius_mode: {mode or 'missing'}")
    profile: Mapping[str, Any] = {}
    if mode == "standard_profile":
        profile = load_bend_radius_profile(routing)
        overrides = routing.get("bend_radius_overrides") or {}
        configured = overrides.get("minimum_ratio_r_over_d")
        limit = _positive_number(
            configured if configured is not None else profile.get("minimum_bend_radius_ratio_r_over_d"),
            "routing.bend_radius_overrides.minimum_ratio_r_over_d")
        rule_unit = "ratio"
    elif mode == "absolute_mm":
        limit = _positive_number(absolute_limit, "routing.minimum_bend_radius_mm")
        rule_unit = "mm"
    else:
        limit = _positive_number(ratio_limit, "routing.minimum_bend_radius_ratio_r_over_d")
        rule_unit = "ratio"
    threshold_status = str(
        routing.get("bend_radius_standard_status", routing.get("threshold_status", "UNKNOWN"))
        if mode == "standard_profile" else routing.get("threshold_status", "UNKNOWN"))
    diameter_raw = route.get("diameter_mm")
    radii_raw = route.get("bend_radii_mm", ())
    radii = [float(value) for value in radii_raw if value is not None and float(value) > 0]
    diameter = float(diameter_raw) if diameter_raw is not None else 0.0
    if threshold_status not in VALID_THRESHOLD_STATUSES:
        raise ValueError(f"Unsupported or missing threshold_status: {threshold_status or 'missing'}")
    assumed = threshold_status == "ASSUMED_PENDING_APPROVAL"

    evidence_data = {
        "diameter_mm": diameter_raw,
        "bend_radii_mm": radii,
        "threshold_status": threshold_status,
        "rule_expression": ("min(bend_radius_mm) >= minimum_bend_radius_mm" if mode == "absolute_mm"
                            else "min(bend_radius_mm) / diameter_mm >= minimum_bend_radius_ratio_r_over_d"),
    }
    common = dict(
        issue_id=_issue_id(route_name),
        rule_id=("ROUTING.MINIMUM_BEND_RADIUS_MM" if mode == "absolute_mm"
                 else "ROUTING.MINIMUM_BEND_RADIUS_R_OVER_D"),
        severity=Severity.S2 if assumed else Severity.S3,
        title="管路最小弯曲半径",
        object_a=route_name,
        limit_value=limit,
        unit=rule_unit,
        standard_reference=(str(routing.get("standard_reference")) if routing.get("standard_reference")
                            else str(profile.get("standard_id") or "") or None),
        evidence=(Evidence(
            kind=EvidenceKind.CATIA_MEASUREMENT,
            source=str(route.get("measurement_source") or "catia_tubing_inspect_route"),
            description=("精确 B-Rep 外形中心线与弯曲半径测量；工程管路语义未确认"
                         if route.get("pipe_semantics_confirmed") is False
                         else "CATIA 原生管路节点直径与弯曲半径测量"),
            object_paths=(route_name,),
            data=evidence_data,
        ),),
        metadata={"threshold_status": threshold_status},
    )
    if not radii or (mode != "absolute_mm" and diameter <= 0):
        return CheckFinding(
            status=CheckStatus.NOT_EVALUATED,
            message=("缺少有效弯曲半径数据，无法按绝对半径规则评价。" if mode == "absolute_mm"
                     else "缺少有效管径或弯曲半径数据，无法计算 R/D。"),
            measured_value=None,
            recommendation="检查管路截面直径及内部节点的 bend_radius 数据后重新执行。",
            **common,
        )

    measured = min(radii) if mode == "absolute_mm" else min(radii) / diameter
    if mode == "standard_profile":
        evidence_data["standard_profile"] = profile.get("standard_id")
        evidence_data["preferred_ratios_r_over_d"] = profile.get("preferred_bend_radius_ratios_r_over_d", [])
        evidence_data["working_pressure_mpa"] = route.get("working_pressure_mpa")
        nominal = [float(value) for value in profile.get("nominal_diameters_mm", [])]
        if nominal and not any(math.isclose(diameter, value, abs_tol=1e-6) for value in nominal):
            return CheckFinding(
                status=CheckStatus.NOT_EVALUATED,
                message=f"DN={diameter:g} mm 不在当前标准配置的公称外径表内，禁止外推判定。",
                measured_value=measured,
                recommendation="在标准配置中补充该公称外径，或选择适用的标准版本。",
                **common,
            )
    if measured >= limit:
        status = CheckStatus.WARN if assumed else CheckStatus.PASS
        metric = "最小弯曲半径" if mode == "absolute_mm" else "最小 R/D"
        suffix = " mm" if mode == "absolute_mm" else ""
        message = (
            f"{metric}={measured:.3f}{suffix}，满足当前配置阈值 {limit:.3f}{suffix}；"
            + ("但该阈值尚待项目批准。" if assumed else "")
        )
        if mode == "standard_profile":
            pressure = route.get("working_pressure_mpa")
            high = profile.get("high_pressure_recommendation") or {}
            pressure_limit = high.get("pressure_above_mpa")
            ratio_recommendation = high.get("recommended_minimum_ratio_r_over_d")
            if pressure is not None and pressure_limit is not None and ratio_recommendation is not None:
                if float(pressure) > float(pressure_limit) and measured < float(ratio_recommendation):
                    status = CheckStatus.WARN
                    message += (f" 工作压力 {float(pressure):g} MPa 超过 {float(pressure_limit):g} MPa，"
                                f"标准建议 R/D 不小于 {float(ratio_recommendation):g}，需工程复核。")
    else:
        status = CheckStatus.WARN if assumed else CheckStatus.FAIL
        metric = "最小弯曲半径" if mode == "absolute_mm" else "最小 R/D"
        suffix = " mm" if mode == "absolute_mm" else ""
        message = (
            f"{metric}={measured:.3f}{suffix}，低于当前配置阈值 {limit:.3f}{suffix}；"
            + ("阈值尚待批准，当前仅提示复核。" if assumed else "判定为不符合。")
        )
    return CheckFinding(
        status=status,
        message=message,
        measured_value=measured,
        recommendation="核对管径、弯曲半径及适用工程规范；必要时增大弯曲半径或调整路径。",
        **common,
    )
