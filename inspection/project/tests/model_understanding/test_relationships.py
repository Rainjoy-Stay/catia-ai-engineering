import unittest

from catia_checker.model_understanding.relationships import (
    build_connection_graph, connection_relation_for_pair, terminal_neighborhood_candidates,
)


class RelationshipCandidateTests(unittest.TestCase):
    def test_world_terminal_finds_nearby_body_but_does_not_claim_connection(self):
        bodies = [
            {"source_id": "pipe", "reference_bounds_mm": [0, 0, 0, 100, 10, 10],
             "reference_bounds_coordinate_space": "WORLD"},
            {"source_id": "flange", "reference_bounds_mm": [99, -5, -5, 110, 15, 15],
             "reference_bounds_coordinate_space": "WORLD"},
        ]
        features = {"pipe": {"dominant_diameter": 10, "terminal_candidates": [
            {"position_mm": [100, 5, 5], "coordinate_space": "WORLD"}]}}
        candidate = terminal_neighborhood_candidates(bodies, features)[0]
        self.assertEqual(candidate["nearby_body_candidates"][0]["object_id"], "flange")
        self.assertEqual(candidate["relationship_state"], "CANDIDATE_ONLY")

    def test_local_terminal_is_not_queried(self):
        bodies = [{"source_id": "pipe", "reference_bounds_mm": [0, 0, 0, 1, 1, 1],
                   "reference_bounds_coordinate_space": "WORLD"}]
        features = {"pipe": {"terminal_candidates": [
            {"position_mm": [0, 0, 0], "coordinate_space": "LOCAL_STEP_REPRESENTATION"}]}}
        self.assertEqual(terminal_neighborhood_candidates(bodies, features), [])

    def test_only_unique_direct_interface_becomes_spacing_exemption(self):
        relationships = [
            {"pipe_body_id": "pipe", "terminal_index": 0,
             "relationship_state": "PROBABLE_DIRECT_INTERFACE",
             "direct_interface_body_ids": ["flange"]},
            {"pipe_body_id": "pipe", "terminal_index": 1,
             "relationship_state": "CANDIDATE_ONLY", "direct_interface_body_ids": []},
        ]
        graph = build_connection_graph([{"source_id": "pipe"}, {"source_id": "flange"}],
                                       relationships)
        self.assertEqual(graph["spacing_exemption_pairs"], [["flange", "pipe"]])
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(len(graph["unresolved_terminals"]), 1)
        relation = connection_relation_for_pair(graph, "pipe", "flange")
        self.assertTrue(relation["unique_interface_match"])

    def test_supported_edge_keeps_its_relation_type(self):
        graph = {"nodes": [{"object_id": "p", "aliases": ["Pipe"]},
                           {"object_id": "c", "aliases": ["Clamp"]}],
                 "edges": [{"source_object_id": "p", "target_object_id": "c",
                            "relationship_type": "SUPPORTED", "confidence": 0.9,
                            "evidence": "COAXIAL_RADIUS_MATCHED_MIDSPAN_ENCLOSURE"}]}
        relation = connection_relation_for_pair(graph, "Pipe", "Clamp")
        self.assertEqual(relation["relationship_type"], "SUPPORTED")
        self.assertFalse(relation["unique_interface_match"])

    def test_direct_flange_edge_selects_flange_profile(self):
        graph = {"nodes": [{"object_id": "p", "aliases": ["Pipe"]},
                           {"object_id": "f", "aliases": ["Flange"]}],
                 "edges": [{"source_object_id": "p", "target_object_id": "f",
                            "source_object_type": "PIPE", "target_object_type": "FLANGE",
                            "relationship_type": "DIRECT_INTERFACE", "evidence": "GEOMETRY"}]}
        relation = connection_relation_for_pair(graph, "Pipe", "Flange")
        self.assertEqual(relation["inspection_profile"], "FLANGE_INTERFACE")


if __name__ == "__main__":
    unittest.main()
