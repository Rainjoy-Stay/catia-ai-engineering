import unittest

from catia_checker.geometry_integrity import (
    GeometryTolerance, admission_decision, build_model_precheck, classify_interaction,
)


SOLID = {"geometry_kind": "SOLID", "closure_state": "CLOSED"}
SURFACE = {"geometry_kind": "SURFACE", "volume_mm3": 0}


class GeometryIntegrityCases(unittest.TestCase):
    def setUp(self):
        self.tol = GeometryTolerance(contact_mm=0.01, micro_overlap_mm=0.1)

    def relation(self, **facts):
        return classify_interaction({"entity_a": SOLID, "entity_b": SOLID, **facts}, self.tol,
                                    required_clearance_mm=5)

    def test_case_01_clear_solids(self): self.assertEqual(self.relation(minimum_distance_mm=8)["result"], "PASS")
    def test_case_02_overlapping_solids(self): self.assertEqual(self.relation(intersection_depth_mm=2)["interaction_type"], "SOLID_INTERFERENCE")
    def test_occt_common_volume_is_solid_interference(self):
        self.assertEqual(self.relation(intersection_volume_mm3=4.0)["result"], "FAIL")
    def test_case_03_contact(self): self.assertEqual(self.relation(intersection_depth_mm=0)["interaction_type"], "CONTACT")
    def test_case_04_micro_overlap(self): self.assertEqual(self.relation(intersection_depth_mm=.05)["result"], "REVIEW")
    def test_case_05_pipe_through_solid_wall(self): self.assertEqual(self.relation(intersection_depth_mm=3)["result"], "FAIL")
    def test_case_06_pipe_through_surface(self):
        value = classify_interaction({"entity_a": SOLID, "entity_b": SURFACE, "intersects": True,
                                      "penetration_confirmed": True}, self.tol)
        self.assertEqual((value["result"], value["interaction_type"]), ("FAIL", "SURFACE_PENETRATION"))
    def test_solid_surface_intersection_without_crossing_evidence_is_review(self):
        value = classify_interaction({"entity_a": SOLID, "entity_b": SURFACE,
                                      "intersects": True}, self.tol)
        self.assertEqual((value["result"], value["interaction_type"]),
                         ("REVIEW", "SURFACE_INTERSECTION"))
    def test_case_07_surface_surface(self):
        value = classify_interaction({"entity_a": SURFACE, "entity_b": SURFACE, "intersects": True}, self.tol)
        self.assertEqual(value["interaction_type"], "SURFACE_INTERSECTION")
    def test_case_08_pipe_fitting_allowed_region(self):
        value = classify_interaction({"entity_a": SOLID, "entity_b": SURFACE, "intersects": True,
                                      "allowed_region": True}, self.tol)
        self.assertEqual(value["result"], "PASS")
    def test_case_09_connection_does_not_hide_other_penetration(self):
        allowed = classify_interaction({"entity_a": SOLID, "entity_b": SURFACE, "intersects": True,
                                        "allowed_region": True}, self.tol)
        illegal = classify_interaction({"entity_a": SOLID, "entity_b": SURFACE, "intersects": True,
                                        "penetration_confirmed": True}, self.tol)
        self.assertEqual((allowed["result"], illegal["result"]), ("PASS", "FAIL"))
    def test_case_10_expected_sleeve_containment(self):
        self.assertEqual(self.relation(expected_containment=True)["interaction_type"], "EXPECTED_CONTAINMENT")
    def test_case_11_hollow_to_solid_conversion(self):
        self.assertEqual(self.relation(suspected_conversion_error=True)["result"], "REVIEW")
    def test_case_12_clamp_contact_allowed(self):
        value = classify_interaction({"entity_a": SOLID, "entity_b": SURFACE, "intersects": True,
                                      "allowed_region": True}, self.tol)
        self.assertEqual(value["interaction_type"], "EXPECTED_CONTACT")
    def test_case_13_duplicate_brep_has_explicit_skip_reason(self):
        self.assertEqual(admission_decision({**SOLID, "duplicate": True})["why_skipped"], "DUPLICATE")
    def test_case_14_zero_volume_boundary_is_included(self):
        self.assertTrue(admission_decision(SURFACE)["included"])
    def test_case_15_reference_surface_is_audited(self):
        value = admission_decision({**SURFACE, "reference_geometry": True})
        self.assertEqual((value["included"], value["why_skipped"]), (False, "REFERENCE_GEOMETRY"))
    def test_precheck_reports_open_shell_reliability(self):
        value = build_model_precheck([{"source_id": "#1", "geometry_kind": "SHELL",
                                       "closure_state": "OPEN", "geometry_state": "AVAILABLE"}],
                                     source_format="STEP")
        self.assertTrue(value["surface_geometry_participates"])
        self.assertEqual(value["model_reliability"], "HIGH")


if __name__ == "__main__":
    unittest.main()
