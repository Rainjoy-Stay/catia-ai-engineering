import unittest

from catia_checker.conversion_reliability import conversion_signal


class ConversionReliabilityTests(unittest.TestCase):
    def test_hollow_role_imported_as_solid_is_review(self):
        result = conversion_signal({"source_id": "S1", "geometry_kind": "SOLID",
                                    "expected_hollow": True, "inner_surface_present": False})
        self.assertEqual((result["result"], result["conversion_issue"]), ("REVIEW", "HOLLOW_TO_SOLID"))

    def test_evidenced_inner_boundary_is_not_flagged(self):
        result = conversion_signal({"source_id": "S2", "geometry_kind": "SOLID",
                                    "expected_hollow": True, "inner_surface_present": True})
        self.assertFalse(result["suspected_conversion_error"])

    def test_evidence_raises_explainable_confidence(self):
        result = conversion_signal({"source_id": "S3", "geometry_kind": "SOLID",
                                    "expected_hollow": True, "inner_surface_present": False,
                                    "outer_radius_mm": 10, "inner_radius_mm": 8,
                                    "wall_thickness_mm": 2, "contained_pipe": True})
        self.assertEqual(result["confidence"], "HIGH")


if __name__ == "__main__":
    unittest.main()
