import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from catia_checker.occt_brep import OCCTBRepModel
from standalone.large_single_part_analysis import merge_batch_manifests, partition_body_names
from standalone.large_single_part_analysis.batching import MultiBatchBackend

def shape(name,x1,x2): return {"shape_id":name,"solid_count":1,"bounds_mm":{"min":[x1,0,0],"max":[x2,1,1]}}
def batch(name,*shapes): return {"batch_id":name,"manifest":{"root_shape_id":"ROOT","shapes":[{"shape_id":"ROOT"},*shapes]}}

class LargeSinglePartBatchingTests(unittest.TestCase):
    def test_partition_preserves_every_body_once(self):
        result=partition_body_names([f"B{i}" for i in range(7)],3)
        self.assertEqual([len(x) for x in result],[3,3,1]); self.assertEqual(sum(result,[]),[f"B{i}" for i in range(7)])
    def test_duplicate_names_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"unique"): partition_body_names(["A","A"],2)
    def test_global_sweep_finds_cross_batch_candidate(self):
        plan=merge_batch_manifests([batch("P1",shape("A",0,2)),batch("P2",shape("B",1,3),shape("C",20,21))])
        self.assertEqual(plan["broad_phase"]["pairs"],[["P1::A","P2::B"]])
        self.assertEqual(plan["candidate_batch_groups"][0]["batch_ids"],["P1","P2"])
        self.assertTrue(plan["coverage_complete"]); self.assertFalse(plan["mesh_used"])
    def test_missing_bounds_closes_completeness(self):
        plan=merge_batch_manifests([batch("P1",{"shape_id":"A","solid_count":1,"bounds_mm":None})])
        self.assertFalse(plan["coverage_complete"])
    def test_cross_batch_exact_common_volume(self):
        a=OCCTBRepModel(); b=OCCTBRepModel(); a.register_shape("A",BRepPrimAPI_MakeBox(2,2,2).Shape()); b.register_shape("B",BRepPrimAPI_MakeBox(gp_Pnt(1,0,0),2,2,2).Shape())
        backend=MultiBatchBackend({"P1":a,"P2":b},{"P1::A":{"batch_id":"P1","local_shape_id":"A"},"P2::B":{"batch_id":"P2","local_shape_id":"B"}})
        self.assertAlmostEqual(backend.distance("P1::A","P2::B")["minimum_distance_mm"],0)
        self.assertAlmostEqual(backend.common_volume("P1::A","P2::B")["intersection_volume_mm3"],4)

if __name__=="__main__": unittest.main()
