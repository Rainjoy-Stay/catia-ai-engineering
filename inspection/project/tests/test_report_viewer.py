import json
import tempfile
import unittest
from pathlib import Path

from catia_checker.report_viewer import actionable_findings, find_default_report, finding_row


class ReportViewerTests(unittest.TestCase):
    def test_orders_failures_first_and_formats_objects(self):
        report = {"findings": [
            {"issue_id": "P", "status": "PASS"},
            {"issue_id": "F", "status": "FAIL", "object_a": "A", "object_b": "B",
             "measured_value": 1.25, "unit": "mm3"},
        ]}
        values = actionable_findings(report)
        self.assertEqual([x["issue_id"] for x in values], ["F", "P"])
        self.assertEqual(finding_row(values[0])[4:], ("A ↔ B", "1.25 mm3"))

    def test_uses_last_run_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = root / "result.json"
            result.write_text("{}", encoding="utf-8")
            (root / "validation").mkdir()
            (root / "validation" / "last-run.json").write_text(
                json.dumps({"result": str(result)}), encoding="utf-8"
            )
            self.assertEqual(find_default_report(root), result.resolve())


if __name__ == "__main__":
    unittest.main()
