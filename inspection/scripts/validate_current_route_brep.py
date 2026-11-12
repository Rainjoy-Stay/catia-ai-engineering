"""Validate the current Part3 route from the exported CATProduct STEP."""

import json
from pathlib import Path

from catia_checker.brep_route_validation import (
    BRepRouteValidationRequest, validate_route_brep,
)

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "project/artifacts/MiniEngine_route_brep_validation_20260922.stp"
result = validate_route_brep(BRepRouteValidationRequest(
    source,
    "STEP_SOLID_0009",
    {
        "Part1.1": ("STEP_SOLID_0001",),
        "Part2.1": ("STEP_SOLID_0002",),
        "Part4.1": ("STEP_SOLID_0003", "STEP_SOLID_0004"),
        "Part3.1": ("STEP_SOLID_0005", "STEP_SOLID_0006", "STEP_SOLID_0007"),
        "Part5.1": ("STEP_SOLID_0008",),
    },
    allowed_zero_distance_contacts=frozenset({"Part1.1"}),
    boundary_component="Part2.1",
))
output = ROOT / "project/artifacts/P3_POINTS1_2_MESH_D4_R4_brep_validation.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
