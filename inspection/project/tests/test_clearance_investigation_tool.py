import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_tool import CheckTool


class FakeMeasurement:
    def __init__(self):
        self.calls = 0

    def execute(self, name, args):
        self.calls += 1
        return json.dumps({
            "document": "sample.CATProduct", "root_product": "sample",
            "method": "CATIA_DMU_TEST", "clearance_mm": 10.0,
            "conflicts": [{"type": "CONTACT", "value_mm": 0.0,
                "first_product": "PipeA", "second_product": "ValveB"}],
            "truncated": False, "cleanup_verified": True,
            "source_saved_by_tool": False, "direct_transient_step_fallback": True,
        })


class ClearanceInvestigationToolTests(unittest.TestCase):
    def test_main_mcp_tool_exposes_opening_interface_input(self):
        definitions = CheckTool(FakeMeasurement(), object()).get_tool_definitions()
        main = next(item for item in definitions if item["name"] == "catia_check_assembly")
        self.assertIn("opening_interface_facts", main["inputSchema"]["properties"])

    def test_prepare_then_finalize_reuses_scan_and_accepts_agent_evidence(self):
        measurement = FakeMeasurement()
        tool = CheckTool(measurement, object())
        prepared = json.loads(tool.execute("catia_prepare_clearance_investigation", {
            "model_type": "STEP"}))
        pair = prepared["pair_contexts"][0]["pair_id"]
        with tempfile.TemporaryDirectory() as folder, patch.object(
                Path, "mkdir"), patch.object(Path, "write_text"):
            result = json.loads(tool.execute("catia_finalize_clearance_investigation", {
                "investigation_id": prepared["investigation_id"],
                "assessments": [{
                    "pair_id": pair, "decision": "PASS_NORMAL_CONNECTION",
                    "confidence": 0.96, "reason": "端面和接口证据一致",
                    "key_evidence": ["端面同心", "接口法向相对"],
                    "relation_type": "PIPE_TO_VALVE",
                    "evidence_trace": [{"tool": "catia_get_model_manifest"}],
                    "unresolved_questions": [],
                }],
            }))
        self.assertEqual(measurement.calls, 1)
        self.assertEqual(result["findings"][0]["status"], "PASS")
        relation = result["findings"][0]["metadata"]["relationship_assessment"]
        self.assertEqual(relation["decision"], "PASS_NORMAL_CONNECTION")
        self.assertTrue(relation["evidence_trace"])


if __name__ == "__main__":
    unittest.main()
