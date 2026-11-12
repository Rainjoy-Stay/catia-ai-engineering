import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_pipe_semantics.bore_evidence import inspect_straight_bore


class BoreWitnessAcceptance(unittest.TestCase):
    def inspect(self,bore_length):
        shape=BRepPrimAPI_MakeCylinder(2,10).Shape()
        if bore_length: shape=BRepAlgoAPI_Cut(shape,BRepPrimAPI_MakeCylinder(1,bore_length).Shape()).Shape()
        model=OCCTBRepModel(); model.register_shape('TEST',shape)
        return inspect_straight_bore(model,'TEST',[[0,0,0],[0,0,10]],1,2)

    def test_open_hollow_passage_and_sampled_wall(self):
        r=self.inspect(10)
        self.assertTrue(r['clear_passage_witness_confirmed'])
        self.assertEqual(r['valid_wall_sample_count'],40)
        self.assertAlmostEqual(r['sampled_wall_min_mm'],1)
        self.assertFalse(r['engineering_pipe_confirmed'])
        self.assertFalse(r['design_cavity_confirmed'])
        self.assertFalse(r['fluid_channel_confirmed'])
        self.assertEqual(r['evidence_scope'],'CLEAR_TEST_CYLINDER_RELATIVE_TO_THIS_SOLID_ONLY')

    def test_blind_bore_not_continuous(self):
        self.assertFalse(self.inspect(8)['clear_passage_witness_confirmed'])

    def test_solid_not_continuous(self):
        self.assertFalse(self.inspect(0)['clear_passage_witness_confirmed'])


if __name__=='__main__': unittest.main()
