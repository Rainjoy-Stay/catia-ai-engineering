import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from io import StringIO

from tools.inspect_active_large_single_part import run_exact_child
from catia_checker.large_single_part import build_large_single_part_result


class FakeProcess:
    def __init__(self, output="", returncode=0, timeout=False):
        self.stdout, self.returncode, self.timeout = StringIO(output), returncode, timeout
        self.killed = False
    def kill(self): self.killed = True; self.returncode = -9
    def poll(self): return self.returncode
    def wait(self, timeout=None):
        if self.timeout and not self.killed: raise subprocess.TimeoutExpired("child", timeout)
        return self.returncode


class LargeSinglePartProcessTests(unittest.TestCase):
    def test_pair_errors_are_counted_in_unified_error_total(self):
        bundle={"findings":[],"resumed_pair_count":0,"checkpoint_path":"resume.json","analysis":{"exact_pair_count":1,"findings":[],"errors":[{"code":"EXACT_PAIR_TIMEOUT"}],"shell_or_surface_count":0,"coverage_complete":False,"truncated":False}}
        result=build_large_single_part_result(bundle,document="x",rules={"ruleset_id":"r"},run_id="id",generated_at="now")
        self.assertEqual(result["counts"]["ERROR"],1)
        self.assertFalse(result["confidence_budget"]["is_complete"])
        self.assertEqual(result["resume_status"]["pending_pairs"],1)
        self.assertTrue(result["resume_status"]["needs_resume"])

    def test_budget_deferred_pair_is_not_engine_error(self):
        bundle={"findings":[],"analysis":{"exact_pair_count":1,"findings":[],"errors":[{"code":"EXACT_PAIR_DEFERRED_BUDGET"}],"shell_or_surface_count":0,"coverage_complete":False,"truncated":False}}
        result=build_large_single_part_result(bundle,document="x",rules={"ruleset_id":"r"},run_id="id",generated_at="now")
        self.assertEqual(result["counts"]["ERROR"],0); self.assertEqual(result["counts"]["NOT_EVALUATED"],1)
        self.assertEqual(result["resume_status"]["deferred_by_budget_pairs"],1)

    def test_progress_is_forwarded_and_result_required(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "result.json"; target.write_text("{}", encoding="utf-8")
            events = []; fake = FakeProcess(json.dumps({"stage":"EXACT_PAIRS","completed":100})+"\n")
            run_exact_child(Path("part.stp"), target, Path("rules.json"), 5,
                            popen_factory=lambda *a, **k: fake, progress=events.append)
            self.assertEqual(events[0]["stage"], "EXACT_PAIRS")

    def test_timeout_kills_child(self):
        fake = FakeProcess(timeout=True)
        with self.assertRaisesRegex(TimeoutError, "exceeded 2 seconds"):
            run_exact_child(Path("part.stp"), Path("missing.json"), Path("rules.json"), 2,
                            popen_factory=lambda *a, **k: fake)
        self.assertTrue(fake.killed)

    def test_nonzero_exit_is_reported(self):
        fake = FakeProcess("OCCT failure", returncode=7)
        with self.assertRaisesRegex(RuntimeError, "code 7"):
            run_exact_child(Path("part.stp"), Path("missing.json"), Path("rules.json"), 3,
                            popen_factory=lambda *a, **k: fake)


if __name__ == "__main__": unittest.main()
