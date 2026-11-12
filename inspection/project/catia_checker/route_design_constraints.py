"""Configuration boundary between project inputs, standards and route search."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class RouteDesignCase:
    diameter_mm: float
    bend_radius_mm: float
    clearance_mm: float
    minimum_straight_mm: float
    standard_id: str | None
    standard_policy: str
    preferred_radius: bool


def load_route_design_cases(
    config_file: str | Path,
    measured_port_diameters_mm: Sequence[float] = (),
) -> tuple[dict[str, Any], tuple[RouteDesignCase, ...]]:
    """Resolve editable inputs into D/R cases; no dimensions live in the solver."""
    path = Path(config_file).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "route-design.v1.0":
        raise ValueError("Unsupported route design configuration schema")
    diameter = config["diameter"]
    mode = diameter["mode"]
    if mode == "candidate_set":
        diameters = _positive_values(diameter.get("candidates_model_mm", ()), "diameter candidates")
    elif mode == "measured_ports":
        diameters = _positive_values(measured_port_diameters_mm, "measured port diameters")
        tolerance = float(diameter.get("matching_tolerance_mm", 0.1))
        if max(diameters) - min(diameters) > tolerance:
            raise ValueError("Port diameters differ; reducer policy is required")
        diameters = (sum(diameters) / len(diameters),)
    else:
        raise ValueError(f"Unsupported diameter mode: {mode}")

    standard_cfg = config.get("standard", {})
    policy = standard_cfg.get("policy", "REFERENCE_ONLY")
    if policy not in {"REFERENCE_ONLY", "PREFERRED", "MANDATORY"}:
        raise ValueError("standard.policy must be REFERENCE_ONLY, PREFERRED or MANDATORY")
    standard: dict[str, Any] = {}
    standard_id = None
    if standard_cfg.get("profile"):
        standard_path = (path.parent / standard_cfg["profile"]).resolve()
        standard = json.loads(standard_path.read_text(encoding="utf-8"))
        standard_id = standard.get("standard_id")

    radius = config["bend_radius"]
    radius_mode = radius["mode"]
    explicit = _positive_values(radius.get("candidates_model_mm", ()), "radius candidates") \
        if radius_mode == "candidate_set" else ()
    if radius_mode == "standard_ratio_series" and not standard:
        raise ValueError("standard_ratio_series requires standard.profile")
    if radius_mode not in {"candidate_set", "standard_ratio_series"}:
        raise ValueError(f"Unsupported bend radius mode: {radius_mode}")

    clearance = float(config["clearance_mm"])
    straight = float(config.get("minimum_straight_mm", 0.0))
    if clearance < 0 or straight < 0:
        raise ValueError("clearance_mm and minimum_straight_mm cannot be negative")
    preferred_ratios = set(map(float, standard.get("preferred_bend_radius_ratios_r_over_d", ())))
    cases: list[RouteDesignCase] = []
    for diameter_mm in diameters:
        radii = explicit
        if radius_mode == "standard_ratio_series":
            radii = tuple(diameter_mm * float(value) for value in
                          standard["standard_radius_ratios_r_over_d"])
        for bend_radius_mm in radii:
            ratio = bend_radius_mm / diameter_mm
            minimum = standard.get("minimum_bend_radius_ratio_r_over_d")
            if policy == "MANDATORY" and minimum is not None and ratio < float(minimum):
                continue
            cases.append(RouteDesignCase(
                diameter_mm, bend_radius_mm, clearance, straight,
                standard_id, policy, ratio in preferred_ratios,
            ))
    if not cases:
        raise ValueError("Design configuration resolved to no D/R cases")
    # Preferred standard cases rank first, then larger R/D. This is only case
    # order; geometry feasibility and route objective remain authoritative.
    cases.sort(key=lambda item: (not item.preferred_radius,
                                 -(item.bend_radius_mm / item.diameter_mm)))
    return config, tuple(cases)


def _positive_values(values: Sequence[float], label: str) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if not result or any(value <= 0 for value in result):
        raise ValueError(f"{label} must contain positive values")
    return result
