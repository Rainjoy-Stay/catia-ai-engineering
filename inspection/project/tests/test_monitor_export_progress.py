import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from monitor_check import export_progress

class ExportProgressTests(unittest.TestCase):
    def test_empty_run(self):
        with tempfile.TemporaryDirectory() as folder:
            result=export_progress(Path(folder))
            self.assertEqual(result['surface_done'],0)
            self.assertIsNone(result['updated_at'])

    def test_reads_durable_surface_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'surfaces').mkdir()
            (root/'export-audit.json').write_text(json.dumps({'expected_body_count':80,'exported_body_count':80,'batch_files':['C:/run/export/batch-1/bulk.stp','C:/run/export/batch-2/bulk.stp']}))
            (root/'surfaces/surface-export-coverage.json').write_text(json.dumps({'registered':100,'exported':40,'errors':[{}]}))
            (root/'surfaces/export-checkpoint.json').write_text(json.dumps({'completed_batches':[{'batch_id':'BATCH_0003','body_mapping':[{'source_path':'Part/set/face'}]}]}))
            result=export_progress(root)
            self.assertEqual(result['surface_done'],40)
            self.assertEqual(result['body_batches'],2)
            self.assertEqual(result['surface_errors'],1)
            self.assertEqual(result['latest_object'],'Part/set/face')
            self.assertFalse(result['export_finished'])

    def test_partial_json_is_tolerated(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'export-audit.json').write_text('{')
            self.assertEqual(export_progress(root)['body_done'],0)
