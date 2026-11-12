import unittest
from tests import test_step_grouped_finite_routes as fixtures
from standalone.step_pipe_semantics.grouped_finite_route import grouped_finite_route_evidence
from standalone.step_pipe_semantics.shared_section_boundary import shared_section_boundary

class SectionBoundaryAcceptance(unittest.TestCase):
    def setup_geometry(self):
        model,ids,seed=fixtures.GroupedRouteAcceptance().evidence()
        grouped=grouped_finite_route_evidence(model,seed,ids)['same_support_torus_face_ids']
        return model,grouped,seed
    def test_split_shared_circle_closes_without_uv_assumption(self):
        model,ids,seed=self.setup_geometry(); r=shared_section_boundary(model,seed,ids,[0,1,0])
        self.assertTrue(r['complete_boundary_circle_verified']); self.assertFalse(r['design_cavity_confirmed'])
        self.assertFalse(r['trim_coverage_confirmed'])
        self.assertEqual(r['boundary_evidence_class'],'COMPLETE_LOCAL_SHARED_CIRCLE')
        self.assertTrue(r['eligible_for_centerline_continuation_test'])
    def test_missing_quarter_stays_incomplete(self):
        model,ids,seed=self.setup_geometry()
        r=shared_section_boundary(model,seed,ids[1:],[0,1,0])
        self.assertFalse(r['complete_boundary_circle_verified'])
        self.assertEqual(r['boundary_evidence_class'],'ANALYTIC_PARTIAL_OPEN_SECTION')
        self.assertFalse(r['eligible_for_centerline_continuation_test'])
    def test_wrong_section_plane_rejected(self):
        model,ids,seed=self.setup_geometry()
        r=shared_section_boundary(model,seed,ids,[0,0,1])
        self.assertFalse(r['complete_boundary_circle_verified'])
        self.assertEqual(r['boundary_evidence_class'],'UNRESOLVED_BOUNDARY')
    def test_single_quarter_cannot_enter_continuation(self):
        model,ids,seed=self.setup_geometry()
        candidates=[shared_section_boundary(model,seed,[fid],[0,1,0]) for fid in ids]
        quarters=[r for r in candidates if r['quarter_circle_only']]
        self.assertTrue(quarters)
        self.assertTrue(all(not r['eligible_for_centerline_continuation_test'] for r in quarters))

if __name__=='__main__': unittest.main()
