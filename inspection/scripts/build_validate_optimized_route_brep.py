"""Build and exactly validate the highest-ranked offline route envelope."""

import json
from pathlib import Path

from catia_checker.brep_route_validation import (
    ComponentRoutePolicy, SeparateBRepRouteValidationRequest,
    validate_separate_route_brep,
)
from catia_checker.route_brep_envelope import build_route_envelope_step

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "project" / "artifacts"
design_file = ARTIFACTS / "part3_route_design_optimization_20260922.json"
design = json.loads(design_file.read_text(encoding="utf-8"))
if design["status"] not in {"OK", "REVIEW_DIAMETER_SELECTION"} or not design["ranked_top"]:
    raise RuntimeError("No optimized route is available for B-Rep validation")
route = design["ranked_top"][0]
route_step = ARTIFACTS / "part3_optimized_route_envelope.stp"
build = build_route_envelope_step(
    route["points_mm"], route["bend_radii_mm"], route["diameter_mm"], route_step)
validation = validate_separate_route_brep(SeparateBRepRouteValidationRequest(
    route_step,
    ARTIFACTS / "MiniEngine_route_brep_validation_20260922.stp",
    "STEP_SOLID_0001",
    {
        "Part1.1": ("STEP_SOLID_0001",),
        "Part2.1": ("STEP_SOLID_0002",),
        "Part4.1": ("STEP_SOLID_0003", "STEP_SOLID_0004"),
        "Part3.1": ("STEP_SOLID_0005", "STEP_SOLID_0006", "STEP_SOLID_0007"),
        "Part5.1": ("STEP_SOLID_0008",),
    },
    component_policies={
        "Part1.1": ComponentRoutePolicy("ALLOW_CONTACT"),
        "Part2.1": ComponentRoutePolicy("CLEARANCE", 0.0),
        "Part3.1": ComponentRoutePolicy("REQUIRED_CONTACT"),
        "Part4.1": ComponentRoutePolicy("CLEARANCE", 0.0),
        "Part5.1": ComponentRoutePolicy("CLEARANCE", 0.0),
    },
    boundary_component="Part2.1",
))
payload = {"build": build, "validation": validation, "catia_mutation": "NONE"}
output = ARTIFACTS / "part3_optimized_route_brep_validation.json"
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
