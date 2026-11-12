import unittest

from catia_checker.semantic_interactions import (
    assess_solid_interactions, enrich_intersection_events,
)


def inputs(roles):
    events = {"events": [{"event_id": "INT-1", "face_pairs": [
        {"object_a": "F1", "object_b": "F2"}]}]}
    logical = {"face_to_component": {"F1": "C1", "F2": "C2"}}
    role_data = {"candidates": [
        {"logical_component_id": "C1", "engineering_role": roles[0]},
        {"logical_component_id": "C2", "engineering_role": roles[1]}]}
    return events, logical, role_data


class SemanticInteractionTests(unittest.TestCase):
    def test_solid_common_volume_fails_and_clearance_passes(self):
        result = assess_solid_interactions([
            {"object_a": "VESSEL", "object_b": "LEGAL", "intersects": False,
             "minimum_distance_mm": 0.2, "intersection_volume_mm3": 0.0,
             "exact_brep": True},
            {"object_a": "VESSEL", "object_b": "ILLEGAL", "intersects": True,
             "section_edge_count": 16, "intersection_volume_mm3": 5546.5,
             "exact_brep": True},
        ])
        self.assertEqual(result["disposition_counts"], {"PASS": 1, "FAIL": 1})
        self.assertEqual(result["assessments"][0]["disposition"], "PASS")
        self.assertEqual(result["assessments"][1]["disposition"], "FAIL")

    def test_nozzle_vessel_without_opening_evidence_is_review(self):
        events, logical, roles = inputs(("NOZZLE", "VESSEL_SHELL"))
        result = enrich_intersection_events(events, logical, roles, [
            {"object_a": "F1", "object_b": "F2", "surface_intersection": True}])
        event = result["events"][0]
        self.assertEqual(event["engineering_relation"], "NOZZLE_TO_VESSEL")
        self.assertEqual(event["disposition"], "REVIEW")

    def test_allowed_nozzle_interface_passes(self):
        events, logical, roles = inputs(("NOZZLE", "VESSEL_SHELL"))
        result = enrich_intersection_events(events, logical, roles, [
            {"object_a": "F1", "object_b": "F2", "allowed_region": True}])
        self.assertEqual(result["events"][0]["disposition"], "PASS")

    def test_confirmed_unallowed_nozzle_penetration_fails(self):
        events, logical, roles = inputs(("NOZZLE", "VESSEL_SHELL"))
        result = enrich_intersection_events(events, logical, roles, [
            {"object_a": "F1", "object_b": "F2", "penetration_confirmed": True}])
        self.assertEqual(result["events"][0]["disposition"], "FAIL")

    def test_same_component_self_intersection_is_review(self):
        events = {"events": [{"event_id": "INT-1", "face_pairs": [
            {"object_a": "F1", "object_b": "F2"}]}]}
        logical = {"face_to_component": {"F1": "C1", "F2": "C1"}}
        result = enrich_intersection_events(events, logical, {"candidates": []}, [])
        self.assertEqual(result["events"][0]["error_category"], "CONVERSION_OR_TOPOLOGY_ERROR")
        self.assertEqual(result["events"][0]["disposition"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
