import unittest

from catia_checker.model_understanding.topology import derive_system_topology


def node(object_id, object_type="UNKNOWN"):
    return {"object_id": object_id, "engineering_object": {"object_type": object_type}}


class SystemTopologyTests(unittest.TestCase):
    def test_aggregates_network_and_finds_branch(self):
        graph = {
            "nodes": [node("P", "PIPE"), node("A"), node("B"), node("C")],
            "edges": [
                {"source_object_id": "P", "target_object_id": "A", "relationship_type": "DIRECT_INTERFACE"},
                {"source_object_id": "P", "target_object_id": "B", "relationship_type": "CONNECTED"},
                {"source_object_id": "P", "target_object_id": "C", "relationship_type": "CONNECTED"},
            ],
        }
        topology = derive_system_topology(graph)
        network = topology["pipe_networks"][0]
        self.assertEqual(network["branch_object_ids"], ["P"])
        self.assertEqual(set(network["interface_object_ids"]), {"A", "B", "C"})

    def test_does_not_bridge_disconnected_networks(self):
        graph = {
            "nodes": [node("P1", "PIPE"), node("X"), node("P2", "PIPE"), node("Y")],
            "edges": [
                {"source_object_id": "P1", "target_object_id": "X", "relationship_type": "DIRECT_INTERFACE"},
                {"source_object_id": "P2", "target_object_id": "Y", "relationship_type": "DIRECT_INTERFACE"},
            ],
        }
        self.assertEqual(derive_system_topology(graph)["summary"]["pipe_network_count"], 2)

    def test_builds_support_chain_separately(self):
        graph = {
            "nodes": [node("P", "PIPE"), node("C", "CLAMP"), node("B", "BRACKET")],
            "edges": [
                {"source_object_id": "P", "target_object_id": "C", "relationship_type": "SUPPORTED", "confidence": .95},
                {"source_object_id": "C", "target_object_id": "B", "relationship_type": "SUPPORTED", "confidence": .75},
            ],
        }
        chain = derive_system_topology(graph)["support_chains"][0]
        self.assertEqual(chain["member_object_ids"], ["B", "C", "P"])
        self.assertEqual(chain["minimum_edge_confidence"], .75)


if __name__ == "__main__":
    unittest.main()
