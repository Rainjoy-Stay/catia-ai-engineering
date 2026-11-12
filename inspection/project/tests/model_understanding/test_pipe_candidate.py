import unittest

from catia_checker.model_understanding.features import score_pipe_candidate


class PipeCandidateTests(unittest.TestCase):
    def test_strong_multi_feature_candidate_is_pipe(self):
        result = score_pipe_candidate({
            "aspect_ratio_max_second": 28.4,
            "tubular_surface_ratio": 0.81,
            "diameter_variation": 0.012,
            "centerline_continuity": 0.96,
            "terminal_count": 2,
        })
        self.assertEqual(result["candidate_type"], "PIPE")
        self.assertGreater(result["confidence"], 0.8)

    def test_cylinder_faces_alone_never_force_pipe(self):
        result = score_pipe_candidate({
            "surface_statistics": {
                "face_count": 4,
                "surface_type_counts": {"CYLINDER": 4, "TORUS": 0},
                "surface_type_area_ratios": {"CYLINDER": None, "TORUS": None},
            }
        })
        self.assertEqual(result["candidate_type"], "UNKNOWN")
        self.assertLess(result["evidence_coverage"], 0.55)

    def test_high_aspect_and_tubular_only_remain_unknown(self):
        result = score_pipe_candidate({
            "aspect_ratio_max_second": 50, "tubular_surface_ratio": 0.95,
        })
        self.assertEqual(result["candidate_type"], "UNKNOWN")

    def test_missing_features_are_explained(self):
        result = score_pipe_candidate({})
        self.assertEqual(result["candidate_type"], "UNKNOWN")
        self.assertTrue(result["uncertainty"])

    def test_short_cylindrical_connector_is_not_forced_to_pipe(self):
        result = score_pipe_candidate({
            "aspect_ratio_max_second": 4.5, "tubular_surface_ratio": 0.9,
            "diameter_variation": 0, "centerline_continuity": 1, "terminal_count": 2,
        })
        self.assertEqual(result["candidate_type"], "UNKNOWN")
        self.assertFalse(result["hard_gates"]["minimum_aspect_ratio"])


if __name__ == "__main__":
    unittest.main()
