import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from route_planning_tool import RoutePlanningTool


class RoutePlanningToolTests(unittest.TestCase):
    def test_exposes_offline_and_active_product_tools(self) -> None:
        definitions = {item["name"]: item for item in RoutePlanningTool().get_tool_definitions()}
        self.assertIn("catia_plan_orthogonal_route", definitions)
        self.assertIn("catia_plan_route_in_active_product", definitions)
        active = definitions["catia_plan_route_in_active_product"]["inputSchema"]
        self.assertIn("obstacle_component_names", active["required"])

    def test_offline_tool_explicitly_reports_no_mutation(self) -> None:
        result = json.loads(RoutePlanningTool().execute("catia_plan_orthogonal_route", {
            "start": {"point": [0, 0, 0], "direction": [1, 0, 0]},
            "goal": {"point": [50, 0, 0], "direction": [-1, 0, 0]},
            "grid_size_mm": 10,
            "bend_radius_mm": 10,
            "candidate_count": 1,
        }))
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["mutation"], "NONE")
        self.assertIn("catia_tubing_create_validated_arrangement_run", result["next_operation"])

    def test_active_product_tool_fails_closed_without_connection(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "connection is unavailable"):
            RoutePlanningTool().execute("catia_plan_route_in_active_product", {
                "start": {"point": [0, 0, 0], "direction": [1, 0, 0]},
                "goal": {"point": [50, 0, 0], "direction": [-1, 0, 0]},
                "obstacle_component_names": ["Equipment.1"],
                "grid_size_mm": 10,
            })


if __name__ == "__main__":
    unittest.main()
