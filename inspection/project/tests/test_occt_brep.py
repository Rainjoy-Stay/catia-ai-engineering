import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakeWire)
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.IGESControl import IGESControl_Writer
from OCP.gp import gp_Ax2, gp_Circ, gp_Pln, gp_Pnt, gp_Dir

from catia_checker.occt_brep import (
    OCCTBRepModel, _decode_step_text, backend_status, sweep_and_prune_pairs,
)


class OCCTBRepTests(unittest.TestCase):
    def test_local_common_locates_robust_interior_without_inventing_intent(self):
        model = OCCTBRepModel()
        model.register_shape('A', BRepPrimAPI_MakeBox(1,1,1).Shape())
        model.register_shape('B', BRepPrimAPI_MakeBox(gp_Pnt(.5,0,0),1,1,1).Shape())
        evidence = model.local_overlap_evidence('A','B')
        self.assertAlmostEqual(evidence['volume_mm3'], .5)
        self.assertTrue(evidence['robust_interior_witness_found'])
        self.assertFalse(evidence['engineering_intent_inferred'])

    def test_micro_overlap_does_not_claim_robust_margin(self):
        model = OCCTBRepModel()
        model.register_shape('A', BRepPrimAPI_MakeBox(1,1,1).Shape())
        model.register_shape('B', BRepPrimAPI_MakeBox(gp_Pnt(1-5e-7,0,0),1,1,1).Shape())
        evidence = model.local_overlap_evidence('A','B')
        self.assertFalse(evidence['robust_interior_witness_found'])

    def test_contact_has_no_volume_witness(self):
        model = OCCTBRepModel()
        model.register_shape('A', BRepPrimAPI_MakeBox(1,1,1).Shape())
        model.register_shape('B', BRepPrimAPI_MakeBox(gp_Pnt(1,0,0),1,1,1).Shape())
        self.assertFalse(model.local_overlap_evidence('A','B')['robust_interior_witness_found'])

    def setUp(self):
        self.model = OCCTBRepModel()

    def test_backend_is_available_without_mesh_fallback(self):
        self.assertTrue(backend_status()["available"])
        self.assertFalse(backend_status()["fallback_to_mesh"])

    def test_step_utf16_name_is_decoded(self):
        encoded = "\\X2\\96F64EF651E04F554F53\\X0\\"
        self.assertEqual(_decode_step_text(encoded), "零件几何体")

    def test_exact_box_distance(self):
        self.model.register_shape("A", BRepPrimAPI_MakeBox(1, 1, 1).Shape())
        self.model.register_shape("B", BRepPrimAPI_MakeBox(gp_Pnt(3, 0, 0), 1, 1, 1).Shape())
        self.assertAlmostEqual(self.model.distance("A", "B")["minimum_distance_mm"], 2.0, places=7)

    def test_solid_surface_section(self):
        self.model.register_shape("BOX", BRepPrimAPI_MakeBox(2, 2, 2).Shape())
        face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(1, 0, 0), gp_Dir(1, 0, 0)), -1, 3, -1, 3).Face()
        self.model.register_shape("FACE", face)
        result = self.model.section("BOX", "FACE")
        self.assertTrue(result["intersects"])
        self.assertGreater(result["section_edge_count"], 0)

    def test_solid_crossing_face_has_two_side_penetration_evidence(self):
        self.model.register_shape("BOX", BRepPrimAPI_MakeBox(2, 2, 2).Shape())
        face = BRepBuilderAPI_MakeFace(
            gp_Pln(gp_Pnt(1, 0, 0), gp_Dir(1, 0, 0)), -1, 3, -1, 3).Face()
        self.model.register_shape("FACE", face)
        result = self.model.pair_fact(
            "BOX", "FACE", entity_a={"geometry_kind": "SOLID"},
            entity_b={"geometry_kind": "FACE"})
        self.assertTrue(result["penetration_evidence_available"])
        self.assertTrue(result["penetration_confirmed"])
        self.assertTrue(result["crosses_surface_normal_sides"])

    def test_solid_ending_at_face_is_not_penetration(self):
        self.model.register_shape("BOX", BRepPrimAPI_MakeBox(2, 2, 2).Shape())
        face = BRepBuilderAPI_MakeFace(
            gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), -1, 3, -1, 3).Face()
        self.model.register_shape("FACE", face)
        result = self.model.pair_fact(
            "BOX", "FACE", entity_a={"geometry_kind": "SOLID"},
            entity_b={"geometry_kind": "FACE"})
        self.assertTrue(result["penetration_evidence_available"])
        self.assertFalse(result["penetration_confirmed"])
        states = {(item["positive_side_state"], item["negative_side_state"])
                  for item in result["side_samples"]}
        self.assertTrue(any("IN" in pair and "OUT" in pair for pair in states))

    def test_common_volume_is_exact(self):
        self.model.register_shape("A", BRepPrimAPI_MakeBox(2, 2, 2).Shape())
        self.model.register_shape("B", BRepPrimAPI_MakeBox(gp_Pnt(1, 0, 0), 2, 2, 2).Shape())
        self.assertAlmostEqual(self.model.common_volume("A", "B")["intersection_volume_mm3"], 4.0, places=6)

    def test_point_containment(self):
        self.model.register_shape("BOX", BRepPrimAPI_MakeBox(2, 2, 2).Shape())
        self.assertTrue(self.model.classify_point("BOX", [1, 1, 1], 1e-7)["contained"])

    def test_surface_pair_shared_boundary_is_contact(self):
        left = BRepBuilderAPI_MakeFace(
            gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0, 1, 0, 1).Face()
        right = BRepBuilderAPI_MakeFace(
            gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 1, 2, 0, 1).Face()
        self.model.register_shape("LEFT", left)
        self.model.register_shape("RIGHT", right)
        fact = self.model.surface_pair_fact(
            "LEFT", "RIGHT", entity_a={"geometry_kind": "FACE"}, entity_b={"geometry_kind": "FACE"})
        self.assertEqual(fact["intersection_type"], "CONTACT")
        self.assertTrue(fact["boundary_contact"])
        self.assertFalse(fact["surface_intersection"])
        self.assertTrue(fact["continuous_surface_contact"])

    def test_coincident_faces_are_contact_not_one_continuous_patch(self):
        first = BRepBuilderAPI_MakeFace(
            gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0, 2, 0, 2).Face()
        second = BRepBuilderAPI_MakeFace(
            gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0, 2, 0, 2).Face()
        self.model.register_shape("A", first)
        self.model.register_shape("B", second)
        fact = self.model.surface_pair_fact(
            "A", "B", entity_a={"geometry_kind": "FACE"}, entity_b={"geometry_kind": "FACE"})
        self.assertTrue(fact["coincident_surface_overlap"])
        self.assertGreater(fact["coincident_surface_area_mm2"], 0)
        self.assertFalse(fact["continuous_surface_contact"])

    def test_surface_pair_interior_crossing_is_intersection(self):
        horizontal = BRepBuilderAPI_MakeFace(
            gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), -1, 1, -1, 1).Face()
        vertical = BRepBuilderAPI_MakeFace(
            gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), -1, 1, -1, 1).Face()
        self.model.register_shape("H", horizontal)
        self.model.register_shape("V", vertical)
        fact = self.model.surface_pair_fact(
            "H", "V", entity_a={"geometry_kind": "FACE"}, entity_b={"geometry_kind": "FACE"})
        self.assertEqual(fact["intersection_type"], "SURFACE_INTERSECTION")
        self.assertFalse(fact["boundary_contact"])
        self.assertTrue(fact["surface_intersection"])

    def test_planar_annulus_reports_exact_circular_inner_boundary(self):
        axis = gp_Ax2(gp_Pnt(10, 20, 30), gp_Dir(0, 0, 1))
        outer = BRepBuilderAPI_MakeWire(
            BRepBuilderAPI_MakeEdge(gp_Circ(axis, 10)).Edge()).Wire()
        inner = BRepBuilderAPI_MakeWire(
            BRepBuilderAPI_MakeEdge(gp_Circ(axis, 3)).Edge()).Wire()
        builder = BRepBuilderAPI_MakeFace(outer, True)
        builder.Add(inner)
        self.model.register_shape("ANNULUS", builder.Face())
        features = self.model.describe("ANNULUS")["surface_features"]
        self.assertTrue(features["host_discontinuity_confirmed"])
        self.assertEqual(len(features["circular_inner_boundaries"]), 1)
        boundary = features["circular_inner_boundaries"][0]
        self.assertAlmostEqual(boundary["radius_mm"], 3.0)
        self.assertEqual(boundary["center_mm"], [10.0, 20.0, 30.0])
        self.assertTrue(boundary["closed"])

    def test_load_iges_registers_individual_faces(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "two_faces.igs"
            writer = IGESControl_Writer("MM", 0)
            self.assertTrue(writer.AddShape(BRepPrimAPI_MakeBox(1, 1, 1).Shape()))
            self.assertTrue(writer.Write(str(source)))
            manifest = self.model.load_iges(source)
        self.assertEqual(manifest["root_shape_id"], "IGES_ROOT")
        self.assertGreaterEqual(manifest["shapes"][0]["face_count"], 6)
        self.assertIn("IGES_FACE_000001", {item["shape_id"] for item in manifest["shapes"]})

    def test_sweep_and_prune_excludes_spatially_remote_shapes(self):
        shapes = [
            {"shape_id": "A", "bounds_mm": {"min": [0, 0, 0], "max": [2, 2, 2]}},
            {"shape_id": "B", "bounds_mm": {"min": [1, 1, 1], "max": [3, 3, 3]}},
            {"shape_id": "FAR", "bounds_mm": {"min": [1000, 0, 0], "max": [1001, 1, 1]}},
        ]
        result = sweep_and_prune_pairs(shapes)
        self.assertEqual(result["total_possible_pairs"], 3)
        self.assertEqual(result["candidate_pair_count"], 1)
        self.assertEqual(result["pairs"], [("A", "B")])


if __name__ == "__main__":
    unittest.main()
