import unittest

from catia_checker.shell_health import build_shell_health, classify_shell_health


class ShellHealthTests(unittest.TestCase):
    def test_open_zero_volume_shell_is_reviewed_and_retained(self):
        result = classify_shell_health({"source_id": "S1", "geometry_kind": "SHELL",
                                        "closure_state": "OPEN", "volume_mm3": 0})
        self.assertEqual(result["result"], "REVIEW")
        self.assertTrue(result["participates_in_spatial_checks"])
        self.assertIn("OPEN_SHELL", result["issues"])

    def test_invalid_non_manifold_is_low_reliability(self):
        result = classify_shell_health({"source_id": "S2", "geometry_kind": "SHELL",
                                        "valid": False, "non_manifold": True})
        self.assertEqual(result["model_reliability"], "LOW")

    def test_healthy_closed_shell_passes(self):
        result = build_shell_health([{"source_id": "S3", "geometry_kind": "SHELL",
                                      "closure_state": "CLOSED", "volume_mm3": 0}])
        self.assertEqual((result["model_reliability"], result["review_count"]), ("HIGH", 0))


if __name__ == "__main__":
    unittest.main()
