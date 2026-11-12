"""Evaluate semantic completeness from observed model content, never file suffix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .domain import SemanticLevel


@dataclass(frozen=True)
class SemanticEvaluation:
    level: SemanticLevel
    score: float
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level.value, "score": round(self.score, 6),
                "evidence": list(self.evidence), "limitations": list(self.limitations)}


def evaluate_semantic_level(manifest: Mapping[str, Any]) -> SemanticEvaluation:
    """Score only facts present in a CATIA manifest.

    The thresholds intentionally prefer SEMI/DUMB when metadata is incomplete.
    A STEP-derived model can be rich and a CATPart can be dumb; extensions are ignored.
    """
    summary = manifest.get("summary", {})
    assembly = manifest.get("assembly", {})
    parts = manifest.get("parts", {})
    unique_parts = int(summary.get("unique_parts", len(parts)) or 0)
    features = int(summary.get("total_features", 0) or 0)
    sketches = int(summary.get("total_sketches", 0) or 0)
    parameters = int(summary.get("total_parameters", 0) or 0)
    relations = sum(int(part.get("counts", {}).get("relations", 0) or 0)
                    for part in parts.values())

    def child_count(node: Mapping[str, Any]) -> int:
        children = node.get("children", ()) or ()
        return len(children) + sum(child_count(item) for item in children)

    component_count = 1 + child_count(assembly) if assembly else 0
    named_components = component_count > 1 and all(
        str(item.get("name", "")).strip()
        for item in _walk_components(assembly)
    )
    score = 0.0
    evidence: list[str] = []
    if component_count > 1:
        score += 0.22; evidence.append(f"assembly hierarchy contains {component_count} components")
    if unique_parts > 1:
        score += 0.13; evidence.append(f"{unique_parts} referenced parts are resolved")
    if named_components:
        score += 0.10; evidence.append("assembly components retain non-empty names")
    if features > 0:
        score += 0.25; evidence.append(f"{features} ordered features are present")
    if sketches > 0:
        score += 0.12; evidence.append(f"{sketches} sketches are present")
    if parameters > 0:
        score += 0.10; evidence.append(f"{parameters} parameters are present")
    if relations > 0:
        score += 0.08; evidence.append(f"{relations} relations are present")
    score = min(score, 1.0)
    if score >= 0.70:
        level = SemanticLevel.RICH
    elif score >= 0.25:
        level = SemanticLevel.SEMI
    else:
        level = SemanticLevel.DUMB
    limitations = []
    if features == 0: limitations.append("no ordered feature history was observed")
    if parameters == 0: limitations.append("no parameters were observed")
    if component_count <= 1: limitations.append("no assembly hierarchy was observed")
    return SemanticEvaluation(level, score, tuple(evidence), tuple(limitations))


def _walk_components(root: Mapping[str, Any]):
    if not root:
        return
    yield root
    for child in root.get("children", ()) or ():
        yield from _walk_components(child)
