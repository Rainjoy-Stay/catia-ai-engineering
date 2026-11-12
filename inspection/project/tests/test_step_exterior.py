import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.ShapeUpgrade import ShapeUpgrade_ShapeDivideClosed
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.exterior import exterior_candidate


class ExteriorAcceptance(unittest.TestCase):
    def inspect(self,shape):
        m=OCCTBRepModel(); s=m.register_shape('TEST',shape)
        return exterior_candidate(s,[m.describe(f) for f in m.solid_face_provenance('TEST')['face_ids']])

    def test_solid_rod_is_candidate_without_cavity_claim(self):
        r=self.inspect(BRepPrimAPI_MakeCylinder(2,10).Shape())
        self.assertEqual(r['geometry_kind'],'STRAIGHT_CYLINDRICAL_EXTERIOR_CANDIDATE')
        self.assertAlmostEqual(r['outer_diameter_mm'],4)
        self.assertAlmostEqual(r['length_mm'],10)
        self.assertIsNone(r['wall_thickness_mm'])
        self.assertFalse(r['design_cavity_confirmed'])
        self.assertFalse(r['engineering_pipe_confirmed'])
        self.assertEqual(r['ports'],[])

    def test_arbitrary_orientation(self):
        axis=gp_Ax2(gp_Pnt(12,-8,9),gp_Dir(1,2,3))
        self.assertAlmostEqual(self.inspect(BRepPrimAPI_MakeCylinder(axis,2,10).Shape())['length_mm'],10)

    def test_split_solid_cylinder(self):
        split=ShapeUpgrade_ShapeDivideClosed(BRepPrimAPI_MakeCylinder(2,10).Shape())
        split.SetNbSplitPoints(1); split.Perform()
        self.assertEqual(len(self.inspect(split.Result())['outer_face_ids']),2)

    def test_hollow_shape_does_not_get_wall_claim_from_exterior(self):
        shape=BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(2,10).Shape(),BRepPrimAPI_MakeCylinder(1,10).Shape()).Shape()
        r=self.inspect(shape)
        self.assertEqual(r['geometry_kind'],'STRAIGHT_CYLINDRICAL_EXTERIOR_CANDIDATE')
        self.assertIsNone(r['wall_thickness_mm'])

    def test_drilled_block_rejected(self):
        shape=BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(gp_Pnt(-3,-3,0),6,6,10).Shape(),BRepPrimAPI_MakeCylinder(1,10).Shape()).Shape()
        self.assertEqual(self.inspect(shape)['geometry_kind'],'UNDETERMINED')

    def test_blind_hole_remains_composite(self):
        shape=BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(2,10).Shape(),BRepPrimAPI_MakeCylinder(1,8).Shape()).Shape()
        self.assertEqual(self.inspect(shape)['geometry_kind'],'UNDETERMINED')


if __name__=='__main__': unittest.main()
