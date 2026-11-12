import copy
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus,BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.route_seeds import tangent_route_seeds
from standalone.step_pipe_semantics.shared_topology import verify_seed_topology


class SharedTopologyAcceptance(unittest.TestCase):
    def model(self,fused=True):
        torus=BRepPrimAPI_MakeTorus(10,2,math.pi/2).Shape()
        cylinder=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10,-5,0),gp_Dir(0,1,0)),2,5).Shape()
        model=OCCTBRepModel()
        if fused:
            model.register_shape('JOIN',BRepAlgoAPI_Fuse(torus,cylinder).Shape())
            ids=model.solid_face_provenance('JOIN')['face_ids']
        else:
            model.register_shape('T',torus); model.register_shape('C',cylinder)
            ids=model.solid_face_provenance('T')['face_ids']+model.solid_face_provenance('C')['face_ids']
        faces=[model.describe(f) for f in ids]
        return model,faces,tangent_route_seeds(faces)

    def test_brep_roundtrip_confirms_shared_edge_and_face_identity(self):
        model,faces,seeds=self.model()
        with TemporaryDirectory() as folder:
            path=Path(folder)/'join.brep'; model.write_brep('JOIN',path)
            replay=OCCTBRepModel(); replay.load_brep('JOIN',path); replay.solid_face_provenance('JOIN')
            result=verify_seed_topology(replay,seeds,faces)
            self.assertTrue(all(c['compatible'] for c in result['face_identity_checks'].values()))
            self.assertTrue(any(s['topology_verified'] for s in result['seeds']))

    def test_geometrically_tangent_separate_shapes_have_no_shared_identity(self):
        model,faces,seeds=self.model(False)
        result=verify_seed_topology(model,seeds,faces)
        self.assertTrue(seeds)
        self.assertTrue(all(not s['topology_verified'] for s in result['seeds']))

    def test_wrong_saved_face_position_blocks_topology_claim(self):
        model,faces,seeds=self.model(); faces=copy.deepcopy(faces)
        for f in faces:
            if f['shape_id']==seeds[0]['torus_face_id']: f['centroid_mm'][0]+=.01
        result=verify_seed_topology(model,seeds,faces)
        self.assertEqual(result['seeds'][0]['reason'],'FACE_CACHE_IDENTITY_UNCONFIRMED')
        self.assertFalse(result['seeds'][0]['topology_verified'])


if __name__=='__main__': unittest.main()
