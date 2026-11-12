import unittest

from catia_checker.opening_interfaces import (
    build_opening_interface_bundle, discover_opening_interface_bundle,
    record_auto_discovery_coverage,
)


class OpeningInterfaceIntegrationTests(unittest.TestCase):
    def test_exact_facts_become_unified_pass_finding(self):
        bundle = build_opening_interface_bundle({
            "source": "OCCT_BREP",
            "opening_face_records": [{
                "face_id": "HOST", "normal": [1, 0, 0],
                "host_wall_thickness_mm": 10, "host_discontinuity_confirmed": True,
                "exact_brep": True, "circular_inner_boundaries": [{
                    "boundary_id": "OPEN", "center_mm": [100, 0, 0],
                    "radius_mm": 20.2, "closed": True, "exact_brep": True}]}],
            "cylindrical_surface_records": [{
                "surface_id": "OUTER", "component_id": "NOZZLE",
                "surface_type": "CYLINDER", "axis_origin_mm": [50, 0, 0],
                "axis_direction": [1, 0, 0], "radius_mm": 20,
                "axis_limits_mm": [0, 70], "exact_brep": True}, {
                "surface_id": "INNER", "component_id": "NOZZLE",
                "surface_type": "CYLINDER", "axis_origin_mm": [50, 0, 0],
                "axis_direction": [1, 0, 0], "radius_mm": 15,
                "axis_limits_mm": [0, 70], "exact_brep": True}],
        })
        self.assertEqual(bundle["disposition_counts"], {"PASS": 1, "FAIL": 0, "REVIEW": 0})
        self.assertEqual(bundle["findings"][0]["status"], "PASS")
        self.assertFalse(bundle["mesh_used"])
        detail = bundle["findings"][0]["metadata"]["opening_interface"]
        self.assertEqual(detail["measurements"]["host_wall_thickness_mm"], 10.0)
        self.assertEqual(detail["measurements"]["opening_radius_mm"], 20.2)
        self.assertTrue(detail["evidence"]["host_discontinuity_confirmed"])

    def test_inventory_auto_discovery_executes_when_evidence_is_complete(self):
        host = {"shape_id": "HOST-FACE", "surface_features": {
            "surface_type": "PLANE", "normal": [1, 0, 0],
            "host_wall_thickness_mm": 10, "host_discontinuity_confirmed": True,
            "circular_inner_boundaries": [{"boundary_id": "OPEN", "center_mm": [100, 0, 0],
                                             "radius_mm": 20.2, "closed": True,
                                             "exact_brep": True}]}}
        cylinders = [{"shape_id": name, "parent_body_id": "NOZZLE",
                      "bounds_mm": {"min": [50, -radius, -radius],
                                    "max": [120, radius, radius]},
                      "surface_features": {"surface_type": "CYLINDER",
                                           "axis_origin_mm": [50, 0, 0],
                                           "axis_direction": [1, 0, 0],
                                           "radius_mm": radius}}
                     for name, radius in (("OUTER", 20), ("INNER", 15))]
        result = discover_opening_interface_bundle(
            {"shapes": [host, *cylinders]}, source="OCCT_BREP")
        self.assertTrue(result["analysis_executed"])
        self.assertEqual(result["analysis"]["disposition_counts"]["PASS"], 1)

    def test_inventory_without_opening_does_not_create_false_failure(self):
        result = discover_opening_interface_bundle({"shapes": [{
            "shape_id": "CYL", "bounds_mm": {"min": [0, -20, -20], "max": [70, 20, 20]},
            "surface_features": {"surface_type": "CYLINDER", "axis_origin_mm": [0, 0, 0],
                                 "axis_direction": [1, 0, 0], "radius_mm": 20}}]},
            source="OCCT_BREP")
        self.assertFalse(result["analysis_executed"])
        self.assertIsNone(result["analysis"])
        self.assertEqual(result["coverage"]["status"], "NOT_CHECKED")
        self.assertIn("NO_RELIABLE_OPENING_EVIDENCE",
                      result["coverage"]["reason_codes"])

    def test_skipped_discovery_marks_confidence_budget_incomplete(self):
        result = discover_opening_interface_bundle({"shapes": []}, source="OCCT_BREP")
        payload = {"confidence_budget": {"checked": [], "not_checked": [], "degraded": []}}
        record_auto_discovery_coverage(payload, result, authority="OCCT精确B-Rep")
        self.assertTrue(payload["confidence_budget"]["not_checked"])
        self.assertIn("未发现", payload["confidence_budget"]["not_checked"][0])

    def test_later_success_clears_earlier_discovery_gap(self):
        payload = {"confidence_budget": {"checked": [], "not_checked": [
            "接管—开孔接口自动检查未执行（CATIA）：未发现可靠开孔"], "degraded": []}}
        record_auto_discovery_coverage(
            payload, {"analysis_executed": True}, authority="OCCT精确B-Rep")
        self.assertEqual(payload["confidence_budget"]["not_checked"], [])
        self.assertEqual(len(payload["confidence_budget"]["checked"]), 1)

    def test_central_rules_override_embedded_analysis_options(self):
        payload = {
            "source": "OCCT_BREP", "analysis_options": {"coaxial_tolerance_mm": 99},
            "opening_face_records": [{"face_id": "HOST", "normal": [1, 0, 0],
                "host_wall_thickness_mm": 10, "host_discontinuity_confirmed": True,
                "exact_brep": True, "circular_inner_boundaries": [{"boundary_id": "OPEN",
                    "center_mm": [100, 0, 0], "radius_mm": 20.2, "closed": True,
                    "exact_brep": True}]}],
            "cylindrical_surface_records": [{"surface_id": "OUTER", "component_id": "N",
                "surface_type": "CYLINDER", "axis_origin_mm": [50, 0, 0.7],
                "axis_direction": [1, 0, 0], "radius_mm": 20,
                "axis_limits_mm": [0, 70], "exact_brep": True}],
        }
        rules = {"opening_interface": {
            "candidate_search_margin_mm": 5, "candidate_angle_limit_deg": 5,
            "candidate_offset_limit_mm": 5, "candidate_radius_limit_mm": 5,
            "candidate_axial_margin_mm": 5, "ambiguity_score_delta": 0.05,
            "coaxial_tolerance_mm": 0.5, "angle_tolerance_deg": 1,
            "radial_clearance_min_mm": 0, "radial_clearance_max_mm": 2,
            "axial_tolerance_mm": 0.1}}
        bundle = build_opening_interface_bundle(payload, rules=rules)
        self.assertEqual(bundle["applied_options"]["analysis_options"]["coaxial_tolerance_mm"], 0.5)
        self.assertEqual(bundle["disposition_counts"]["FAIL"], 1)

    def test_unapproved_rules_downgrade_geometry_fail_to_warning(self):
        rules = {"routing": {"threshold_status": "ASSUMED_PENDING_APPROVAL"}}
        bundle = build_opening_interface_bundle({
            "source": "OCCT_BREP",
            "opening_face_records": [{"face_id": "HOST", "normal": [1, 0, 0],
                "host_wall_thickness_mm": 10, "host_discontinuity_confirmed": True,
                "exact_brep": True, "circular_inner_boundaries": [{"boundary_id": "OPEN",
                    "center_mm": [100, 0, 0.7], "radius_mm": 20.2, "closed": True,
                    "exact_brep": True}]}],
            "cylindrical_surface_records": [{"surface_id": "OUTER", "component_id": "N",
                "surface_type": "CYLINDER", "axis_origin_mm": [50, 0, 0],
                "axis_direction": [1, 0, 0], "radius_mm": 20,
                "axis_limits_mm": [0, 70], "exact_brep": True}],
        }, rules=rules)
        self.assertEqual(bundle["geometry_disposition_counts"]["FAIL"], 1)
        self.assertEqual(bundle["disposition_counts"]["FAIL"], 0)
        self.assertEqual(bundle["disposition_counts"]["REVIEW"], 1)
        self.assertEqual(bundle["findings"][0]["status"], "WARN")
        self.assertFalse(bundle["findings"][0]["metadata"]["formal_adjudication_allowed"])

    def test_issue_id_does_not_change_when_failure_reason_changes(self):
        from catia_checker.opening_interfaces import _finding
        common = {"opening_id": "OPEN-7", "nozzle_id": "NOZZLE-2",
                  "disposition": "FAIL", "measurements": {"radial_clearance_mm": 0.2}}
        first = _finding({**common, "failure_codes": ["AXIS_OFFSET_OUT_OF_TOLERANCE"]},
                         "OCCT_BREP")
        second = _finding({**common, "failure_codes": ["NOZZLE_DOES_NOT_SPAN_HOST_WALL"]},
                          "OCCT_BREP")
        self.assertEqual(first.issue_id, second.issue_id)
        self.assertEqual(first.metadata["issue_identity"]["algorithm"],
                         "OPENING_NOZZLE_PAIR_V1")


if __name__ == "__main__":
    unittest.main()
