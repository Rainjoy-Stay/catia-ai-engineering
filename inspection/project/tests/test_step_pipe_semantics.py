import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics import straight_candidate


class StraightGeometryAcceptance(unittest.TestCase):
    def inspect(self, shape):
        model = OCCTBRepModel(); solid = model.register_shape('TEST',shape)
        ids = model.solid_face_provenance('TEST')['face_ids']
        return straight_candidate(solid,[model.describe(f) for f in ids])

    def pipe(self,axis=None):
        axis = axis or gp_Ax2(gp_Pnt(0,0,0),gp_Dir(0,0,1))
        return BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(axis,2,10).Shape(),
                              BRepPrimAPI_MakeCylinder(axis,1,10).Shape()).Shape()

    def test_hollow_straight_dimensions(self):
        result = self.inspect(self.pipe())
        self.assertEqual(result['geometry_kind'],'STRAIGHT_HOLLOW_CANDIDATE')
        self.assertAlmostEqual(result['length_mm'],10)
        self.assertAlmostEqual(result['wall_thickness_mm'],1)
        self.assertFalse(result['engineering_pipe_confirmed'])
        self.assertEqual(result['status'],'NOT_EVALUATED')

    def test_arbitrary_orientation_and_position(self):
        result = self.inspect(self.pipe(gp_Ax2(gp_Pnt(37,-12,5),gp_Dir(1,2,3))))
        self.assertEqual(result['geometry_kind'],'STRAIGHT_HOLLOW_CANDIDATE')
        self.assertAlmostEqual(result['length_mm'],10)

    def test_solid_cylinder_is_not_pipe(self):
        self.assertEqual(self.inspect(BRepPrimAPI_MakeCylinder(2,10).Shape())['geometry_kind'],'UNDETERMINED')

    def test_drilled_block_is_not_pipe(self):
        block = BRepPrimAPI_MakeBox(gp_Pnt(-3,-3,0),6,6,10).Shape()
        drilled = BRepAlgoAPI_Cut(block,BRepPrimAPI_MakeCylinder(1,10).Shape()).Shape()
        self.assertEqual(self.inspect(drilled)['geometry_kind'],'UNDETERMINED')

    def test_blind_bore_is_not_open_pipe(self):
        blind = BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(2,10).Shape(),
                               BRepPrimAPI_MakeCylinder(1,8).Shape()).Shape()
        self.assertEqual(self.inspect(blind)['geometry_kind'],'UNDETERMINED')

    def test_eccentric_bore_is_not_uniform_pipe(self):
        bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(.2,0,0),gp_Dir(0,0,1)),1,10).Shape()
        result = self.inspect(BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(2,10).Shape(),bore).Shape())
        self.assertEqual(result['reason'],'CYLINDERS_NOT_COAXIAL')

    def test_step_roundtrip_retains_hollow_candidate(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        with TemporaryDirectory() as folder:
            path = Path(folder)/'pipe.step'
            writer = STEPControl_Writer(); writer.Transfer(self.pipe(),STEPControl_AsIs)
            writer.Write(str(path))
            model = OCCTBRepModel(); manifest = model.load_step(path)
            solid = next(s for s in manifest['shapes'] if s.get('solid_count') == 1 and s.get('shape_id','').startswith('STEP_SOLID_'))
            faces = [model.describe(f) for f in model.solid_face_provenance(solid['shape_id'])['face_ids']]
            self.assertEqual(straight_candidate(solid,faces)['geometry_kind'],'STRAIGHT_HOLLOW_CANDIDATE')

    def test_duplicate_face_evidence_cannot_establish_pipe(self):
        model = OCCTBRepModel(); solid = model.register_shape('TEST',self.pipe())
        faces = [model.describe(f) for f in model.solid_face_provenance('TEST')['face_ids']]
        faces[-1] = faces[0]
        self.assertEqual(straight_candidate(solid,faces)['reason'],'INCOMPLETE_OR_UNVERIFIED_FACE_EVIDENCE')


if __name__ == '__main__': unittest.main()
