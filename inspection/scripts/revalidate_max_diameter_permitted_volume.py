from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "project"))
from catia_checker.brep_route_validation import (  # noqa: E402
    BoundaryRoutePolicy, ComponentRoutePolicy,
    SeparateBRepRouteValidationRequest, validate_separate_route_brep,
)

ART = ROOT / "project" / "artifacts"
result_file = ART / "max_diameter_r25_20260922" / "route_development_result.json"
payload = json.loads(result_file.read_text(encoding="utf-8"))
shapes = {
    "Part1.1": ("STEP_SOLID_0001",),
    "Part2.1": ("STEP_SOLID_0002",),
    "Part4.1": ("STEP_SOLID_0003", "STEP_SOLID_0004"),
    "Part3.1": ("STEP_SOLID_0005", "STEP_SOLID_0006", "STEP_SOLID_0007"),
    "Part5.1": ("STEP_SOLID_0008",),
}
policies = {
    "Part1.1": ComponentRoutePolicy("ALLOW_CONTACT", 0.0),
    "Part2.1": ComponentRoutePolicy("ALLOW_CONTACT", 0.0),
    "Part4.1": ComponentRoutePolicy("CLEARANCE", 0.0),
    "Part3.1": ComponentRoutePolicy("CLEARANCE", 0.0),
    "Part5.1": ComponentRoutePolicy("CLEARANCE", 0.0),
}
for item in payload["candidates"]:
    item["validation"] = validate_separate_route_brep(
        SeparateBRepRouteValidationRequest(
            item["envelope"]["output_step"],
            ART / "MiniEngine_route_brep_validation_20260922.stp",
            "STEP_SOLID_0001", shapes,
            component_policies=policies,
            boundary_component="Part2.1",
            boundary_policy=BoundaryRoutePolicy(
                "Part2.1", "PERMITTED_VOLUME", 0.999999),
        ))
passing = [x for x in payload["candidates"] if x["validation"]["status"] == "PASS"]
payload["status"] = "PASS" if passing else "NO_BREP_VALID_CANDIDATE"
payload["selected_rank"] = passing[0]["rank"] if passing else None
payload["selected_diameter_mm"] = passing[0]["diameter_mm"] if passing else None
result_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
selected = passing[0] if passing else payload["candidates"][0]
part2 = next(x for x in selected["validation"]["components"] if x["component"] == "Part2.1")
print(json.dumps({
    "status": payload["status"],
    "selected_rank": payload["selected_rank"],
    "diameter_mm": payload["selected_diameter_mm"],
    "part2_state": part2["state"],
    "contained_fraction": part2.get("contained_fraction"),
}, ensure_ascii=False))
