import unittest

from catia_checker.dmu_results import convert_dmu_scan
from catia_checker.models import CheckStatus, Severity


RULES = {
    "ruleset_id": "test-rules-v1",
    "dmu_clash": {"clearance_mm": 0.1, "contact_is_failure": False,
                  "clash_is_failure": True},
    "routing": {"threshold_status": "ASSUMED_PENDING_APPROVAL"},
    "required_context": {
        "hot_zone_classification": False,
        "pressure_and_temperature_metadata": True,
        "motion_envelopes": False,
        "support_and_clamp_metadata": False,
        "maintenance_removal_envelopes": False,
    },
}


def scan(conflicts, **overrides):
    payload = {
        "document": "Product1.CATProduct", "root_product": "Product1",
        "method": "CATIA_DMU_SPACE_ANALYSIS_ISOLATED_SINGLE_COMPUTE",
        "clearance_mm": 0.1, "conflicts": conflicts, "truncated": False,
        "cleanup_verified": True, "source_saved_by_tool": False,
    }
    payload.update(overrides)
    return payload


class DmuResultTests(unittest.TestCase):
    def test_clash_is_fail_and_preserves_raw_measurement(self) -> None:
        conflict = {
            "name": "干涉结果.1", "type": "CLASH", "value_mm": -15.514,
            "interference_depth_mm": 15.514, "first_product": "Tube.1",
            "second_product": "Frame.1", "rule_status": "UNFILTERED",
        }
        finding = convert_dmu_scan(scan([conflict]), RULES).findings[0]
        self.assertEqual(finding.status, CheckStatus.FAIL)
        self.assertEqual(finding.severity, Severity.S4)
        self.assertEqual(finding.measured_value, -15.514)
        self.assertEqual(finding.evidence[0].data["interference_depth_mm"], 15.514)

    def test_contact_remains_warn_without_semantic_context(self) -> None:
        conflict = {"type": "CONTACT", "value_mm": 0.0,
                    "first_product": "Tube.1", "second_product": "Clamp.1",
                    "rule_status": "UNFILTERED"}
        finding = convert_dmu_scan(scan([conflict]), RULES).findings[0]
        self.assertEqual(finding.status, CheckStatus.WARN)
        self.assertEqual(finding.severity, Severity.S2)

    def test_relationship_review_maps_to_not_evaluated(self) -> None:
        conflict = {"type": "CONTACT", "value_mm": 0.0,
                    "first_product": "Tube.1", "second_product": "Valve.1",
                    "relationship_assessment": {"decision": "REVIEW_REQUIRED",
                        "confidence": 0.3, "reason": "证据不足"}}
        finding = convert_dmu_scan(scan([conflict]), RULES).findings[0]
        self.assertEqual(finding.status, CheckStatus.NOT_EVALUATED)

    def test_normal_connection_maps_to_pass(self) -> None:
        conflict = {"type": "CONTACT", "value_mm": 0.0,
                    "first_product": "Tube.1", "second_product": "Valve.1",
                    "relationship_assessment": {"decision": "PASS_NORMAL_CONNECTION",
                        "confidence": 0.95, "reason": "接口匹配"}}
        finding = convert_dmu_scan(scan([conflict]), RULES).findings[0]
        self.assertEqual(finding.status, CheckStatus.PASS)

    def test_exempted_pair_is_not_reported_as_pass(self) -> None:
        conflict = {"type": "CONTACT", "value_mm": 0.0,
                    "first_product": "Tube.1", "second_product": "Port.1",
                    "rule_status": "EXEMPTED"}
        finding = convert_dmu_scan(scan([conflict]), RULES).findings[0]
        self.assertEqual(finding.status, CheckStatus.EXEMPTED)

    def test_allowed_contact_pair_does_not_exempt_physical_clash(self) -> None:
        conflict = {"type": "CLASH", "value_mm": -2.0,
                    "first_product": "Tube.1", "second_product": "Port.1",
                    "rule_status": "EXEMPTED"}
        finding = convert_dmu_scan(scan([conflict]), RULES).findings[0]
        self.assertEqual(finding.status, CheckStatus.FAIL)

    def test_issue_id_is_stable_when_pair_order_reverses(self) -> None:
        first = {"type": "CLASH", "value_mm": -1.0,
                 "first_product": "A.1", "second_product": "B.1"}
        second = {"type": "CLASH", "value_mm": -1.0,
                  "first_product": "B.1", "second_product": "A.1"}
        id_a = convert_dmu_scan(scan([first]), RULES).findings[0].issue_id
        id_b = convert_dmu_scan(scan([second]), RULES).findings[0].issue_id
        self.assertEqual(id_a, id_b)

    def test_truncation_and_missing_context_are_explicit(self) -> None:
        bundle = convert_dmu_scan(scan([], truncated=True), RULES)
        self.assertTrue(bundle.confidence_budget.degraded)
        self.assertIn("运动包络", bundle.confidence_budget.not_checked)
        self.assertNotIn("压力和温度元数据", bundle.confidence_budget.not_checked)
        self.assertFalse(bundle.confidence_budget.is_complete)


if __name__ == "__main__":
    unittest.main()
