import unittest

from catia_checker.models import CheckStatus
from catia_checker.routing_rules import evaluate_bend_radius, general_clearance_mm, validate_rules


class RoutingRuleTests(unittest.TestCase):
    def test_general_clearance_uses_routing_value(self) -> None:
        rules = {
            "dmu_clash": {"clearance_mm": 0.1},
            "routing": {"minimum_general_clearance_mm": 10.0},
        }
        self.assertEqual(general_clearance_mm(rules), 10.0)

    def test_bend_radius_fails_when_approved_limit_is_not_met(self) -> None:
        rules = {"routing": {
            "minimum_bend_radius_ratio_r_over_d": 3.0,
            "threshold_status": "APPROVED",
        }}
        finding = evaluate_bend_radius({
            "name": "Tube.1", "diameter_mm": 40.0, "bend_radii_mm": [80.0, 160.0],
        }, rules)
        self.assertEqual(finding.status, CheckStatus.FAIL)
        self.assertEqual(finding.measured_value, 2.0)

    def test_assumed_limit_warns_instead_of_claiming_compliance(self) -> None:
        rules = {"routing": {
            "minimum_bend_radius_ratio_r_over_d": 3.0,
            "threshold_status": "ASSUMED_PENDING_APPROVAL",
        }}
        finding = evaluate_bend_radius({
            "name": "Tube.2", "diameter_mm": 40.0, "bend_radii_mm": [160.0],
        }, rules)
        self.assertEqual(finding.status, CheckStatus.WARN)
        self.assertEqual(finding.measured_value, 4.0)

    def test_missing_geometry_is_not_evaluated(self) -> None:
        rules = {"routing": {
            "minimum_bend_radius_ratio_r_over_d": 3.0,
            "threshold_status": "APPROVED",
        }}
        finding = evaluate_bend_radius({
            "name": "StraightTube.1", "diameter_mm": 40.0, "bend_radii_mm": [],
        }, rules)
        self.assertEqual(finding.status, CheckStatus.NOT_EVALUATED)

    def test_absolute_bend_radius_supports_centimeter_rule_after_mm_conversion(self) -> None:
        rules = {"routing": {
            "bend_radius_mode": "absolute_mm",
            "minimum_bend_radius_mm": 100.0,
            "threshold_status": "APPROVED",
        }}
        finding = evaluate_bend_radius({
            "name": "Tube.3", "diameter_mm": None, "bend_radii_mm": [90.0, 120.0],
        }, rules)
        self.assertEqual(finding.status, CheckStatus.FAIL)
        self.assertEqual(finding.measured_value, 90.0)
        self.assertEqual(finding.unit, "mm")

    def test_missing_bend_rule_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_bend_radius({
                "name": "Tube.4", "diameter_mm": 20.0, "bend_radii_mm": [80.0],
            }, {"routing": {"threshold_status": "APPROVED"}})

    def test_ruleset_validation_rejects_unknown_approval(self) -> None:
        rules = {
            "schema_version": "1.1.0", "ruleset_id": "test", 
            "dmu_clash": {"clearance_mm": 0.1, "max_conflicts": 10},
            "routing": {"threshold_status": "UNKNOWN", "bend_radius_mode": "absolute_mm",
                        "minimum_bend_radius_mm": 100, "minimum_general_clearance_mm": 10,
                        "minimum_hot_zone_clearance_mm": 25},
        }
        with self.assertRaises(ValueError):
            validate_rules(rules)

    def test_hb_standard_profile_uses_editable_minimum_ratio(self) -> None:
        rules = {"routing": {
            "bend_radius_mode": "standard_profile",
            "bend_radius_profile_file": "standards/HB_4-55-2002_bend_radius.json",
            "bend_radius_overrides": {"minimum_ratio_r_over_d": None},
            "threshold_status": "APPROVED",
            "standard_reference": "HB 4-55-2002",
        }}
        finding = evaluate_bend_radius({
            "name": "HB-Tube", "diameter_mm": 20.0, "bend_radii_mm": [39.0],
        }, rules)
        self.assertEqual(finding.status, CheckStatus.FAIL)
        self.assertEqual(finding.limit_value, 2.0)

    def test_hb_high_pressure_recommendation_warns_without_forcing_failure(self) -> None:
        rules = {"routing": {
            "bend_radius_mode": "standard_profile",
            "bend_radius_profile_file": "standards/HB_4-55-2002_bend_radius.json",
            "bend_radius_overrides": {"minimum_ratio_r_over_d": None},
            "threshold_status": "APPROVED",
        }}
        finding = evaluate_bend_radius({
            "name": "HP-Tube", "diameter_mm": 20.0, "bend_radii_mm": [60.0],
            "working_pressure_mpa": 16.0,
        }, rules)
        self.assertEqual(finding.status, CheckStatus.WARN)
        self.assertIn("建议", finding.message)

    def test_project_override_changes_minimum_without_code_change(self) -> None:
        rules = {"routing": {
            "bend_radius_mode": "standard_profile",
            "bend_radius_profile_file": "standards/HB_4-55-2002_bend_radius.json",
            "bend_radius_overrides": {"minimum_ratio_r_over_d": 2.5},
            "threshold_status": "APPROVED",
        }}
        finding = evaluate_bend_radius({
            "name": "Override-Tube", "diameter_mm": 20.0, "bend_radii_mm": [45.0],
        }, rules)
        self.assertEqual(finding.status, CheckStatus.FAIL)
        self.assertEqual(finding.limit_value, 2.5)


if __name__ == "__main__":
    unittest.main()
