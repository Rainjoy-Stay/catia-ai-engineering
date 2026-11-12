from pathlib import Path
import tempfile
import unittest

from catia_checker.model_understanding.adapters.step_brep import inspect_step_brep


STEP = """ISO-10303-21;
HEADER;ENDSEC;
DATA;
#11=CARTESIAN_POINT('',(10.0,20.0,30.0));
#12=DIRECTION('',(0.0,0.0,1.0));
#13=DIRECTION('',(1.0,0.0,0.0));
#10=AXIS2_PLACEMENT_3D('',#11,#12,#13);
#20=CYLINDRICAL_SURFACE('',#10,5.0);
#21=PLANE('',#10);
#30=ADVANCED_FACE('',(#40),#20,.T.);
#31=ADVANCED_FACE('',(#41),#21,.T.);
#50=CLOSED_SHELL('',(#30,#31));
#60=MANIFOLD_SOLID_BREP('Pipe body',#50);
ENDSEC;END-ISO-10303-21;
"""


class StepBrepTests(unittest.TestCase):
    def test_faces_are_assigned_through_explicit_brep_references(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.step"
            path.write_text(STEP, encoding="latin-1")
            result = inspect_step_brep(path)
        self.assertEqual(result["body_count"], 1)
        body = result["bodies"][0]
        self.assertEqual(body["source_name"], "Pipe body")
        self.assertEqual(body["closure_state"], "CLOSED")
        self.assertEqual(body["surface_statistics"]["surface_type_counts"]["CYLINDER"], 1)
        self.assertEqual(body["surface_statistics"]["surface_type_counts"]["PLANE"], 1)
        self.assertEqual(body["faces"][0]["parameters"]["radius"], 5.0)
        self.assertEqual(body["tubular_features"]["dominant_diameter"], 10.0)
        self.assertEqual(body["tubular_features"]["tubular_surface_ratio"], 0.5)
        self.assertEqual(body["faces"][0]["placement"]["origin_mm"], [10.0, 20.0, 30.0])
        self.assertEqual(body["faces"][0]["placement"]["axis_direction"], [0.0, 0.0, 1.0])
        self.assertEqual(body["tubular_features"]["axis_consistency"], 1.0)

    def test_file_suffix_does_not_change_object_classification(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fitting.stp"
            path.write_text(STEP, encoding="latin-1")
            body = inspect_step_brep(path)["bodies"][0]
        self.assertNotIn("object_type", body)

    def test_radius_clustering_does_not_average_unrelated_holes(self):
        text = STEP.replace("#31=ADVANCED_FACE('',(#41),#21,.T.);",
            "#22=CYLINDRICAL_SURFACE('',#10,5.01);\n"
            "#23=CYLINDRICAL_SURFACE('',#10,20.0);\n"
            "#31=ADVANCED_FACE('',(#41),#22,.T.);\n"
            "#32=ADVANCED_FACE('',(#42),#23,.T.);").replace(
            "#50=CLOSED_SHELL('',(#30,#31));", "#50=CLOSED_SHELL('',(#30,#31,#32));")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "clusters.step"
            path.write_text(text, encoding="latin-1")
            tubular = inspect_step_brep(path)["bodies"][0]["tubular_features"]
        self.assertAlmostEqual(tubular["dominant_radius"], 5.005)
        self.assertEqual(tubular["radius_clusters"][0]["sample_count"], 2)
        self.assertEqual(len(tubular["radius_clusters"]), 2)

    def test_equal_support_concentric_wall_clusters_choose_outer_radius(self):
        text = STEP.replace("#31=ADVANCED_FACE('',(#41),#21,.T.);",
            "#22=CYLINDRICAL_SURFACE('',#10,4.0);\n"
            "#31=ADVANCED_FACE('',(#41),#22,.T.);")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "hollow.step"
            path.write_text(text, encoding="latin-1")
            tubular = inspect_step_brep(path)["bodies"][0]["tubular_features"]
        self.assertEqual(tubular["dominant_radius"], 5.0)

    def test_complex_relationship_places_body_bounds_in_world_coordinates(self):
        transform_records = """
#70=ADVANCED_BREP_SHAPE_REPRESENTATION('',(#60),#10);
#71=SHAPE_REPRESENTATION('',(#10),#10);
#72=SHAPE_REPRESENTATION_RELATIONSHIP('','',#70,#71);
#80=CARTESIAN_POINT('',(0.,0.,0.));
#81=CARTESIAN_POINT('',(100.,200.,300.));
#82=AXIS2_PLACEMENT_3D('',#80,#12,#13);
#83=AXIS2_PLACEMENT_3D('',#81,#12,#13);
#84=ITEM_DEFINED_TRANSFORMATION('','',#82,#83);
#90=SHAPE_REPRESENTATION('',(#83),#10);
#85=(REPRESENTATION_RELATIONSHIP('','',#71,#90)REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#84)SHAPE_REPRESENTATION_RELATIONSHIP());
"""
        text = STEP.replace("ENDSEC;END-ISO-10303-21;", transform_records +
                            "ENDSEC;END-ISO-10303-21;")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "assembly.step"
            path.write_text(text, encoding="latin-1")
            body = inspect_step_brep(path)["bodies"][0]
        self.assertEqual(body["reference_bounds_coordinate_space"], "WORLD")
        self.assertEqual(body["reference_bounds_mm"][:3], [110.0, 220.0, 330.0])
        self.assertEqual(body["assembly_transform"]["relationship_path"], ["#72", "#85"])

    def test_body_is_traced_to_product_name(self):
        records = """
#70=ADVANCED_BREP_SHAPE_REPRESENTATION('',(#60),#10);
#71=SHAPE_REPRESENTATION('',(#10),#10);
#72=SHAPE_REPRESENTATION_RELATIONSHIP('','',#71,#70);
#73=PRODUCT('Pipe-001','','',());
#74=PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE('','',#73,.NOT_KNOWN.);
#75=PRODUCT_DEFINITION('','',#74,#10);
#76=PRODUCT_DEFINITION_SHAPE('','',#75);
#77=SHAPE_DEFINITION_REPRESENTATION(#76,#71);
#78=NEXT_ASSEMBLY_USAGE_OCCURRENCE('Pipe-Instance-7','','',#75,#75,'');
"""
        text = STEP.replace("ENDSEC;END-ISO-10303-21;", records + "ENDSEC;END-ISO-10303-21;")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "product.step"
            path.write_text(text, encoding="latin-1")
            body = inspect_step_brep(path)["bodies"][0]
        self.assertEqual(body["product_name"], "Pipe-001")
        self.assertEqual(body["product_id"], "#73")
        self.assertEqual(body["occurrence_names"], ["Pipe-Instance-7"])


if __name__ == "__main__":
    unittest.main()
