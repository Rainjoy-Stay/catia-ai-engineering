import unittest

from catia_checker.model_understanding.semantics.reasoner import SemanticReasoner


class SemanticReasonerTests(unittest.TestCase):
    def test_valid_result_must_cite_supplied_fact(self):
        reasoner = SemanticReasoner(lambda cases: [{
            "classification": "BRACKET", "confidence": 0.82,
            "evidence_refs": ["plane_face_ratio"], "reason": "平面安装结构候选",
            "uncertainty": ["载荷路径未知"],
        }])
        result = reasoner.judge_objects([{"object_id": "b", "facts": {"plane_face_ratio": 1.0}}])[0]
        self.assertEqual(result["classification"], "BRACKET")
        self.assertEqual(result["decision_source"], "AI_VALIDATED")

    def test_unknown_evidence_reference_fails_closed(self):
        reasoner = SemanticReasoner(lambda cases: [{
            "classification": "CLAMP", "confidence": 0.99,
            "evidence_refs": ["invented_contact_area"], "reason": "猜测",
            "uncertainty": [],
        }])
        result = reasoner.judge_objects([{"object_id": "x", "facts": {"plane_face_ratio": 1.0}}])[0]
        self.assertEqual(result["classification"], "UNKNOWN")
        self.assertEqual(result["decision_source"], "CONSERVATIVE_FALLBACK")

    def test_extra_disposition_field_is_rejected(self):
        reasoner = SemanticReasoner(lambda cases: [{
            "classification": "CONNECTED", "confidence": 0.99,
            "evidence_refs": ["distance_mm"], "reason": "接口一致", "uncertainty": [],
            "inspection_disposition": "EXEMPT",
        }])
        result = reasoner.judge_relationships([{"pair_id": "a|b", "facts": {"distance_mm": 0.0}}])[0]
        self.assertEqual(result["classification"], "UNKNOWN")

    def test_no_judge_never_invents_semantics(self):
        result = SemanticReasoner(None).judge_objects([{"object_id": "x", "facts": {}}])[0]
        self.assertEqual(result["classification"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
