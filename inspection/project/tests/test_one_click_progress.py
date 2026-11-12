import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[2]/"scripts"/"one_click_check.py"
SPEC=importlib.util.spec_from_file_location("one_click_check",PATH); MODULE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)

class OneClickProgressTests(unittest.TestCase):
    def test_progress_metrics_accumulate_without_losing_resume_state(self):
        value={}
        events=[{"stage":"CATIA_BATCH_EXPORT_COMPLETE","batch_number":2,"body_count":20},
          {"stage":"CHECKPOINT_LOADED","resumed_pair_count":9},
          {"stage":"CHECKPOINT_RESUME_PLAN","total_pairs":35,"pending_pairs":26},
          {"stage":"EXACT_PAIR_PRIMARY_COMPLETE","status":"COMPLETE"},
          {"stage":"EXACT_PAIR_PRIMARY_COMPLETE","status":"TIMEOUT"},
          {"stage":"EXACT_PAIR_PRIMARY_COMPLETE","status":"DEFERRED"},
          {"stage":"EXACT_PAIR_RETRY_PLAN","retry_count":1,"retry_timeout_seconds":90}]
        for event in events: MODULE.update_progress_metrics(value,event)
        self.assertEqual(value["resumed_pairs"],9); self.assertEqual(value["pair_attempts_completed"],3)
        self.assertEqual(value["pair_successes"],1); self.assertEqual(value["pair_timeouts"],1)
        self.assertEqual(value["retry_count"],1)
        self.assertEqual(value["pair_deferred_by_budget"],1)

    def test_face_auto_options_are_registered(self):
        source=PATH.read_text(encoding="utf-8")
        self.assertIn("--large-single-part-face-auto",source)
        self.assertIn('record("完成", "PARTIAL" if incomplete else "PASS"',source)

    def test_active_large_single_part_captures_evidence_before_word_report(self):
        source=PATH.read_text(encoding="utf-8")
        capture=source.index('run_evidence([str(ROOT / "scripts" / "capture_finding_evidence.py")')
        report=source.index('run("Word报告生成"',capture)
        self.assertLess(capture,report)

    def test_offline_large_single_part_imports_source_for_required_screenshot(self):
        source=PATH.read_text(encoding="utf-8")
        self.assertIn('"--source-file", str(args.large_single_part_source)',source)
        self.assertNotIn('"SKIPPED", "源文件离线检查',source)

if __name__=="__main__": unittest.main()
