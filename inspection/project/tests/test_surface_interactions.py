import unittest

from catia_checker.geometry_integrity import GeometryTolerance
from catia_checker.models import CheckStatus
from catia_checker.surface_interactions import surface_fact_to_finding


class SurfaceInteractionTests(unittest.TestCase):
    def test_duplicate_display_names_keep_distinct_stable_issue_ids(self):
        common = {
            "object_a_name": "PartBody", "object_b_name": "PartBody",
            "entity_a": {"geometry_kind": "SOLID"},
            "entity_b": {"geometry_kind": "SOLID"},
            "minimum_distance_mm": 2.0,
        }
        first = surface_fact_to_finding(
            {**common, "object_a": "STEP_SOLID_0001", "object_b": "STEP_SOLID_0002"},
            tolerance=GeometryTolerance())
        second = surface_fact_to_finding(
            {**common, "object_a": "STEP_SOLID_0003", "object_b": "STEP_SOLID_0004"},
            tolerance=GeometryTolerance())
        self.assertNotEqual(first.issue_id, second.issue_id)

    def setUp(self):
        self.tolerance = GeometryTolerance()

    def test_pipe_penetration_of_zero_volume_surface_fails(self):
        finding = surface_fact_to_finding({
            "object_a": "Pipe.1", "object_b": "BulkheadSurface.1",
            "entity_a": {"geometry_kind": "SOLID"},
            "entity_b": {"geometry_kind": "SURFACE", "volume_mm3": 0},
            "intersects": True, "penetration_confirmed": True,
            "intersection_points_mm": [[10, 20, 30]],
            "method": "CATIA_TESSELLATED_SURFACE_INTERSECTION",
        }, tolerance=self.tolerance)
        self.assertEqual(finding.status, CheckStatus.FAIL)
        self.assertEqual(finding.metadata["interaction_type"], "SURFACE_PENETRATION")
        self.assertEqual(finding.location_xyz_mm, (10, 20, 30))

    def test_surface_intersection_is_not_reported_as_solid_volume_clash(self):
        finding = surface_fact_to_finding({
            "object_a": "WallA", "object_b": "WallB",
            "entity_a": {"geometry_kind": "SURFACE"},
            "entity_b": {"geometry_kind": "SURFACE"}, "intersects": True,
        }, tolerance=self.tolerance)
        self.assertEqual(finding.rule_id, "GEOMETRY.SURFACE_INTERSECTION")
        self.assertEqual(finding.status, CheckStatus.FAIL)

    def test_allowed_interface_is_pass_not_global_exemption(self):
        finding = surface_fact_to_finding({
            "object_a": "Pipe.1", "object_b": "Fitting.1",
            "entity_a": {"geometry_kind": "SOLID"}, "entity_b": {"geometry_kind": "SURFACE"},
            "intersects": True, "allowed_region": True,
        }, tolerance=self.tolerance)
        self.assertEqual(finding.status, CheckStatus.PASS)
        self.assertEqual(finding.metadata["interaction_type"], "EXPECTED_CONTACT")

    def test_exact_solid_clearance_uses_step_names_and_keeps_stable_ids(self):
        finding = surface_fact_to_finding({
            "object_a": "STEP_SOLID_0001", "object_b": "STEP_SOLID_0002",
            "object_a_name": "零件几何体", "object_b_name": "NOZZLE-A",
            "entity_a": {"geometry_kind": "SOLID"},
            "entity_b": {"geometry_kind": "SOLID"},
            "minimum_distance_mm": 0.2, "intersection_volume_mm3": 0.0,
            "method": "OCCT_EXACT_BREP",
        }, tolerance=self.tolerance, required_clearance_mm=0.0)
        self.assertEqual(finding.status, CheckStatus.PASS)
        self.assertEqual((finding.object_a, finding.object_b), ("零件几何体", "NOZZLE-A"))
        self.assertEqual(finding.evidence[0].data["stable_object_ids"],
                         ["STEP_SOLID_0001", "STEP_SOLID_0002"])


if __name__ == "__main__":
    unittest.main()
