import unittest

from catia_checker.model_understanding.visualization import build_overlay_spec


class OverlaySpecTests(unittest.TestCase):
    def test_world_centerline_terminals_and_review_relation_are_preserved(self):
        features = {"pipe": {"classification_confidence": 0.97,
            "centerline_segments_world": [{"primitive_type": "LINE_AXIS",
                                            "start_mm": [0, 0, 0], "end_mm": [100, 0, 0]}],
            "terminal_candidates": [{"position_mm": [0, 0, 0], "direction": [-1, 0, 0],
                                     "coordinate_space": "WORLD"}]}}
        relationships = [{"pipe_body_id": "pipe", "support_body_id": "bracket",
                          "relationship_type": "SUPPORTED", "confidence": 0.75,
                          "evidence": "PLANAR_CONTACT"}]
        spec = build_overlay_spec(features, relationships)
        self.assertEqual(spec["schema_version"], "catia-overlay.v0.8")
        self.assertEqual(len(spec["layers"]["centerlines"]), 1)
        self.assertEqual(len(spec["layers"]["terminals"]), 1)
        self.assertTrue(spec["layers"]["relationships"][0]["review_required"])
        self.assertFalse(spec["display_policy"]["source_model_modified"])


if __name__ == "__main__":
    unittest.main()
