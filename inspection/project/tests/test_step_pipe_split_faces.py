import copy
import unittest
from OCP.ShapeUpgrade import ShapeUpgrade_ShapeDivideClosed
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics import straight_candidate


class SplitWallAcceptance(unittest.TestCase):
    def evidence(self, hollow=True):
        shape=BRepPrimAPI_MakeCylinder(2,10).Shape()
        if hollow: shape=BRepAlgoAPI_Cut(shape,BRepPrimAPI_MakeCylinder(1,10).Shape()).Shape()
        split=ShapeUpgrade_ShapeDivideClosed(shape); split.SetNbSplitPoints(1); split.Perform()
        model=OCCTBRepModel(); solid=model.register_shape('SPLIT',split.Result())
        faces=[model.describe(f) for f in model.solid_face_provenance('SPLIT')['face_ids']]
        return solid,faces

    def test_real_split_hollow_wall(self):
        solid,faces=self.evidence()
        self.assertGreater(len(faces),4)
        r=straight_candidate(solid,faces)
        self.assertEqual(r['geometry_kind'],'STRAIGHT_HOLLOW_CANDIDATE')
        self.assertEqual([len(g) for g in r['wall_face_groups']],[2,2])

    def test_split_solid_cylinder_stays_nonpipe(self):
        self.assertEqual(straight_candidate(*self.evidence(False))['geometry_kind'],'UNDETERMINED')

    def test_missing_wall_fragment_rejected(self):
        solid,faces=self.evidence(); faces=faces[:-1]
        self.assertEqual(straight_candidate(solid,faces)['reason'],'INCOMPLETE_OR_UNVERIFIED_FACE_EVIDENCE')

    def test_changed_wall_axis_not_merged(self):
        solid,faces=self.evidence(); faces=copy.deepcopy(faces)
        f=next(f['surface_features'] for f in faces if f['surface_features']['surface_type']=='CYLINDER')
        f['axis_origin_mm'][0]+=.2
        self.assertEqual(straight_candidate(solid,faces)['geometry_kind'],'UNDETERMINED')

    def test_partial_wall_area_not_accepted(self):
        solid,faces=self.evidence(); faces=copy.deepcopy(faces)
        next(f['surface_features'] for f in faces if f['surface_features']['surface_type']=='CYLINDER')['area_mm2']*=.5
        self.assertEqual(straight_candidate(solid,faces)['geometry_kind'],'UNDETERMINED')


if __name__=='__main__': unittest.main()
