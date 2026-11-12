import unittest

from catia_checker.model_understanding.productization import build_review_package


def report(nodes=("A",), edges=(), status="NOT_EVALUATED"):
    return {
        "run_id": "R1", "document": "Model",
        "counts": {status: 1},
        "findings": [{"issue_id": "I1", "status": status, "object_a": "A", "object_b": "B"}],
        "audit": {"semantic_regression_gate": {"passed": True}, "source_model_modified": False},
        "model_understanding_connection_graph": {
            "nodes": [{"object_id": item, "stable_object_id": item} for item in nodes],
            "edges": list(edges), "system_topology": {"summary": {"pipe_network_count": 1}},
        },
    }


class ReviewPackageTests(unittest.TestCase):
    def test_builds_pending_review_queue(self):
        package = build_review_package(report())
        self.assertEqual(package["review_queue"]["pending_count"], 1)
        self.assertTrue(package["safety"]["fallback_available"])

    def test_applies_separate_human_verification(self):
        verification = {"records": [{"target_id": "I1", "decision": "CONFIRMED"}]}
        package = build_review_package(report(), verifications=verification)
        self.assertEqual(package["review_queue"]["verified_count"], 1)

    def test_computes_stable_incremental_delta(self):
        package = build_review_package(report(nodes=("A", "B")), previous_report=report(nodes=("A",)))
        self.assertEqual(package["incremental_reinspection"]["added_object_ids"], ["B"])
        self.assertTrue(package["incremental_reinspection"]["changed"])


if __name__ == "__main__":
    unittest.main()
