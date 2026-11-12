import unittest
from standalone.step_pipe_semantics.route_graph import build_face_route_graph


def seed(torus,cylinders,shared,verified=True):
    return {'torus_face_id':torus,'cylinder_face_ids':cylinders,
            'shared_edge_cylinder_face_ids':shared,'topology_verified':verified}


class FaceGraphAcceptance(unittest.TestCase):
    def graph(self,seeds): return build_face_route_graph([{'source_body_index':1,'seeds':seeds}])['bodies'][0]

    def test_infinite_support_tangency_not_connected(self):
        self.assertEqual(self.graph([seed('T',['C'],[],False)])['edges'],[])

    def test_same_support_disconnected_fragments_stay_separate(self):
        g=self.graph([seed('T1',['C1','C2'],['C1']),seed('T2',['C1','C2'],['C2'])])
        self.assertEqual(len(g['components']),2)

    def test_duplicate_seeds_do_not_inflate_graph(self):
        s=seed('T',['C'],['C']); g=self.graph([s,s])
        self.assertEqual(len(g['edges']),1)
        self.assertEqual(g['components'][0]['cycle_rank'],0)

    def test_branch_retains_no_centerline_claim(self):
        g=self.graph([seed('T',['C1','C2','C3'],['C1','C2','C3'])])
        self.assertEqual(g['components'][0]['classification'],'BRANCHED_FACE_GRAPH')
        self.assertFalse(g['components'][0]['centerline_reconstructed'])

    def test_cycle_distinguished_from_chain(self):
        g=self.graph([seed('T1',['C1','C2'],['C1','C2']),seed('T2',['C1','C2'],['C1','C2'])])
        self.assertEqual(g['components'][0]['cycle_rank'],1)
        self.assertEqual(g['components'][0]['classification'],'CYCLIC_FACE_GRAPH')


if __name__=='__main__': unittest.main()
