"""Geometry admission, health precheck, and deterministic relation policy.

This module deliberately does not calculate B-Rep intersections.  It consumes
facts produced by CATIA/a CAD kernel and makes the admission and disposition
rules consistent for solids and zero-volume boundary geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .shell_health import classify_shell_health
from .conversion_reliability import conversion_signal
from .allowed_regions import evaluate_allowed_region


class GeometryEntityKind(str, Enum):
    SOLID = "SOLID"
    CLOSED_SHELL = "CLOSED_SHELL"
    OPEN_SHELL = "OPEN_SHELL"
    SURFACE = "SURFACE"
    FACE = "FACE"
    SHEET_BODY = "SHEET_BODY"
    COMPOUND = "COMPOUND"
    UNKNOWN = "UNKNOWN"


class InteractionType(str, Enum):
    CLEAR = "CLEAR"
    NEAR = "NEAR"
    CONTACT = "CONTACT"
    MICRO_OVERLAP = "MICRO_OVERLAP"
    SOLID_INTERFERENCE = "SOLID_INTERFERENCE"
    SURFACE_PENETRATION = "SURFACE_PENETRATION"
    SURFACE_INTERSECTION = "SURFACE_INTERSECTION"
    CONTAINMENT = "CONTAINMENT"
    EXPECTED_CONTACT = "EXPECTED_CONTACT"
    EXPECTED_CONTAINMENT = "EXPECTED_CONTAINMENT"
    SUSPECTED_CONVERSION_ERROR = "SUSPECTED_CONVERSION_ERROR"
    NOT_EVALUATED = "NOT_EVALUATED"


class InspectionResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


PHYSICAL_BOUNDARY_KINDS = frozenset({
    GeometryEntityKind.SOLID, GeometryEntityKind.CLOSED_SHELL,
    GeometryEntityKind.OPEN_SHELL, GeometryEntityKind.SURFACE,
    GeometryEntityKind.FACE, GeometryEntityKind.SHEET_BODY,
})


@dataclass(frozen=True)
class GeometryTolerance:
    contact_mm: float = 0.01
    micro_overlap_mm: float = 0.1
    near_margin_mm: float = 0.5
    source: str = "ruleset"

    def __post_init__(self) -> None:
        if min(self.contact_mm, self.micro_overlap_mm, self.near_margin_mm) < 0:
            raise ValueError("geometry tolerances must be non-negative")
        if self.micro_overlap_mm < self.contact_mm:
            raise ValueError("micro_overlap_mm must be >= contact_mm")


def classify_entity(record: Mapping[str, Any]) -> GeometryEntityKind:
    explicit = str(record.get("entity_kind") or "").upper()
    if explicit:
        try:
            return GeometryEntityKind(explicit)
        except ValueError:
            pass
    step_type = str(record.get("step_entity_type") or "").upper()
    closure = str(record.get("closure_state") or "UNKNOWN").upper()
    geometry = str(record.get("geometry_kind") or "UNKNOWN").upper()
    if step_type == "SHELL_BASED_SURFACE_MODEL":
        return GeometryEntityKind.CLOSED_SHELL if closure == "CLOSED" else GeometryEntityKind.OPEN_SHELL
    if geometry == "SOLID":
        return GeometryEntityKind.SOLID
    if geometry == "SHELL":
        return GeometryEntityKind.CLOSED_SHELL if closure == "CLOSED" else GeometryEntityKind.OPEN_SHELL
    if geometry in {"SURFACE", "FACE", "SHEET_BODY", "COMPOUND"}:
        return GeometryEntityKind(geometry)
    return GeometryEntityKind.UNKNOWN


def admission_decision(record: Mapping[str, Any]) -> dict[str, Any]:
    """Decide whether geometry participates; volume is never an exclusion rule."""
    kind = classify_entity(record)
    if bool(record.get("suppressed")):
        return {"included": False, "why_skipped": "SUPPRESSED", "entity_kind": kind.value}
    if bool(record.get("user_excluded")):
        return {"included": False, "why_skipped": "USER_EXCLUDED", "entity_kind": kind.value}
    if bool(record.get("duplicate")):
        return {"included": False, "why_skipped": "DUPLICATE", "entity_kind": kind.value}
    if bool(record.get("reference_geometry")):
        return {"included": False, "why_skipped": "REFERENCE_GEOMETRY", "entity_kind": kind.value}
    state = str(record.get("geometry_state") or "AVAILABLE").upper()
    if state in {"EMPTY", "UNAVAILABLE"}:
        return {"included": False, "why_skipped": "GEOMETRY_PARSE_FAILED", "entity_kind": kind.value}
    if kind in PHYSICAL_BOUNDARY_KINDS:
        return {"included": True, "why_skipped": None, "entity_kind": kind.value,
                "zero_volume_supported": kind is not GeometryEntityKind.SOLID}
    return {"included": False, "why_skipped": "NO_PHYSICAL_MEANING_UNCONFIRMED",
            "entity_kind": kind.value}


def build_model_precheck(records: Iterable[Mapping[str, Any]], *,
                         source_format: str = "UNKNOWN") -> dict[str, Any]:
    entities = list(records)
    admissions = []
    counts = {kind.value: 0 for kind in GeometryEntityKind}
    issues: list[dict[str, Any]] = []
    conversion_signals = []
    for record in entities:
        decision = admission_decision(record)
        object_id = str(record.get("stable_body_id") or record.get("source_id") or
                        record.get("source_name") or "UNKNOWN")
        decision = {"object_id": object_id, **decision}
        admissions.append(decision)
        counts[decision["entity_kind"]] += 1
        if decision["entity_kind"] == GeometryEntityKind.OPEN_SHELL.value:
            issues.append({"object_id": object_id, "code": "OPEN_SHELL", "severity": "REVIEW"})
        if decision["entity_kind"] == GeometryEntityKind.UNKNOWN.value:
            issues.append({"object_id": object_id, "code": "UNKNOWN_GEOMETRY", "severity": "REVIEW"})
        stats = record.get("surface_statistics") or {}
        if stats.get("unmeasured_face_count", 0):
            issues.append({"object_id": object_id, "code": "UNMEASURED_FACES", "severity": "REVIEW"})
        if record.get("suspected_hollow_became_solid"):
            issues.append({"object_id": object_id, "code": "SUSPECTED_HOLLOW_TO_SOLID",
                           "severity": "REVIEW"})
        shell_health = classify_shell_health(record)
        signal = conversion_signal(record)
        conversion_signals.append(signal)
        if signal["suspected_conversion_error"]:
            issues.append({"object_id": object_id, "code": "SUSPECTED_HOLLOW_TO_SOLID",
                           "severity": "REVIEW"})
        for code in shell_health["issues"]:
            if code not in {item["code"] for item in issues if item["object_id"] == object_id}:
                issues.append({"object_id": object_id, "code": code, "severity": "REVIEW"})
    included = sum(item["included"] for item in admissions)
    penalty = min(80, sum(15 if item["code"] in {"OPEN_SHELL", "SUSPECTED_HOLLOW_TO_SOLID"}
                          else 5 for item in issues))
    score = max(0, 100 - penalty) if entities else 0
    reliability = "HIGH" if score >= 85 else "MEDIUM" if score >= 60 else "LOW"
    return {
        "schema_version": "geometry-precheck.v1.0", "source_format": source_format,
        "model_health_score": score, "model_reliability": reliability,
        "entity_count": len(entities), "included_entity_count": included,
        "geometry_type_counts": counts, "issues": issues,
        "conversion_signals": conversion_signals,
        "admission_log": admissions,
        "surface_geometry_participates": any(
            item["included"] and item["entity_kind"] != GeometryEntityKind.SOLID.value
            for item in admissions),
    }


def classify_interaction(fact: Mapping[str, Any], tolerance: GeometryTolerance,
                         *, required_clearance_mm: float = 0.0) -> dict[str, Any]:
    """Classify an exact geometry fact without inventing geometric measurements."""
    kind_a = classify_entity(fact.get("entity_a") or {})
    kind_b = classify_entity(fact.get("entity_b") or {})
    surface_pair = kind_a is not GeometryEntityKind.SOLID or kind_b is not GeometryEntityKind.SOLID
    bounded_region = evaluate_allowed_region(fact)
    if fact.get("interface_depth_mm") is not None and bounded_region["result"] == "REVIEW":
        interaction, result = InteractionType.NOT_EVALUATED, InspectionResult.REVIEW
    elif fact.get("suspected_conversion_error"):
        interaction, result = InteractionType.SUSPECTED_CONVERSION_ERROR, InspectionResult.REVIEW
    elif fact.get("expected_containment"):
        interaction, result = InteractionType.EXPECTED_CONTAINMENT, InspectionResult.PASS
    elif fact.get("contained"):
        interaction, result = InteractionType.CONTAINMENT, InspectionResult.REVIEW
    elif (not surface_pair and fact.get("intersection_volume_mm3") is not None and
          float(fact["intersection_volume_mm3"]) > 0.0):
        interaction, result = InteractionType.SOLID_INTERFERENCE, InspectionResult.FAIL
    elif fact.get("intersects") and surface_pair:
        both_non_solid = (kind_a is not GeometryEntityKind.SOLID and
                          kind_b is not GeometryEntityKind.SOLID)
        if fact.get("allowed_region"):
            interaction, result = InteractionType.EXPECTED_CONTACT, InspectionResult.PASS
        elif fact.get("boundary_contact"):
            interaction, result = InteractionType.CONTACT, InspectionResult.REVIEW
        elif both_non_solid:
            interaction, result = InteractionType.SURFACE_INTERSECTION, InspectionResult.FAIL
        elif fact.get("penetration_confirmed") is True:
            interaction, result = InteractionType.SURFACE_PENETRATION, InspectionResult.FAIL
        else:
            # A Solid/Surface section is necessary but not sufficient evidence
            # for penetration. It may terminate at, or merely touch, the face.
            interaction, result = InteractionType.SURFACE_INTERSECTION, InspectionResult.REVIEW
    elif fact.get("intersection_depth_mm") is not None:
        depth = float(fact["intersection_depth_mm"])
        if depth <= tolerance.contact_mm:
            interaction, result = InteractionType.CONTACT, InspectionResult.REVIEW
        elif depth <= tolerance.micro_overlap_mm:
            interaction, result = InteractionType.MICRO_OVERLAP, InspectionResult.REVIEW
        else:
            interaction, result = InteractionType.SOLID_INTERFERENCE, InspectionResult.FAIL
    elif fact.get("minimum_distance_mm") is not None:
        distance = float(fact["minimum_distance_mm"])
        if distance <= tolerance.contact_mm:
            interaction, result = InteractionType.CONTACT, InspectionResult.REVIEW
        elif distance < required_clearance_mm:
            interaction, result = InteractionType.NEAR, InspectionResult.FAIL
        else:
            interaction, result = InteractionType.CLEAR, InspectionResult.PASS
    else:
        interaction, result = InteractionType.NOT_EVALUATED, InspectionResult.REVIEW
    return {"interaction_type": interaction.value, "result": result.value,
            "geometry_kind_a": kind_a.value, "geometry_kind_b": kind_b.value,
            "tolerance": {"contact_mm": tolerance.contact_mm,
                          "micro_overlap_mm": tolerance.micro_overlap_mm,
                          "near_margin_mm": tolerance.near_margin_mm,
                          "source": tolerance.source}}
