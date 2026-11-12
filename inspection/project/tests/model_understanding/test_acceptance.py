import unittest

from catia_checker.model_understanding.productization.acceptance import (
    acceptance_markdown, evaluate_acceptance,
)


def package(pending=2, gate=True):
    return {
        "schema_version": "model-understanding-review-package.v2.0",
        "run_id": "R1", "document": "Fixture", "package_fingerprint": "abc",
        "overview": {"inspection_counts": {"ERROR": 0}, "engineering_object_count": 3,
                     "relationship_count": 2, "pipe_network_count": 1},
        "review_queue": {"pending_count": pending},
        "safety": {"semantic_regression_gate": {"passed": gate},
                   "source_model_modified": False, "fallback_available": True},
    }


class AcceptanceTests(unittest.TestCase):
    def test_accepts_with_separate_review_queue(self):
        result = evaluate_acceptance(package())
        self.assertEqual(result["release_status"], "ACCEPTED_WITH_REVIEW_QUEUE")
        self.assertEqual(result["automated_pass_count"], result["automated_check_count"])

    def test_rejects_failed_safety_gate(self):
        self.assertEqual(evaluate_acceptance(package(gate=False))["release_status"], "REJECTED")

    def test_markdown_states_review_boundary(self):
        value = package()
        text = acceptance_markdown(evaluate_acceptance(value), value)
        self.assertIn("待工程人工复核：2 项", text)
        self.assertIn("不覆盖原始识别证据", text)


if __name__ == "__main__":
    unittest.main()
