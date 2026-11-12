import math
import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus,BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.finite_route import finite_route_evidence


class FiniteRouteAcceptance(unittest.TestCase):
    def shapes(self):
        return (BRepPrimAPI_MakeTorus(10,2,math.pi/2).Shape(),
                BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10,-5,0),gp_Dir(0,1,0)),2,5).Shape())

    def evidence(self,fused):
        torus,cylinder=self.shapes(); model=OCCTBRepModel()
        if fused:
            model.register_shape('JOIN',BRepAlgoAPI_Fuse(torus,cylinder).Shape())
            ids=model.solid_face_provenance('JOIN')['face_ids']
        else:
            model.register_shape('T',torus); model.register_shape('C',cylinder)
            ids=model.solid_face_provenance('T')['face_ids']+model.solid_face_provenance('C')['face_ids']
        torus_id=next(f for f in ids if (model.describe(f)['surface_features'] or {}).get('surface_type')=='TORUS')
        cylinders=[f for f in ids if (model.describe(f)['surface_features'] or {}).get('surface_type')=='CYLINDER']
        return finite_route_evidence(model,{'torus_face_id':torus_id,
            'shared_edge_cylinder_face_ids':cylinders,'support_tangent_point_mm':[10,0,0],
            'section_radius_mm':2})

    def test_real_fused_full_section_join_can_be_candidate(self):
        result=self.evidence(True)
        self.assertTrue(result['local_full_section_route_candidate'])
        self.assertFalse(result['centerline_reconstructed'])
        self.assertFalse(result['engineering_pipe_confirmed'])

    def test_same_support_without_shared_topology_is_not_candidate(self):
        result=self.evidence(False)
        self.assertFalse(result['complete_boundary_circle_verified'])
        self.assertFalse(result['local_full_section_route_candidate'])


if __name__=='__main__': unittest.main()
