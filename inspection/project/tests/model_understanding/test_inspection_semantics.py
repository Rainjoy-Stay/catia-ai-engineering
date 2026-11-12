import unittest

from catia_checker.model_understanding.integration import derive_inspection_disposition


class InspectionSemanticTests(unittest.TestCase):
    def test_clash_always_fails_even_with_connected_relation(self):
        result = derive_inspection_disposition(
            {"type": "CLASH"}, {"relation_type": "CONNECTED", "confidence": 1.0})
        self.assertEqual(result["disposition"], "INTERFERENCE_FAIL")

    def test_supported_contact_uses_support_policy(self):
        result = derive_inspection_disposition(
            {"type": "CONTACT"}, {"relation_type": "SUPPORTED", "confidence": 0.95})
        self.assertEqual(result["disposition"], "SUPPORT_CHECK")

    def test_low_confidence_contact_fails_closed(self):
        result = derive_inspection_disposition(
            {"type": "CONTACT"}, {"relation_type": "SUPPORTED", "confidence": 0.75})
        self.assertEqual(result["disposition"], "CONSERVATIVE_FALLBACK")

    def test_positive_clearance_stays_standard_spacing(self):
        result = derive_inspection_disposition(
            {"type": "CLEARANCE"}, {"relation_type": "SUPPORTED", "confidence": 0.99})
        self.assertEqual(result["disposition"], "STANDARD_SPACING")

    def test_connection_profile_is_preserved_for_rule_dispatch(self):
        result = derive_inspection_disposition(
            {"type": "CONTACT"}, {"relation_type": "DIRECT_INTERFACE", "confidence": 0.95,
                                  "inspection_profile": "FLANGE_INTERFACE"})
        self.assertEqual(result["disposition"], "CONNECTION_CHECK")
        self.assertEqual(result["inspection_profile"], "FLANGE_INTERFACE")

    def test_adapter_wrapped_profile_is_preserved(self):
        result = derive_inspection_disposition(
            {"type": "CONTACT"}, {"relation_type": "DIRECT_INTERFACE", "confidence": 0.95,
                                  "metadata": {"raw_ai_metadata": {
                                      "inspection_profile": "FITTING_INTERFACE"}}})
        self.assertEqual(result["inspection_profile"], "FITTING_INTERFACE")


if __name__ == "__main__":
    unittest.main()
