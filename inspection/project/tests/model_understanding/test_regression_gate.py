import unittest

from catia_checker.model_understanding.integration.regression_gate import validate_semantic_report


def report_for(conflict_type, disposition, status, confidence=1.0):
    return {
        "source": {"returned_conflict_count": 1},
        "counts": {status: 1},
        "findings": [{
            "issue_id": "X-1", "status": status,
            "evidence": [{"kind": "CATIA_CLASH", "data": {
                "type": conflict_type,
                "relationship_assessment": {"confidence": confidence},
                "inspection_disposition": {"disposition": disposition},
            }}],
        }],
    }


class RegressionGateTests(unittest.TestCase):
    def test_accepts_safe_clash_failure(self):
        result = validate_semantic_report(report_for("CLASH", "INTERFERENCE_FAIL", "FAIL"))
        self.assertTrue(result["passed"])

    def test_rejects_clash_bypass(self):
        result = validate_semantic_report(report_for("CLASH", "CONNECTION_CHECK", "PASS"))
        self.assertFalse(result["passed"])
        self.assertIn("CLASH_NOT_FAILED", {item["code"] for item in result["violations"]})

    def test_rejects_low_confidence_pass(self):
        result = validate_semantic_report(report_for("CONTACT", "SUPPORT_CHECK", "PASS", 0.7))
        self.assertFalse(result["passed"])
        self.assertIn("LOW_CONFIDENCE_PASS", {item["code"] for item in result["violations"]})

    def test_requires_fallback_review(self):
        result = validate_semantic_report(report_for("CONTACT", "CONSERVATIVE_FALLBACK", "WARN", 0.2))
        self.assertFalse(result["passed"])
        self.assertIn("FALLBACK_NOT_REVIEWED", {item["code"] for item in result["violations"]})


if __name__ == "__main__":
    unittest.main()
