import unittest

from catia_checker.model_understanding.semantic_learning import SCHEMA_VERSION, predict, train


def row(object_id, object_type, system_type, **features):
    return {"schema_version": SCHEMA_VERSION, "object_id": object_id, "features": features,
            "labels": {"object_type": object_type, "system_type": system_type},
            "label_source": "ENGINEER_APPROVED"}


class SemanticLearningTests(unittest.TestCase):
    def setUp(self):
        self.model = train([
            row("F1", "PIPE", "FUEL", instance_name="燃油供油管", line_id="FUEL-101",
                outside_diameter_mm=12, connected_equipment=["fuel pump", "injector"]),
            row("F2", "PIPE", "FUEL", instance_name="fuel manifold", line_id="FUEL-202",
                outside_diameter_mm=12, connected_equipment=["fuel valve"]),
            row("H1", "PIPE", "HYDRAULIC", instance_name="液压回油管", line_id="HYD-301",
                outside_diameter_mm=8, connected_equipment=["hydraulic actuator"]),
            row("H2", "PIPE", "HYDRAULIC", instance_name="hydraulic pressure tube", line_id="HYD-302",
                outside_diameter_mm=8, connected_equipment=["hydraulic pump"]),
        ])

    def test_predicts_system_with_context(self):
        sample = {"schema_version": SCHEMA_VERSION, "object_id": "X", "features": {
            "instance_name": "燃油支管", "line_id": "FUEL-999", "outside_diameter_mm": 12,
            "connected_equipment": ["fuel valve"]}}
        result = predict(self.model, sample, confidence_threshold=0.6)
        self.assertEqual(result["predictions"]["system_type"]["label"], "FUEL")

    def test_geometry_alone_cannot_claim_fluid_system(self):
        sample = {"schema_version": SCHEMA_VERSION, "object_id": "X", "features": {
            "outside_diameter_mm": 12, "length_mm": 400}}
        result = predict(self.model, sample, confidence_threshold=0.5)
        self.assertEqual(result["predictions"]["system_type"]["label"], "UNKNOWN")
        self.assertEqual(result["predictions"]["system_type"]["reason"], "SYSTEM_CONTEXT_REQUIRED")

    def test_rare_label_is_held_for_review(self):
        model = train([row("V1", "VALVE", "FUEL", system_tag="FUEL")])
        sample = {"schema_version": SCHEMA_VERSION, "object_id": "X",
                  "features": {"system_tag": "FUEL"}}
        result = predict(model, sample, confidence_threshold=0.5)
        self.assertEqual(result["predictions"]["object_type"]["reason"],
                         "INSUFFICIENT_LABEL_EXAMPLES")


if __name__ == "__main__":
    unittest.main()

