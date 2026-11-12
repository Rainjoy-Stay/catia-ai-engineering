import unittest
from unittest.mock import patch

from catia_checker.model_understanding.features.support import (
    bracket_attachment_candidates, midspan_support_candidates,
)


class SupportRecognitionTests(unittest.TestCase):
    @patch("catia_checker.model_understanding.features.support.circular_interface_candidates")
    def test_radius_matched_midspan_enclosure_is_supported(self, interfaces):
        interfaces.side_effect = lambda body: ([] if body["source_id"] == "pipe" else [{
            "center_mm": [50, 0, 0], "normal": [1, 0, 0], "radius_mm": 5.2}])
        bodies = [{"source_id": "pipe"}, {"source_id": "clamp"}]
        features = {"pipe": {"dominant_radius": 5, "centerline_segments_world": [{
            "primitive_type": "LINE_AXIS", "start_mm": [0, 0, 0], "end_mm": [100, 0, 0],
            "direction": [1, 0, 0]}]}}
        result = midspan_support_candidates(bodies, features)
        self.assertEqual(result[0]["relationship_type"], "SUPPORTED")
        self.assertEqual(result[0]["object_type_candidate"], "CLAMP")

    @patch("catia_checker.model_understanding.features.support.circular_interface_candidates")
    def test_terminal_circle_is_not_misclassified_as_support(self, interfaces):
        interfaces.side_effect = lambda body: ([] if body["source_id"] == "pipe" else [{
            "center_mm": [100, 0, 0], "normal": [1, 0, 0], "radius_mm": 5.2}])
        bodies = [{"source_id": "pipe"}, {"source_id": "fitting"}]
        features = {"pipe": {"dominant_radius": 5, "centerline_segments_world": [{
            "primitive_type": "LINE_AXIS", "start_mm": [0, 0, 0], "end_mm": [100, 0, 0],
            "direction": [1, 0, 0]}]}}
        self.assertEqual(midspan_support_candidates(bodies, features), [])

    def test_compact_planar_contact_on_proven_clamp_is_bracket_candidate(self):
        bodies = [
            {"source_id": "pipe", "reference_bounds_mm": [-100, -20, -20, 100, 20, 20]},
            {"source_id": "clamp", "reference_bounds_mm": [-10, -21, -21, 10, 21, 21]},
            {"source_id": "bracket", "reference_bounds_mm": [-15, -30, -41, 15, 30, -21],
             "surface_statistics": {"face_count": 6,
                                    "surface_type_counts": {"PLANE": 6, "CYLINDER": 0, "TORUS": 0}}},
        ]
        clamps = [{"pipe_body_id": "pipe", "support_body_id": "clamp",
                   "interface_matches": [{"interface": {"radius_mm": 20}}]}]
        result = bracket_attachment_candidates(bodies, clamps)
        self.assertEqual(result[0]["object_type_candidate"], "BRACKET")
