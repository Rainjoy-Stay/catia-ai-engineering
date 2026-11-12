import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from docx import Document

from catia_checker.opening_interfaces import build_opening_interface_bundle
from catia_checker.routing_rules import validate_rules
from catia_checker.snapshots import compare_snapshots, create_snapshot


PROJECT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT / "tools" / "generate_check_report.py"
SPEC = importlib.util.spec_from_file_location("opening_e2e_report", REPORT_PATH)
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


def exact_facts(offset_mm=0.0):
    return {
        "source": "OCCT_BREP",
        "opening_face_records": [{
            "face_id": "HOST-FACE", "normal": [1, 0, 0],
            "host_wall_thickness_mm": 10, "host_discontinuity_confirmed": True,
            "exact_brep": True, "circular_inner_boundaries": [{
                "boundary_id": "OPEN-1", "center_mm": [100, 0, offset_mm],
                "radius_mm": 20.2, "closed": True, "exact_brep": True,
            }],
        }],
        "cylindrical_surface_records": [{
            "surface_id": "OUTER", "component_id": "NOZZLE-1",
            "surface_type": "CYLINDER", "axis_origin_mm": [50, 0, 0],
            "axis_direction": [1, 0, 0], "radius_mm": 20,
            "axis_limits_mm": [0, 70], "exact_brep": True,
        }, {
            "surface_id": "INNER", "component_id": "NOZZLE-1",
            "surface_type": "CYLINDER", "axis_origin_mm": [50, 0, 0],
            "axis_direction": [1, 0, 0], "radius_mm": 15,
            "axis_limits_mm": [0, 70], "exact_brep": True,
        }],
    }


def result_payload(bundle, rules):
    counts = {key: 0 for key in
              ("PASS", "WARN", "FAIL", "NOT_EVALUATED", "EXEMPTED", "ERROR")}
    for finding in bundle["findings"]:
        counts[finding["status"]] += 1
    return {
        "schema_version": "1.1.0", "document": "SyntheticOpening.CATProduct",
        "ruleset_id": rules["ruleset_id"], "applied_rules": rules,
        "run_id": "OPENING-E2E", "generated_at": "2026-09-14T00:00:00Z",
        "source": {"method": "OCCT_EXACT_BREP", "computation_type": "EXACT_BREP",
                   "truncated": False, "cleanup_verified": True,
                   "source_saved_by_tool": False},
        "counts": counts, "findings": bundle["findings"],
        "opening_interface_analysis": bundle,
        "confidence_budget": {"checked": ["接管—开孔精确接口"],
                              "not_checked": [], "assumptions": [], "degraded": []},
        "audit": {"geometry_authority": "OCCT精确B-Rep",
                  "source_model_modified": False, "exceptions": []},
    }


class OpeningInterfaceEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads((PROJECT / "config" / "rules-active.json").read_text(
            encoding="utf-8"))
        validate_rules(cls.rules)

    def test_pending_rules_generate_review_word_with_exact_evidence(self):
        bundle = build_opening_interface_bundle(exact_facts(), rules=self.rules)
        data = result_payload(bundle, self.rules)
        self.assertEqual(data["counts"]["WARN"], 1)
        self.assertEqual(REPORT._overall_status(data)[0], "检查不完整 / 需要复核")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "check.json", root / "report.docx"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            REPORT.build_report(source, target)
            self.assertTrue(target.exists())
            document = Document(target)
            text = "\n".join(
                [paragraph.text for paragraph in document.paragraphs]
                + [cell.text for table in document.tables for row in table.rows for cell in row.cells])
        self.assertIn("接口精确几何证据", text)
        self.assertIn("局部壁厚=10.000 mm", text)
        self.assertIn("网格参与最终判定=否", text)
        self.assertIn("待批准，仅输出几何预判", text)

    def test_approved_rules_publish_formal_pass(self):
        rules = json.loads(json.dumps(self.rules))
        rules["routing"]["threshold_status"] = "APPROVED"
        rules["ruleset_id"] = "opening-approved-e2e"
        validate_rules(rules)
        bundle = build_opening_interface_bundle(exact_facts(), rules=rules)
        data = result_payload(bundle, rules)
        self.assertEqual(bundle["geometry_disposition_counts"]["PASS"], 1)
        self.assertEqual(data["counts"]["PASS"], 1)
        self.assertEqual(REPORT._overall_status(data)[0], "通过")

    def test_baseline_tracks_geometry_regression_under_pending_rules(self):
        before = result_payload(
            build_opening_interface_bundle(exact_facts(0.0), rules=self.rules), self.rules)
        after = result_payload(
            build_opening_interface_bundle(exact_facts(0.7), rules=self.rules), self.rules)
        before_id = before["findings"][0]["issue_id"]
        self.assertEqual(before_id, after["findings"][0]["issue_id"])
        comparison = compare_snapshots(create_snapshot(after), create_snapshot(before))
        self.assertEqual(comparison["regressions"], [before_id])
        self.assertEqual(comparison["summary"]["added"], 0)
        self.assertEqual(comparison["summary"]["resolved"], 0)


if __name__ == "__main__":
    unittest.main()
