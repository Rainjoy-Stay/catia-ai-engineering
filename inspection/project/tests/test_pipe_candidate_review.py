import unittest

from catia_checker.pipe_candidate_review import review_pipe_candidates


class PipeCandidateReviewTests(unittest.TestCase):
    def test_keeps_curved_and_slender_composite_but_excludes_straight(self):
        result = review_pipe_candidates([
            {"source_body_index": 10, "candidate": {
                "geometry_kind": "STRAIGHT_CYLINDRICAL_EXTERIOR_CANDIDATE",
                "reason": "COAXIAL_FACES_FULL_OUTER_AREA_AND_NORMAL_ENDS"}},
            {"source_body_index": 20, "bounds_mm": {"min": [0, 0, 0], "max": [30, 3, 2]},
             "candidate": {"geometry_kind": "UNDETERMINED",
                           "reason": "COMPOSITE_EXTERIOR_REQUIRES_ROUTE_REVIEW"}},
            {"source_body_index": 30, "candidate": {
                "geometry_kind": "BSPLINE_CIRCULAR_SWEEP_EXTERIOR_CANDIDATE",
                "outer_diameter_mm": 6.0, "centerline_bend_radius_mm": 18.0,
                "minimum_radius_ratio_r_over_d": 3.0}},
        ])
        self.assertEqual([item["body_index"] for item in result["candidates"]], [30, 20])
        self.assertEqual(result["excluded_straight_cylinder_count"], 1)
        self.assertTrue(all(item["status"] == "NOT_EVALUATED" for item in result["candidates"]))

    def test_rejects_stubby_composite_shape(self):
        result = review_pipe_candidates([{
            "source_body_index": 40,
            "bounds_mm": {"min": [0, 0, 0], "max": [4, 3, 3]},
            "candidate": {"geometry_kind": "UNDETERMINED",
                          "reason": "COMPOSITE_EXTERIOR_REQUIRES_ROUTE_REVIEW"},
        }])
        self.assertEqual(result["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
