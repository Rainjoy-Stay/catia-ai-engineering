import json
from pathlib import Path
import tempfile
import unittest

from catia_checker.release_baseline import validate_baseline


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "release_baseline_v4_5.json"


class ReleaseBaselineTests(unittest.TestCase):
    def test_repository_baseline_is_consistent(self):
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        result = validate_baseline(data, ROOT.parent)
        self.assertEqual("PASS", result["status"], result["errors"])
        self.assertEqual("PARTIAL", result["release_status"])

    def test_unresolved_live_chain_is_rejected(self):
        data = {"product_version": "4.5.0-dev", "release_status": "PARTIAL",
                "inspection_chains": [{"id": "x", "verification_level": "LIVE_VERIFIED",
                                       "not_evaluated_count": 1, "evidence": ["x"]}],
                "delivery_files": []}
        result = validate_baseline(data, Path(tempfile.gettempdir()))
        self.assertEqual("FAIL", result["status"])

    def test_pass_cannot_hide_not_implemented_chain(self):
        data = {"product_version": "4.5.0-dev", "release_status": "PASS",
                "inspection_chains": [{"id": "x", "verification_level": "NOT_IMPLEMENTED",
                                       "not_evaluated_count": 1, "evidence": []}],
                "delivery_files": []}
        result = validate_baseline(data, Path(tempfile.gettempdir()))
        self.assertEqual("FAIL", result["status"])


if __name__ == "__main__":
    unittest.main()
