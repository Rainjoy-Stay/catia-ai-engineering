import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from catia_checker.occt_brep import OCCTBRepModel
from tools.recheck_turbine_source_step import extract_entities


class SourceExtractionTests(unittest.TestCase):
    def test_dependency_extraction_keeps_exact_geometry_and_source_file(self):
        with TemporaryDirectory() as folder:
            source, subset = Path(folder) / 'source.step', Path(folder) / 'subset.step'
            writer = STEPControl_Writer()
            writer.Transfer(BRepPrimAPI_MakeBox(2, 3, 4).Shape(), STEPControl_AsIs)
            writer.Write(str(source))
            before = source.read_bytes()
            text = before.decode('latin-1')
            solid_id = int(re.search(r'#(\d+)\s*=\s*MANIFOLD_SOLID_BREP', text).group(1))
            audit = extract_entities(source, {solid_id}, subset)
            manifest = OCCTBRepModel().load_step(subset, lightweight=False)
            solids = [s for s in manifest['shapes'] if s['shape_id'] != 'STEP_ROOT']
            self.assertEqual(len(solids), 1)
            self.assertTrue(solids[0]['valid'])
            self.assertAlmostEqual(solids[0]['volume_mm3'], 24)
            self.assertEqual(solids[0]['face_count'], 6)
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(audit['geometry_records_changed'])

    def test_missing_source_entity_rejected(self):
        with TemporaryDirectory() as folder:
            source, subset = Path(folder) / 'source.step', Path(folder) / 'subset.step'
            source.write_text('DATA;\n#1=GEOMETRIC_REPRESENTATION_CONTEXT(3);\nENDSEC;', encoding='latin-1')
            with self.assertRaisesRegex(RuntimeError, 'Missing STEP entity'):
                extract_entities(source, {99}, subset)


if __name__ == '__main__':
    unittest.main()
