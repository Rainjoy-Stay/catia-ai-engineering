"""Map engineering relationships to inspection policy without changing geometry facts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class InspectionDisposition(str, Enum):
    STANDARD_SPACING = "STANDARD_SPACING"
    CONNECTION_CHECK = "CONNECTION_CHECK"
    SUPPORT_CHECK = "SUPPORT_CHECK"
    INTERFERENCE_FAIL = "INTERFERENCE_FAIL"
    CONSERVATIVE_FALLBACK = "CONSERVATIVE_FALLBACK"


def derive_inspection_disposition(conflict: Mapping[str, Any],
                                  relationship: Mapping[str, Any] | None = None) -> dict[str, Any]:
    conflict_type = str(conflict.get("type", "UNKNOWN")).upper()
    relationship = dict(relationship or conflict.get("relationship_assessment") or {})
    relation_type = str(relationship.get("relation_type", "UNKNOWN")).upper()
    confidence = float(relationship.get("confidence", 0.0))
    metadata = relationship.get("metadata") or {}
    raw_metadata = metadata.get("raw_ai_metadata") or {}
    inspection_profile = str(relationship.get("inspection_profile") or
                             metadata.get("inspection_profile") or
                             raw_metadata.get("inspection_profile") or "GENERIC")
    if conflict_type == "CLASH":
        disposition = InspectionDisposition.INTERFERENCE_FAIL
        reason = "CATIA检测到实体穿透；工程关系不得绕过穿透安全门。"
    elif conflict_type == "CLEARANCE":
        disposition = InspectionDisposition.STANDARD_SPACING
        reason = "组件间存在正间隙，继续执行标准间距规则。"
    elif conflict_type == "CONTACT" and relation_type in {"DIRECT_INTERFACE", "CONNECTED"} and confidence >= 0.92:
        disposition = InspectionDisposition.CONNECTION_CHECK
        reason = "零距离接触具有高置信直接连接证据，进入连接检查策略。"
    elif conflict_type == "CONTACT" and relation_type == "SUPPORTED" and confidence >= 0.92:
        disposition = InspectionDisposition.SUPPORT_CHECK
        reason = "零距离接触具有高置信支撑证据，进入支撑检查策略。"
    else:
        disposition = InspectionDisposition.CONSERVATIVE_FALLBACK
        reason = "冲突或关系证据不足，保持人工复核。"
    return {"disposition": disposition.value, "reason": reason,
            "conflict_type": conflict_type, "relationship_type": relation_type,
            "relationship_confidence": confidence,
            "inspection_profile": inspection_profile,
            "source": "INSPECTION_SEMANTIC_LAYER_V1.0"}
