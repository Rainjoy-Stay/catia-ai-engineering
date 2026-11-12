import json
from pathlib import Path
import tempfile
import unittest

from catia_checker.model_understanding.geometry.signatures import stable_body_id
from catia_checker.model_understanding.graph import ConnectionGraphRepository, GraphQueries


class GraphRepositoryTests(unittest.TestCase):
    def graph(self):
        return {"schema_version": "connection-graph.v0.4",
                "nodes": [{"object_id": "#1", "aliases": ["Pipe", "BODY_A"]},
                          {"object_id": "#2", "aliases": ["Clamp", "BODY_B"]}],
                "edges": [{"source_object_id": "#1", "target_object_id": "#2",
                           "relationship_type": "SUPPORTED"}]}

    def test_signature_does_not_depend_on_step_entity_id(self):
        body = {"source_id": "#1", "product_name": "Pipe", "geometry_kind": "SOLID",
                "closure_state": "CLOSED", "reference_bounds_mm": [0, 0, 0, 100, 10, 10],
                "surface_statistics": {"surface_type_counts": {"CYLINDER": 1}},
                "tubular_features": {"radius_clusters": [{"radius": 5}]}, "face_ids": ["#9"]}
        changed_entity_numbers = {**body, "source_id": "#999", "face_ids": ["#500"]}
        self.assertEqual(stable_body_id(body), stable_body_id(changed_entity_numbers))

    def test_save_load_query_and_separate_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = ConnectionGraphRepository(Path(folder) / "graph.json")
            repository.save_graph(self.graph())
            graph = repository.load_graph()
            record = repository.record_verification(
                target_type="RELATIONSHIP", target_id="#1|#2", decision="CONFIRMED",
                reviewer="tester", note="fixture")
            stored_graph = json.loads(repository.graph_path.read_text(encoding="utf-8"))
            verification = json.loads(repository.verification_path.read_text(encoding="utf-8"))
        self.assertEqual(GraphQueries(graph).neighbors("#1", "SUPPORTED")[0]["neighbor"]["object_id"], "#2")
        self.assertNotIn("verification", stored_graph)
        self.assertEqual(verification["records"][0], record)

    def test_accepts_v11_system_topology_graph(self):
        graph = {**self.graph(), "schema_version": "connection-graph.v1.1",
                 "system_topology": {"schema_version": "system-topology.v1.1"}}
        with tempfile.TemporaryDirectory() as folder:
            repository = ConnectionGraphRepository(Path(folder) / "graph.json")
            repository.save_graph(graph)
            loaded = repository.load_graph()
        self.assertEqual(loaded["schema_version"], "connection-graph.v1.1")


if __name__ == "__main__":
    unittest.main()
