import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

SPEC = importlib.util.spec_from_file_location('monitor_check', Path(__file__).parents[1] / 'tools/monitor_check.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PauseTests(unittest.TestCase):
    def test_pause_saves_request_and_blocks_restart_until_drained(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor = MODULE.Monitor(Path(folder))
            monitor.direct_source = Path(folder) / 'model.stp'
            monitor.process = Mock()
            monitor.process.poll.return_value = None
            monitor.status = 'RUNNING'
            monitor.pause()
            self.assertEqual(monitor.status, 'PAUSING')
            self.assertTrue((Path(folder) / 'pause-request.json').exists())
            with self.assertRaises(ValueError):
                monitor.start(workers=1)

    def test_idle_pause_rejected_without_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor = MODULE.Monitor(Path(folder))
            with self.assertRaises(ValueError):
                monitor.pause()
            self.assertFalse((Path(folder) / 'pause-request.json').exists())

    def test_worker_exit_two_means_paused(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor = MODULE.Monitor(Path(folder))
            monitor.process = Mock(stdout=[])
            monitor.process.wait.return_value = 2
            monitor.read()
            self.assertEqual(monitor.status, 'PAUSED')


if __name__ == '__main__':
    unittest.main()
