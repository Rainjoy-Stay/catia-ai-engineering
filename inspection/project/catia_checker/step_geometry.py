"""Read analytic pipe-like geometry preserved in a STEP text file.

This is deliberately conservative: it reports reproducible geometric
candidates and confidence, but does not pretend that STEP restores native
CATIA Piping semantics or engineering intent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_TORUS = re.compile(
    r"#(?P<id>\d+)\s*=\s*TOROIDAL_SURFACE\([^,]*,#(?P<placement>\d+),"
    r"(?P<major>[-+0-9.Ee]+),(?P<minor>[-+0-9.Ee]+)\)"
)
_CYLINDER = re.compile(
    r"#(?P<id>\d+)\s*=\s*CYLINDRICAL_SURFACE\([^,]*,#(?P<placement>\d+),"
    r"(?P<radius>[-+0-9.Ee]+)\)"
)


def inspect_step_pipe_geometry(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve()
    if source.suffix.lower() not in {".stp", ".step"}:
        raise ValueError("STEP geometry inspection requires a .stp or .step file")
    text = source.read_text(encoding="latin-1")
    scale_to_mm = 1.0
    if ".MILLI.,.METRE." not in text and "SI_UNIT($,.METRE.)" in text:
        scale_to_mm = 1000.0

    cylinders = []
    for match in _CYLINDER.finditer(text):
        radius = float(match.group("radius")) * scale_to_mm
        if radius > 0:
            cylinders.append({
                "step_entity": f"#{match.group('id')}",
                "placement_entity": f"#{match.group('placement')}",
                "surface_radius_mm": radius,
                "diameter_mm": radius * 2.0,
            })

    bends = []
    for index, match in enumerate(_TORUS.finditer(text), 1):
        major = float(match.group("major")) * scale_to_mm
        minor = float(match.group("minor")) * scale_to_mm
        # A pipe elbow's analytic torus normally has a major radius larger
        # than its tube-surface radius. Reject tiny fillets and spindle tori.
        if minor <= 0 or major <= minor:
            continue
        diameter = minor * 2.0
        bends.append({
            "name": f"STEP-PIPE-BEND-{index:03d}",
            "step_entity": f"#{match.group('id')}",
            "placement_entity": f"#{match.group('placement')}",
            "diameter_mm": diameter,
            "bend_radii_mm": [major],
            "centerline_bend_radius_mm": major,
            "outer_surface_radius_mm": minor,
            "r_over_d": major / diameter,
            "confidence": "HIGH",
            "basis": (
                "STEP analytic TOROIDAL_SURFACE; major radius is treated as the "
                "centerline bend radius and twice the minor radius as the pipe OD candidate"
            ),
        })

    return {
        "source_file": str(source),
        "method": "STEP_ANALYTIC_SURFACE_INFERENCE",
        "unit_scale_to_mm": scale_to_mm,
        "cylindrical_surface_count": len(cylinders),
        "toroidal_pipe_bend_count": len(bends),
        "cylinders": cylinders,
        "bends": bends,
        "limitations": [
            "STEP does not restore line number, specification, flow direction, support semantics, or design intent",
            "Each torus is accepted only as a geometric pipe-bend candidate; ambiguous accessory fillets require review",
        ],
    }
