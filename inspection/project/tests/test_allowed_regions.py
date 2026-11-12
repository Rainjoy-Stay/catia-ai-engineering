import unittest

from catia_checker.allowed_regions import evaluate_allowed_region


class AllowedRegionTests(unittest.TestCase):
    def test_interface_within_depth_is_allowed(self):
        result = evaluate_allowed_region({"connection_relationship": "PIPE_FITTING",
                                          "interface_depth_mm": 2})
        self.assertEqual(result["result"], "EXPECTED_CONTACT")

    def test_deep_insertion_is_not_blanket_exempt(self):
        result = evaluate_allowed_region({"connection_relationship": "PIPE_FITTING",
                                          "interface_depth_mm": 20})
        self.assertEqual(result["reason"], "BEYOND_ALLOWED_REGION")

    def test_unknown_depth_requires_review(self):
        self.assertEqual(evaluate_allowed_region({"allowed_region": True})["result"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
