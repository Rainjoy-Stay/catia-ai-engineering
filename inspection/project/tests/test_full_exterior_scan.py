import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder,BRepPrimAPI_MakeTorus
from OCP.STEPControl import STEPControl_Writer,STEPControl_AsIs
from OCP.TopoDS import TopoDS_Compound


class FullExteriorIntegration(unittest.TestCase):
    def test_two_solid_step_scans_without_inventing_cavity_or_body(self):
        root=Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as folder:
            directory=Path(folder); source=directory/'two_solids.step'; output=directory/'result'
            compound=TopoDS_Compound(); builder=BRep_Builder(); builder.MakeCompound(compound)
            builder.Add(compound,BRepPrimAPI_MakeCylinder(2,10).Shape())
            builder.Add(compound,BRepPrimAPI_MakeTorus(20,2,math.pi/2).Shape())
            writer=STEPControl_Writer(); writer.Transfer(compound,STEPControl_AsIs); writer.Write(str(source))
            process=subprocess.run([sys.executable,str(root/'tools'/'scan_full_step_exteriors.py'),
                str(source),str(output)],timeout=30,capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr)
            result=json.loads((output/'full_exterior_scan.json').read_text(encoding='utf-8'))
            self.assertEqual(result['scanned_count'],2)
            self.assertEqual(result['geometry_counts'].get('STRAIGHT_CYLINDRICAL_EXTERIOR_CANDIDATE'),1)
            self.assertEqual(result['geometry_counts'].get('CIRCULAR_CURVED_EXTERIOR_CANDIDATE'),1)
            self.assertTrue(result['source_unchanged'])
            for record in result['records']:
                self.assertIsNone(record['source_body_index'])
                self.assertFalse(record['candidate']['design_cavity_confirmed'])
                self.assertIsNone(record['candidate']['wall_thickness_mm'])
                self.assertTrue((output/record['detail_file']).is_file())


if __name__=='__main__': unittest.main()
