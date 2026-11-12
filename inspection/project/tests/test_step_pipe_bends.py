import math
import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics import bend_candidate, straight_candidate, connection_candidates


class BendAndConnectionAcceptance(unittest.TestCase):
    def describe(self,shape,sid='BEND',bend=True):
        model = OCCTBRepModel(); solid = model.register_shape(sid,shape)
        faces = [model.describe(f) for f in model.solid_face_provenance(sid)['face_ids']]
        return (bend_candidate if bend else straight_candidate)(solid,faces)

    def bend(self,angle=math.pi/2,axis=None):
        axis = axis or gp_Ax2(gp_Pnt(0,0,0),gp_Dir(0,0,1))
        return BRepAlgoAPI_Cut(BRepPrimAPI_MakeTorus(axis,10,2,angle).Shape(),
                              BRepPrimAPI_MakeTorus(axis,10,1,angle).Shape()).Shape()

    def straight(self,sid,point,direction,length=5,ro=2):
        axis = gp_Ax2(gp_Pnt(*point),gp_Dir(*direction))
        shape = BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(axis,ro,length).Shape(),
                               BRepPrimAPI_MakeCylinder(axis,1,length).Shape()).Shape()
        return self.describe(shape,sid,bend=False)

    def test_quarter_bend_dimensions(self):
        r = self.describe(self.bend())
        self.assertEqual(r['geometry_kind'],'CIRCULAR_HOLLOW_BEND_CANDIDATE')
        self.assertAlmostEqual(r['centerline_bend_radius_mm'],10)
        self.assertAlmostEqual(r['sweep_angle_rad'],math.pi/2)
        self.assertAlmostEqual(r['wall_thickness_mm'],1)
        self.assertEqual(r['bend_radius_compliance'],'NOT_EVALUATED')

    def test_rotated_translated_45_degree_bend(self):
        r = self.describe(self.bend(math.pi/4,gp_Ax2(gp_Pnt(23,-41,8),gp_Dir(1,2,3))))
        self.assertEqual(r['geometry_kind'],'CIRCULAR_HOLLOW_BEND_CANDIDATE')
        self.assertAlmostEqual(r['centerline_length_mm'],10*math.pi/4)

    def test_solid_torus_is_not_hollow_bend(self):
        self.assertEqual(self.describe(BRepPrimAPI_MakeTorus(10,2,math.pi/2).Shape())['geometry_kind'],'UNDETERMINED')

    def test_full_loop_is_unsupported(self):
        self.assertEqual(self.describe(self.bend(2*math.pi))['geometry_kind'],'UNDETERMINED')

    def test_bend_step_roundtrip(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        with TemporaryDirectory() as folder:
            path = Path(folder)/'bend.step'
            writer = STEPControl_Writer(); writer.Transfer(self.bend(),STEPControl_AsIs)
            writer.Write(str(path))
            model = OCCTBRepModel(); manifest = model.load_step(path)
            solid = next(s for s in manifest['shapes'] if s['shape_id'].startswith('STEP_SOLID_'))
            faces = [model.describe(f) for f in model.solid_face_provenance(solid['shape_id'])['face_ids']]
            r = bend_candidate(solid,faces)
            self.assertEqual(r['geometry_kind'],'CIRCULAR_HOLLOW_BEND_CANDIDATE')
            self.assertAlmostEqual(r['centerline_bend_radius_mm'],10)

    def test_bend_to_straight_geometric_connection_only(self):
        bend = self.describe(self.bend())
        port = bend['ports'][0]
        straight = self.straight('STRAIGHT',port['center_mm'],port['outward_direction'])
        matches = connection_candidates([bend,straight])
        self.assertEqual(len(matches),1)
        self.assertFalse(matches[0]['verified'])
        self.assertFalse(matches[0]['ambiguous'])
        self.assertEqual(matches[0]['status'],'NOT_EVALUATED')

    def test_wrong_radius_and_gap_rejected(self):
        a = self.straight('A',(0,0,0),(0,0,1))
        wrong = self.straight('B',(0,0,5),(0,0,1),ro=3)
        gap = self.straight('C',(0,0,5.1),(0,0,1))
        self.assertEqual(connection_candidates([a,wrong,gap]),[])

    def test_coincident_duplicate_not_a_connection(self):
        a = self.straight('A',(0,0,0),(0,0,1))
        b = self.straight('B',(0,0,0),(0,0,1))
        self.assertEqual(connection_candidates([a,b]),[])

    def test_competing_connections_stay_ambiguous(self):
        a = self.straight('A',(0,0,0),(0,0,1))
        b = self.straight('B',(0,0,5),(0,0,1))
        c = self.straight('C',(0,0,5),(0,0,1))
        matches = connection_candidates([a,b,c])
        self.assertEqual(len(matches),2)
        self.assertTrue(all(m['ambiguous'] and not m['verified'] for m in matches))


if __name__ == '__main__': unittest.main()
