import unittest

from catia_checker.component_relationships import (
    RelationshipDecision, build_pair_context, conservative_assessment,
    validate_ai_assessment,
)


class ComponentRelationshipTests(unittest.TestCase):
    def context(self, kind="CONTACT", model="CATIA"):
        return build_pair_context({
            "type": kind, "value_mm": 0.0,
            "first_product": "PipeA", "second_product": "ValveB",
        }, model_type=model)

    def test_positive_clearance_keeps_threshold_check(self):
        result = conservative_assessment(self.context("CLEARANCE"))
        self.assertEqual(result.decision, RelationshipDecision.CHECK_CLEARANCE)

    def test_contact_without_semantics_requires_review(self):
        result = conservative_assessment(self.context("CONTACT", "STEP"))
        self.assertEqual(result.decision, RelationshipDecision.REVIEW_REQUIRED)

    def test_contact_with_unique_geometry_graph_interface_is_normal_connection(self):
        context = build_pair_context({
            "type": "CONTACT", "value_mm": 0.0,
            "first_product": "PipeA", "second_product": "FlangeB",
            "assembly_relation": {
                "relationship_type": "DIRECT_INTERFACE",
                "evidence": "COINCIDENT_CIRCULAR_INTERFACE",
                "unique_interface_match": True,
            },
        }, model_type="STEP")
        result = conservative_assessment(context)
        self.assertEqual(result.decision, RelationshipDecision.PASS_NORMAL_CONNECTION)
        self.assertEqual(result.source, "DETERMINISTIC_GEOMETRY_V0.4")

    def test_high_confidence_pipe_clamp_support_contact_passes(self):
        context = build_pair_context({
            "type": "CONTACT", "first_product": "Pipe", "second_product": "Clamp",
            "assembly_relation": {"relationship_type": "SUPPORTED", "confidence": 0.9,
                                  "evidence": "COAXIAL_RADIUS_MATCHED_MIDSPAN_ENCLOSURE"},
        }, model_type="STEP")
        result = conservative_assessment(context)
        self.assertEqual(result.decision, RelationshipDecision.PASS_NORMAL_CONNECTION)
        self.assertEqual(result.relation_type, "SUPPORTED")

    def test_low_confidence_bracket_support_stays_review(self):
        context = build_pair_context({
            "type": "CONTACT", "first_product": "Clamp", "second_product": "Bracket",
            "assembly_relation": {"relationship_type": "SUPPORTED", "confidence": 0.75,
                                  "evidence": "PLANAR_COMPACT_BODY_CONTACTING_PROVEN_CLAMP"},
        }, model_type="STEP")
        self.assertEqual(conservative_assessment(context).decision,
                         RelationshipDecision.REVIEW_REQUIRED)

    def test_ai_can_confirm_well_evidenced_contact(self):
        result = validate_ai_assessment(self.context(), {
            "decision": "PASS_NORMAL_CONNECTION", "confidence": 0.93,
            "reason": "端面、轴线和接口一致", "key_evidence": ["端面同心", "原生连接器已连接"],
            "relation_type": "PIPE_TO_VALVE",
        })
        self.assertEqual(result.decision, RelationshipDecision.PASS_NORMAL_CONNECTION)

    def test_deterministic_source_is_preserved_through_validation(self):
        value = conservative_assessment(build_pair_context({
            "type": "CONTACT", "first_product": "PipeA", "second_product": "WeldB",
            "assembly_relation": {"relationship_type": "DIRECT_INTERFACE",
                                  "evidence": "COINCIDENT_CIRCULAR_INTERFACE",
                                  "unique_interface_match": True},
        }, model_type="STEP")).to_dict()
        result = validate_ai_assessment(self.context(), value)
        self.assertEqual(result.source, "DETERMINISTIC_GEOMETRY_V0.4")

    def test_clash_cannot_be_auto_passed(self):
        result = validate_ai_assessment(self.context("CLASH"), {
            "decision": "PASS_NORMAL_CONNECTION", "confidence": 0.99,
            "reason": "可能是插接", "key_evidence": ["名称像接头"],
        })
        self.assertEqual(result.decision, RelationshipDecision.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
