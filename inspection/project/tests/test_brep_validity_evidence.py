import unittest
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS_Shell,TopoDS_Solid
from OCP.TopAbs import TopAbs_FACE
from catia_checker.occt_brep import _subshapes
from catia_checker.brep_validity_evidence import validity_evidence

class ValidityDiagnosticAcceptance(unittest.TestCase):
    def test_closed_box_has_no_reported_errors(self):
        r=validity_evidence(BRepPrimAPI_MakeBox(1,1,1).Shape(),'BOX')
        self.assertTrue(r['kernel_valid']); self.assertTrue(r['diagnostic_complete']); self.assertFalse(r['issues'])
        self.assertEqual(r['status'],'NOT_EVALUATED')
    def test_missing_face_solid_stays_invalid_without_healing(self):
        box=BRepPrimAPI_MakeBox(1,1,1).Shape(); builder=BRep_Builder(); shell=TopoDS_Shell(); builder.MakeShell(shell)
        for face in _subshapes(box,TopAbs_FACE)[:-1]: builder.Add(shell,face)
        solid=TopoDS_Solid(); builder.MakeSolid(solid); builder.Add(solid,shell)
        r=validity_evidence(solid,'OPEN')
        self.assertFalse(r['kernel_valid']); self.assertTrue(r['diagnostic_complete']); self.assertTrue(r['issues'])
        self.assertFalse(r['geometry_modified'])

if __name__=='__main__': unittest.main()
