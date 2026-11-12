import unittest

from catia_checker.model_understanding.geometry import AABBSpatialIndex


class SpatialIndexTests(unittest.TestCase):
    def test_terminal_query_returns_only_nearby_bounds(self):
        index = AABBSpatialIndex([
            {"object_id": "PIPE", "coordinate_space": "WORLD", "bounds_mm": [0, 0, 0, 10, 2, 2]},
            {"object_id": "FITTING", "coordinate_space": "WORLD", "bounds_mm": [10, 0, 0, 14, 4, 4]},
            {"object_id": "CASE", "coordinate_space": "WORLD", "bounds_mm": [100, 0, 0, 200, 100, 100]},
        ])
        result = index.query_point([10, 1, 1], 5, exclude_ids=["PIPE"])
        self.assertEqual([item["object_id"] for item in result], ["FITTING"])
        self.assertEqual(result[0]["aabb_distance_lower_bound_mm"], 0)

    def test_invalid_bounds_fail_closed(self):
        with self.assertRaises(ValueError):
            AABBSpatialIndex([{"object_id": "X", "coordinate_space": "WORLD",
                               "bounds_mm": [1, 0, 0, 0, 1, 1]}])

    def test_local_step_bounds_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "WORLD"):
            AABBSpatialIndex([{"object_id": "X", "coordinate_space": "LOCAL_STEP_REPRESENTATION",
                               "bounds_mm": [0, 0, 0, 1, 1, 1]}])


if __name__ == "__main__":
    unittest.main()
