import unittest

from catia_checker.model_understanding.objects import classify_engineering_objects


class EngineeringObjectTests(unittest.TestCase):
    def test_pipe_and_clamp_require_qualified_evidence(self):
        bodies = [{"source_id": "p"}, {"source_id": "c"}, {"source_id": "x"}]
        scores = {"p": {"candidate_type": "PIPE", "confidence": 0.91,
                        "classifier": "DETERMINISTIC_MULTI_FEATURE_V0.2",
                        "evidence": ["aspect_ratio=20"], "uncertainty": []}}
        supports = [{"support_body_id": "c", "confidence": 0.9,
                     "evidence": "COAXIAL_RADIUS_MATCHED_MIDSPAN_ENCLOSURE",
                     "object_type_candidate": "CLAMP"}]
        result = {item["object_id"]: item for item in
                  classify_engineering_objects(bodies, scores, supports)}
        self.assertEqual(result["p"]["object_type"], "PIPE")
        self.assertEqual(result["c"]["object_type"], "CLAMP")
        self.assertEqual(result["x"]["object_type"], "UNKNOWN")

    def test_names_alone_do_not_force_classification(self):
        result = classify_engineering_objects(
            [{"source_id": "x", "product_name": "Definitely-A-Bracket"}], {}, [])[0]
        self.assertEqual(result["object_type"], "UNKNOWN")

    def test_flange_requires_disk_and_analytic_face_evidence(self):
        body = {"source_id": "f", "reference_bounds_mm": [0, 0, 0, 150, 150, 50],
                "surface_statistics": {"surface_type_counts": {
                    "PLANE": 3, "CYLINDER": 2, "CONE": 2, "TORUS": 0}}}
        result = classify_engineering_objects([body], {}, [], [{
            "source_object_id": "p", "target_object_id": "f", "relationship_type": "DIRECT_INTERFACE"}])[0]
        self.assertEqual(result["object_type"], "FLANGE")
        self.assertEqual(result["classification_source"], "DETERMINISTIC_INTERFACE_GEOMETRY_V1.2")

    def test_toroidal_elbow_is_fitting(self):
        body = {"source_id": "e", "reference_bounds_mm": [0, 0, 0, 60, 160, 160],
                "surface_statistics": {"surface_type_counts": {
                    "PLANE": 2, "CYLINDER": 0, "CONE": 0, "TORUS": 2}}}
        result = classify_engineering_objects([body], {}, [], [{
            "source_object_id": "p", "target_object_id": "e", "relationship_type": "DIRECT_INTERFACE"}])[0]
        self.assertEqual(result["object_type"], "FITTING")

    def test_valve_like_long_body_is_not_forced_to_flange(self):
        body = {"source_id": "v", "reference_bounds_mm": [0, 0, 0, 178, 178, 358],
                "surface_statistics": {"surface_type_counts": {
                    "PLANE": 5, "CYLINDER": 6, "CONE": 6, "TORUS": 0}}}
        self.assertEqual(classify_engineering_objects([body], {}, [])[0]["object_type"], "UNKNOWN")

    def test_toroidal_motor_mount_without_pipe_connection_stays_unknown(self):
        body = {"source_id": "mount", "reference_bounds_mm": [0, 0, 0, 180, 45, 70],
                "surface_statistics": {"surface_type_counts": {
                    "PLANE": 8, "CYLINDER": 4, "CONE": 0, "TORUS": 2}}}
        result = classify_engineering_objects([body], {}, [])[0]
        self.assertEqual(result["object_type"], "UNKNOWN")
