import json
import tempfile
import unittest
from pathlib import Path
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound,TopoDS_Shell
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopAbs import TopAbs_FACE
from catia_checker.occt_brep import _subshapes
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
from OCP.STEPControl import STEPControl_Writer,STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from tools.scan_new_export_batch import worker
from tools.review_surface_recovery_pilot import digest

class ExplicitBodyExportAcceptance(unittest.TestCase):
    def test_non_solid_export_is_preserved_without_volume_authority(self):
        builder=BRep_Builder(); shell=TopoDS_Shell(); builder.MakeShell(shell)
        for face in _subshapes(BRepPrimAPI_MakeBox(1,1,1).Shape(),TopAbs_FACE)[:-1]: builder.Add(shell,face)
        with tempfile.TemporaryDirectory() as folder:
            step=Path(folder)/'open_shell.stp'; output=Path(folder)/'evidence.json'
            writer=STEPControl_Writer(); writer.Transfer(shell,STEPControl_AsIs)
            self.assertEqual(writer.Write(str(step)),IFSelect_RetDone); before=digest(step)
            worker(step,7,output); result=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['solid_count'],0); evidence=result['non_solid_geometry']
            self.assertEqual(evidence['face_count'],5); self.assertTrue(Path(evidence['cache_file']).is_file())
            self.assertIsNone(evidence['root_volume_mm3']); self.assertFalse(evidence['design_cavity_confirmed'])
            self.assertEqual(evidence['solid_interference_evaluation'],'NOT_EVALUATED'); self.assertEqual(digest(step),before)
    def test_one_exported_body_can_contain_two_solids_without_cavity_claim(self):
        builder=BRep_Builder(); compound=TopoDS_Compound(); builder.MakeCompound(compound)
        for x in (0,20):
            builder.Add(compound,BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,0,0),gp_Dir(0,0,1)),2,10).Shape())
        with tempfile.TemporaryDirectory() as folder:
            step=Path(folder)/'one_body.stp'; output=Path(folder)/'evidence.json'
            writer=STEPControl_Writer(); writer.Transfer(compound,STEPControl_AsIs)
            self.assertEqual(writer.Write(str(step)),IFSelect_RetDone); before=digest(step)
            worker(step,42,output); result=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['solid_count'],2); self.assertTrue(result['body_split_into_multiple_solids'])
            self.assertEqual(result['source_body_index'],42); self.assertEqual(digest(step),before)
            for record in result['records']:
                self.assertTrue(record['solid']['shape_id'].startswith('NEW_BODY_000042::'))
                self.assertEqual(record['candidate']['status'],'NOT_EVALUATED')
                self.assertFalse(record['candidate']['design_cavity_confirmed'])
                self.assertIsNone(record['candidate']['wall_thickness_mm'])

if __name__=='__main__': unittest.main()
