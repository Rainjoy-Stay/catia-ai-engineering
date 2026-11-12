import importlib.util
from pathlib import Path
import unittest
from docx import Document


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "generate_check_report.py"
SPEC = importlib.util.spec_from_file_location("generate_check_report", MODULE_PATH)
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


class ReportStatusTests(unittest.TestCase):
    def test_resume_status_is_rendered_as_summary_table(self):
        doc=Document(); REPORT._add_summary(doc,{"counts":{},"source":{"cleanup_verified":True},"confidence_budget":{"checked":[],"not_checked":["pending"],"degraded":[]},"resume_status":{"total_candidate_pairs":35,"completed_pairs":11,"newly_completed_pairs":2,"resumed_pairs":9,"timeout_pairs":24,"failed_pairs":0,"pending_pairs":24,"completion_percent":31.43,"needs_resume":True}})
        cells=[cell.text for table in doc.tables for row in table.rows for cell in row.cells]
        self.assertIn("断点复用",cells); self.assertIn("31.43%",cells)
        self.assertIn("未完成，不得判整机通过",cells)

    def test_empty_or_incomplete_run_is_not_pass(self):
        status, _ = REPORT._overall_status({"counts": {}, "confidence_budget": {}})
        self.assertNotEqual(status, "通过")

    def test_only_complete_approved_run_can_pass(self):
        data = {
            "counts": {}, "source": {"truncated": False, "cleanup_verified": True},
            "confidence_budget": {"checked": ["DMU"], "not_checked": [], "degraded": []},
            "applied_rules": {"routing": {"threshold_status": "APPROVED"}},
        }
        self.assertEqual(REPORT._overall_status(data)[0], "通过")

    def test_semantic_failure_controls_overall_status(self):
        data = {
            "counts": {}, "source": {"truncated": False, "cleanup_verified": True},
            "confidence_budget": {"checked": ["OCCT"], "not_checked": [], "degraded": []},
            "applied_rules": {"routing": {"threshold_status": "APPROVED"}},
            "solid_interaction_assessments": {"disposition_counts": {"FAIL": 1}},
        }
        self.assertEqual(REPORT._overall_status(data)[0], "不通过")

    def test_opening_interface_rows_expose_engineering_evidence(self):
        rows = dict(REPORT._opening_interface_report_rows({"metadata": {
            "opening_interface": {
                "opening_id": "OPEN-1", "nozzle_id": "NOZZLE-1",
                "measurements": {"axis_offset_mm": 0.2, "axis_angle_deg": 0.1,
                                 "opening_radius_mm": 20.2, "nozzle_outer_radius_mm": 20,
                                 "radial_clearance_mm": 0.2, "host_wall_thickness_mm": 10,
                                 "crosses_opening_plane": True, "spans_host_wall": True},
                "evidence": {"exact_brep": True, "boundary_complete": True,
                             "host_discontinuity_confirmed": True},
                "reason_labels": [],
            }}}))
        self.assertIn("10.000 mm", rows["筒壁贯通"])
        self.assertIn("跨越完整筒壁=是", rows["筒壁贯通"])
        self.assertIn("网格参与最终判定=否", rows["判定证据"])

    def test_skipped_opening_scope_cannot_pass(self):
        data = {
            "counts": {}, "source": {"truncated": False, "cleanup_verified": True},
            "confidence_budget": {"checked": ["DMU"],
                                  "not_checked": ["接管—开孔接口自动检查未执行"],
                                  "degraded": []},
            "applied_rules": {"routing": {"threshold_status": "APPROVED"}},
        }
        self.assertEqual(REPORT._overall_status(data)[0], "检查不完整 / 需要复核")

    def test_pipe_candidate_review_is_rendered_and_stays_not_evaluated(self):
        doc = Document()
        REPORT._add_pipe_candidate_review(doc, {"pipe_candidate_review": {
            "excluded_straight_cylinder_count": 4,
            "candidates": [{"body_index": 741, "name": "PIPE-A",
                            "evidence_tier": "COMPOSITE_ROUTE_REVIEW",
                            "status": "NOT_EVALUATED"}],
        }})
        text = "\n".join(p.text for p in doc.paragraphs)
        cells = [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
        self.assertIn("管路候选复核", text)
        self.assertIn("NOT_EVALUATED", cells)
        self.assertIn("已排除 4 个", text)


if __name__ == "__main__":
    unittest.main()
