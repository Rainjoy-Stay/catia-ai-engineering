import json
from pathlib import Path
import tempfile
import unittest

from catia_checker.llm_adapter import TemplateAdapter, create_llm_adapter, load_runtime_config
from catia_checker.models import (
    CheckFinding,
    CheckStatus,
    ConfidenceBudget,
    Severity,
    build_llm_payload,
)


class LLMAdapterTests(unittest.TestCase):
    def test_template_preserves_structured_values(self) -> None:
        payload = {
            "document": "Product1.CATProduct",
            "counts": {"CLASH": 1, "CONTACT": 0, "CLEARANCE": 0, "EXEMPTED": 0},
            "conflicts": [{
                "type": "CLASH",
                "first_product": "Part1.1",
                "second_product": "Part2.1",
                "value_mm": -12.5,
                "rule_status": "UNFILTERED",
            }],
        }
        response = TemplateAdapter().explain(payload)
        self.assertTrue(response.degraded)
        self.assertIn("-12.5 mm", response.text)
        self.assertIn("Part1.1 / Part2.1", response.text)

    def test_runtime_config_factory(self) -> None:
        config = {"schema_version": "1.1.0", "llm": {"mode": "template"}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_runtime_config(path)
        self.assertIsInstance(create_llm_adapter(loaded), TemplateAdapter)

    def test_template_accepts_unified_findings(self) -> None:
        finding = CheckFinding(
            issue_id="WARN-01",
            rule_id="CLEARANCE.PIPE_STATIC",
            status=CheckStatus.WARN,
            severity=Severity.S2,
            title="管路间距需要复核",
            message="实测间距接近暂定限值。",
            object_a="Tube.1",
            object_b="Frame.1",
            measured_value=8.5,
            limit_value=12.0,
            unit="mm",
        )
        payload = build_llm_payload(
            "Product1.CATProduct",
            [finding],
            ConfidenceBudget(
                checked=("静态间距",),
                not_checked=("运动包络",),
            ),
        )
        response = TemplateAdapter().explain(payload)
        self.assertIn("WARN-01 [WARN/S2]", response.text)
        self.assertIn("8.5 mm", response.text)
        self.assertIn("未检查=1", response.text)

    def test_template_never_invents_engineering_semantics(self) -> None:
        result = TemplateAdapter().judge_engineering_semantics(
            [{"object_id": "x", "facts": {"plane_face_ratio": 1.0}}], "object")
        self.assertEqual(result[0]["classification"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
