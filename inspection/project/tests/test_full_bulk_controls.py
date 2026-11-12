import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from monitor_check import Monitor
from run_full_bulk_check import load_completed_export

class FullBulkControlTests(unittest.TestCase):
    def fixture(self, root):
        step=root/'surface.stp';step.write_bytes(b'STEP')
        step.with_suffix('.mapping.json').write_text(json.dumps({'file':step.name,'size_bytes':4,'sha256':hashlib.sha256(b'STEP').hexdigest()}))
        (root/'recovery-file-verification.json').write_text('[]')
        (root/'export-audit.json').write_text(json.dumps({'status':'EXPORTED','source':'model.CATPart','batch_files':[str(step)],'body_mapping':[],'errors':[]}))
        return step

    def test_snapshot_resume_requires_original_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);step=self.fixture(root)
            self.assertEqual(load_completed_export(root,'model.CATPart')[0],[str(step)])
            step.write_bytes(b'EDIT')
            with self.assertRaisesRegex(RuntimeError,'changed'):load_completed_export(root,'model.CATPart')

    def test_wrong_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root)
            with self.assertRaises(RuntimeError):load_completed_export(root,'other.CATPart')

    def test_attach_pause_uses_marker_not_termination(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root)
            monitor=Monitor(root);monitor.full_bulk=True;monitor.control_existing=True;monitor.watch_pid=123;monitor.status='RUNNING'
            with patch('monitor_check.process_alive',return_value=True):
                monitor.pause()
            self.assertTrue((root/'pause-request.json').exists())
            self.assertEqual(monitor.status,'PAUSING')

    def test_export_phase_refuses_pause(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor=Monitor(Path(folder));monitor.full_bulk=True;monitor.status='RUNNING';monitor.watch_pid=123
            with patch('monitor_check.process_alive',return_value=True):
                with self.assertRaisesRegex(ValueError,'导出'):monitor.pause()

    def test_original_runner_exit_zero_with_pause_is_paused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root);(root/'pause-request.json').write_text('{}')
            events=root/'events.jsonl';events.write_text(json.dumps({'stage':'RUN_END','exit_code':0,'time':'2026-10-01T02:30:00'})+'\n')
            monitor=Monitor(root);monitor.control_existing=True;monitor.full_bulk=True;monitor.watch_events=events
            self.assertEqual(monitor.snapshot()['status'],'PAUSED')
            self.assertFalse(monitor.snapshot()['watch_only'])

    def test_resume_blocked_while_original_process_alive(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor=Monitor(Path(folder));monitor.status='PAUSED';monitor.control_existing=True;monitor.watch_pid=123
            with patch('monitor_check.process_alive',return_value=True):
                with self.assertRaisesRegex(ValueError,'正在运行'):monitor.start()

    def test_resume_command_uses_snapshot_not_reexport(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root);(root/'pause-request.json').write_text('{}')
            monitor=Monitor(root);monitor.full_bulk=True;monitor.control_existing=True;monitor.status='PAUSED'
            with patch('monitor_check.process_alive',return_value=False),patch('monitor_check.subprocess.Popen') as launch,patch('monitor_check.threading.Thread'):
                monitor.start(workers=3,budget_minutes=20)
            command=launch.call_args.args[0]
            self.assertIn('--resume-check',command)
            self.assertNotIn('--resume-export',command)
            self.assertIn('3',command)
            self.assertFalse((root/'pause-request.json').exists())
