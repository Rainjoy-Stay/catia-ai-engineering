"""Conservative multi-feature PIPE candidate scoring without AI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PipeCandidateConfig:
    minimum_aspect_ratio: float = 5.0
    minimum_tubular_ratio: float = 0.35
    minimum_dominant_radius_support: float = 0.50
    aspect_ratio_full_score: float = 12.0
    tubular_ratio_full_score: float = 0.75
    diameter_variation_limit: float = 0.05
    centerline_full_score: float = 0.85
    minimum_pipe_score: float = 0.70
    minimum_evidence_coverage: float = 0.55


_WEIGHTS = {
    "aspect": 0.25, "tubular": 0.25, "diameter_stability": 0.20,
    "centerline": 0.20, "terminals": 0.10,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_pipe_candidate(features: Mapping[str, Any], *,
                         config: PipeCandidateConfig | None = None) -> dict[str, Any]:
    config = config or PipeCandidateConfig()
    scores: dict[str, float] = {}
    evidence: list[str] = []
    uncertainty: list[str] = []

    aspect = features.get("aspect_ratio_max_second", features.get("aspect_ratio_max_min"))
    if aspect is not None:
        scores["aspect"] = _clamp(float(aspect) / config.aspect_ratio_full_score)
        evidence.append(f"aspect_ratio={float(aspect):.6g}")
    else:
        uncertainty.append("aspect ratio unavailable")

    tubular = features.get("tubular_surface_ratio")
    if tubular is None:
        stats = features.get("surface_statistics", {})
        ratios = stats.get("surface_type_area_ratios", {})
        cylinder, torus = ratios.get("CYLINDER"), ratios.get("TORUS")
        if cylinder is not None and torus is not None:
            tubular = float(cylinder) + float(torus)
        elif stats.get("face_count"):
            counts = stats.get("surface_type_counts", {})
            tubular = (float(counts.get("CYLINDER", 0)) + float(counts.get("TORUS", 0))) / float(
                stats["face_count"])
            uncertainty.append("tubular ratio uses face-count proxy because face areas are unavailable")
    if tubular is not None:
        scores["tubular"] = _clamp(float(tubular) / config.tubular_ratio_full_score)
        evidence.append(f"tubular_surface_ratio={float(tubular):.6g}")
    else:
        uncertainty.append("tubular surface ratio unavailable")

    variation = features.get("diameter_variation")
    if variation is not None:
        variation = max(0.0, float(variation))
        scores["diameter_stability"] = _clamp(1.0 - variation / config.diameter_variation_limit)
        evidence.append(f"diameter_variation={variation:.6g}")
    else:
        uncertainty.append("diameter variation unavailable")

    centerline = features.get("centerline_continuity")
    if centerline is not None:
        scores["centerline"] = _clamp(float(centerline) / config.centerline_full_score)
        evidence.append(f"centerline_continuity={float(centerline):.6g}")
    else:
        uncertainty.append("centerline continuity unavailable")

    terminals = features.get("terminal_count")
    if terminals is not None:
        scores["terminals"] = 1.0 if int(terminals) == 2 else 0.35 if int(terminals) > 0 else 0.0
        evidence.append(f"terminal_count={int(terminals)}")
    else:
        uncertainty.append("terminal count unavailable")

    covered_weight = sum(_WEIGHTS[key] for key in scores)
    weighted_score = sum(_WEIGHTS[key] * value for key, value in scores.items())
    score = weighted_score / covered_weight if covered_weight else 0.0
    confidence = score * covered_weight
    hard_gates = {
        "minimum_aspect_ratio": aspect is not None and float(aspect) >= config.minimum_aspect_ratio,
        "minimum_tubular_ratio": tubular is not None and float(tubular) >= config.minimum_tubular_ratio,
        "minimum_dominant_radius_support": (
            features.get("dominant_radius_support") is None or
            float(features["dominant_radius_support"]) >= config.minimum_dominant_radius_support),
    }
    candidate_type = ("PIPE" if score >= config.minimum_pipe_score and
                       covered_weight >= config.minimum_evidence_coverage and
                       all(hard_gates.values()) else "UNKNOWN")
    if candidate_type == "UNKNOWN":
        uncertainty.append("evidence coverage or combined score is below the PIPE decision threshold")
        uncertainty.extend(f"hard gate failed: {name}" for name, passed in hard_gates.items() if not passed)
    return {
        "candidate_type": candidate_type,
        "confidence": round(confidence, 6),
        "pipe_score": round(score, 6),
        "evidence_coverage": round(covered_weight, 6),
        "feature_scores": {key: round(value, 6) for key, value in scores.items()},
        "hard_gates": hard_gates,
        "evidence": evidence,
        "uncertainty": uncertainty,
        "classifier": "DETERMINISTIC_MULTI_FEATURE_V0.2",
    }
