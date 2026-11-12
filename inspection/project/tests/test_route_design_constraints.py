import unittest
from pathlib import Path

from catia_checker.route_design_constraints import load_route_design_cases


class RouteDesignConstraintTests(unittest.TestCase):
    def test_reference_standard_generates_editable_design_cases(self):
        config = Path(__file__).parents[1] / "config" / "route-design-current.json"
        raw, cases = load_route_design_cases(config)
        self.assertEqual(raw["standard"]["policy"], "REFERENCE_ONLY")
        self.assertEqual({case.diameter_mm for case in cases}, {4.0})
        self.assertEqual({case.bend_radius_mm for case in cases}, {10, 12, 14, 16, 20, 24})
        self.assertTrue(any(case.preferred_radius for case in cases))


if __name__ == "__main__":
    unittest.main()
