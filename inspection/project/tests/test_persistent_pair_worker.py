import tempfile
import unittest
from pathlib import Path

from catia_checker.large_single_part import _PersistentPairWorker


SERVER = '''
import json, sys, time
count = 0
for line in sys.stdin:
    request = json.loads(line)
    if request["first"].endswith("sleep"):
        time.sleep(2)
    count += 1
    response = {"ok": True, "result": {"request_count": count}}
    print("PAIR_RESULT " + json.dumps(response), flush=True)
'''


class PersistentPairWorkerTests(unittest.TestCase):
    def test_process_is_reused_across_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "server.py"
            script.write_text(SERVER, encoding="utf-8")
            worker = _PersistentPairWorker(script)
            try:
                first = worker.request(Path("a"), Path("b"), 0.0, 2.0)
                second = worker.request(Path("a"), Path("c"), 0.0, 2.0)
            finally:
                worker.close()
        self.assertEqual(first["request_count"], 1)
        self.assertEqual(second["request_count"], 2)

    def test_timeout_restarts_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "server.py"
            script.write_text(SERVER, encoding="utf-8")
            worker = _PersistentPairWorker(script)
            try:
                with self.assertRaises(TimeoutError):
                    worker.request(Path("sleep"), Path("b"), 0.0, 0.1)
                result = worker.request(Path("a"), Path("b"), 0.0, 2.0)
            finally:
                worker.close()
        self.assertEqual(result["request_count"], 1)


if __name__ == "__main__":
    unittest.main()
