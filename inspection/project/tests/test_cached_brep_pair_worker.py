import unittest

from tools.inspect_cached_brep_pair import inspect_pair


class FakeModel:
    def __init__(self, distance_mm):
        self.distance_mm = distance_mm
        self.common_calls = 0

    def distance(self, first, second):
        return {"minimum_distance_mm": self.distance_mm, "exact_brep": True}

    def common_volume(self, first, second):
        self.common_calls += 1
        return {"intersection_volume_mm3": 3.0, "exact_brep": True}


class CachedBrepPairWorkerTests(unittest.TestCase):
    def test_positive_gap_skips_boolean_common(self):
        model = FakeModel(0.25)
        result = inspect_pair(model, common_volume_distance_threshold_mm=1e-5)
        self.assertEqual(model.common_calls, 0)
        self.assertEqual(result["common"]["intersection_volume_mm3"], 0.0)
        self.assertFalse(result["common"]["boolean_computed"])

    def test_contact_candidate_keeps_boolean_common(self):
        model = FakeModel(0.0)
        result = inspect_pair(model, common_volume_distance_threshold_mm=1e-5)
        self.assertEqual(model.common_calls, 1)
        self.assertEqual(result["common"]["intersection_volume_mm3"], 3.0)
        self.assertTrue(result["common"]["boolean_computed"])


if __name__ == "__main__":
    unittest.main()
