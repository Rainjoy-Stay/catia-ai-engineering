import math
import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus,BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.exterior import exterior_candidate


class CurvedExteriorAcceptance(unittest.TestCase):
    def inspect(self,shape):
        m=OCCTBRepModel(); s=m.register_shape('TEST',shape)
        return exterior_candidate(s,[m.describe(f) for f in m.solid_face_provenance('TEST')['face_ids']])

    def test_solid_curved_exterior_without_hole(self):
        r=self.inspect(BRepPrimAPI_MakeTorus(10,2,math.pi/2).Shape())
        self.assertEqual(r['geometry_kind'],'CIRCULAR_CURVED_EXTERIOR_CANDIDATE')
        self.assertAlmostEqual(r['centerline_bend_radius_mm'],10)
        self.assertAlmostEqual(r['sweep_angle_rad'],math.pi/2)
        self.assertIsNone(r['wall_thickness_mm'])
        self.assertFalse(r['design_cavity_confirmed'])
        self.assertFalse(r['engineering_pipe_confirmed'])
        self.assertEqual(r['ports'],[])

    def test_rotated_translated_45_degree(self):
        axis=gp_Ax2(gp_Pnt(12,-8,9),gp_Dir(1,2,3))
        r=self.inspect(BRepPrimAPI_MakeTorus(axis,10,2,math.pi/4).Shape())
        self.assertAlmostEqual(r['centerline_length_mm'],10*math.pi/4)

    def test_hollow_bend_still_no_wall_claim(self):
        shape=BRepAlgoAPI_Cut(BRepPrimAPI_MakeTorus(10,2,math.pi/2).Shape(),BRepPrimAPI_MakeTorus(10,1,math.pi/2).Shape()).Shape()
        r=self.inspect(shape)
        self.assertEqual(r['geometry_kind'],'CIRCULAR_CURVED_EXTERIOR_CANDIDATE')
        self.assertIsNone(r['wall_thickness_mm'])

    def test_closed_torus_not_open_bend(self):
        self.assertEqual(self.inspect(BRepPrimAPI_MakeTorus(10,2).Shape())['geometry_kind'],'UNDETERMINED')

    def test_straight_shape_is_not_curved(self):
        self.assertEqual(self.inspect(BRepPrimAPI_MakeCylinder(2,10).Shape())['geometry_kind'],'STRAIGHT_CYLINDRICAL_EXTERIOR_CANDIDATE')

    def test_rounding_in_actual_seed_not_bend(self):
        from pathlib import Path
        path=Path(__file__).resolve().parents[1]/'artifacts'/'step_pipe_complex_discovery'/'SOURCE_SOLID_0835.brep'
        if not path.exists(): self.skipTest('Local model cache unavailable')
        m=OCCTBRepModel(); m.load_brep('ROUNDING',path)
        s=m.describe('ROUNDING'); faces=[m.describe(f) for f in m.solid_face_provenance('ROUNDING')['face_ids']]
        self.assertEqual(exterior_candidate(s,faces)['geometry_kind'],'UNDETERMINED')


if __name__=='__main__': unittest.main()
