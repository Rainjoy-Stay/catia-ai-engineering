"""Turn exact or tessellated surface-interaction facts into traceable findings.

The geometry kernel remains the authority for intersection points and distance.
This adapter never estimates a volume for an open shell or surface.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .geometry_integrity import GeometryTolerance, InspectionResult, classify_interaction
from .models import CheckFinding, CheckStatus, Evidence, EvidenceKind, Severity


def _status(value: str) -> CheckStatus:
    return {InspectionResult.PASS.value: CheckStatus.PASS,
            InspectionResult.FAIL.value: CheckStatus.FAIL}.get(value, CheckStatus.NOT_EVALUATED)


def surface_fact_to_finding(fact: Mapping[str, Any], *, tolerance: GeometryTolerance,
                            required_clearance_mm: float = 0.0) -> CheckFinding:
    """Convert one deterministic Solid/Surface or Surface/Surface fact.

    Required fields are object_a, object_b, entity_a, entity_b, and one of
    intersects, intersection_depth_mm, minimum_distance_mm, or contained.
    """
    first_id, second_id = str(fact["object_a"]), str(fact["object_b"])
    first = str(fact.get("object_a_name") or first_id)
    second = str(fact.get("object_b_name") or second_id)
    decision = classify_interaction(fact, tolerance, required_clearance_mm=required_clearance_mm)
    interaction = decision["interaction_type"]
    # Display names are not unique in STEP exports (several solids commonly
    # share names such as PartBody).  Stable topology IDs must therefore own
    # finding identity; names remain presentation-only fields.
    digest = hashlib.sha256(
        "|".join(sorted((first_id, second_id)) + [interaction]).encode()
    ).hexdigest()[:10].upper()
    points = list(fact.get("intersection_points_mm") or [])
    location = tuple(points[0]) if points and len(points[0]) == 3 else None
    measured = fact.get("minimum_distance_mm")
    if measured is None:
        measured = fact.get("intersection_depth_mm")
    status = _status(decision["result"])
    title = {
        "SURFACE_PENETRATION": "实体穿过无厚度边界",
        "SURFACE_INTERSECTION": "无厚度边界发生相交",
        "EXPECTED_CONTACT": "允许区域内的预期接触",
        "SUSPECTED_CONVERSION_ERROR": "疑似格式转换几何失真",
    }.get(interaction, f"几何关系：{interaction}")
    message = {
        CheckStatus.FAIL: "确定性几何计算确认了非允许的交叉或间距违规。",
        CheckStatus.PASS: "交互位于已验证的允许区域或为预期包含关系。",
        CheckStatus.NOT_EVALUATED: "几何或工程语义证据不足，需人工复核。",
    }[status]
    raw = dict(fact)
    raw["stable_object_ids"] = [first_id, second_id]
    raw["classification"] = decision
    return CheckFinding(
        issue_id=f"GEO-{interaction}-{digest}", rule_id=f"GEOMETRY.{interaction}",
        status=status, severity=Severity.S4 if status is CheckStatus.FAIL else Severity.S2,
        title=title, message=message, object_a=first, object_b=second,
        measured_value=float(measured) if measured is not None else None,
        limit_value=required_clearance_mm if measured is not None else None,
        unit="mm" if measured is not None else None, tolerance=tolerance.contact_mm,
        location_xyz_mm=location, recommendation=(
            "在 CATIA 中核对交点附近是否存在设计孔、接口、法兰或允许区域；"
            "若不存在，修正管路或边界几何后复检。"),
        evidence=(Evidence(kind=EvidenceKind.CATIA_MEASUREMENT,
                           source=str(fact.get("method", "GEOMETRY_KERNEL")),
                           description="Solid/Shell/Surface interaction fact",
                           object_paths=(first, second), data=raw),),
        metadata={"interaction_type": interaction, "geometry_kind_a": decision["geometry_kind_a"],
                  "geometry_kind_b": decision["geometry_kind_b"],
                  "requires_human_review": status is CheckStatus.NOT_EVALUATED},
    )
