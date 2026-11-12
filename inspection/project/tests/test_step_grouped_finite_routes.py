import math
import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus,BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.ShapeUpgrade import ShapeUpgrade_ShapeDivideClosed
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.route_seeds import tangent_route_seeds
from standalone.step_pipe_semantics.grouped_finite_route import grouped_finite_route_evidence


class GroupedRouteAcceptance(unittest.TestCase):
    def evidence(self):
        torus=BRepPrimAPI_MakeTorus(10,2,math.pi/2).Shape()
        cylinder=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10,-5,0),gp_Dir(0,1,0)),2,5).Shape()
        split=ShapeUpgrade_ShapeDivideClosed(BRepAlgoAPI_Fuse(torus,cylinder).Shape())
        split.SetNbSplitPoints(3); split.Perform()
        model=OCCTBRepModel(); model.register_shape('SPLIT',split.Result())
        ids=model.solid_face_provenance('SPLIT')['face_ids']; faces=[model.describe(f) for f in ids]
        return model,ids,tangent_route_seeds(faces)[0]

    def test_four_split_quarters_can_recover_local_candidate(self):
        model,ids,seed=self.evidence(); r=grouped_finite_route_evidence(model,seed,ids)
        self.assertGreaterEqual(len(r['same_support_torus_face_ids']),4)
        self.assertTrue(r['complete_boundary_circle_verified'])
        self.assertTrue(r['local_grouped_route_candidate'])
        self.assertFalse(r['centerline_reconstructed'])

    def test_missing_quarter_not_a_closed_section(self):
        model,ids,seed=self.evidence()
        grouped=grouped_finite_route_evidence(model,seed,ids)['same_support_torus_face_ids']
        r=grouped_finite_route_evidence(model,seed,[i for i in ids if i!=grouped[0]])
        self.assertFalse(r['complete_boundary_circle_verified'])
        self.assertFalse(r['local_grouped_route_candidate'])

    def test_early_boundary_rejection_does_not_claim_trim_coverage(self):
        model,ids,seed=self.evidence()
        grouped=grouped_finite_route_evidence(model,seed,ids)['same_support_torus_face_ids']
        partial=[i for i in ids if i!=grouped[0]]
        result=grouped_finite_route_evidence(model,seed,partial,sample_only_complete_boundary=True)
        self.assertFalse(result['local_grouped_route_candidate'])
        self.assertEqual(result['trim_coverage_samples'],[])
        self.assertIsNone(result['sampled_full_section_continuation'])
        self.assertEqual(result['coverage_deferred_reason'],'INCOMPLETE_BOUNDARY_ALREADY_PREVENTS_CANDIDATE')


if __name__=='__main__': unittest.main()
