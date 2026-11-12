"""Pure post-create verification for native CATIA Arrangement Runs."""

from __future__ import annotations

from math import dist
from typing import Any, Sequence


def verify_created_route(
    inspection: dict[str, Any], expected_points: Sequence[Sequence[float]],
    expected_radii: Sequence[float], expected_diameter: float,
    tolerance_mm: float = 1e-4,
) -> dict[str, Any]:
    issues: list[str] = []
    actual_diameter = inspection.get("SectionDiameter")
    if actual_diameter is None or abs(float(actual_diameter)-expected_diameter) > tolerance_mm:
        issues.append("SECTION_DIAMETER_MISMATCH")
    nodes = inspection.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != len(expected_points):
        issues.append("NODE_COUNT_MISMATCH")
        nodes = []
    point_errors = []
    for index, (node, expected) in enumerate(zip(nodes, expected_points), 1):
        actual = node.get("point")
        if not isinstance(actual, list) or len(actual) != 3:
            issues.append(f"NODE_POINT_UNAVAILABLE:{index}")
            continue
        error = dist(tuple(map(float, actual)), tuple(map(float, expected)))
        point_errors.append(error)
        if error > tolerance_mm:
            issues.append(f"NODE_POINT_MISMATCH:{index}:{error:.9g}")
    radius_errors = []
    for offset, expected in enumerate(expected_radii, 2):
        if offset-1 >= len(nodes) or nodes[offset-1].get("bend_radius") is None:
            issues.append(f"BEND_RADIUS_UNAVAILABLE:{offset}")
            continue
        error = abs(float(nodes[offset-1]["bend_radius"])-float(expected))
        radius_errors.append(error)
        if error > tolerance_mm:
            issues.append(f"BEND_RADIUS_MISMATCH:{offset}:{error:.9g}")
    return {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
        "maximum_node_error_mm": max(point_errors, default=None),
        "maximum_radius_error_mm": max(radius_errors, default=None),
        "tolerance_mm": tolerance_mm,
    }
