import json
import unittest

from catia_checker.models import (
    CheckFinding,
    CheckStatus,
    ConfidenceBudget,
    Evidence,
    EvidenceKind,
    Severity,
    build_llm_payload,
)


class ResultModelTests(unittest.TestCase):
    def _finding(self) -> CheckFinding:
        return CheckFinding(
            issue_id="FAIL-01",
            rule_id="DMU.HARD_CLASH",
            status=CheckStatus.FAIL,
            severity=Severity.S4,
            title="启动空气管与内部结构干涉",
            message="CATIA DMU 检测到实体穿透。",
            object_a="Product4/Tube.1",
            object_b="Product4/Structure.1",
            measured_value=-15.514,
            limit_value=0.0,
            unit="mm",
            location_xyz_mm=(10.0, 20.0, 30.0),
            evidence=(Evidence(
                kind=EvidenceKind.CATIA_CLASH,
                source="CATIA DMU Between All",
                object_paths=("Product4/Tube.1", "Product4/Structure.1"),
                data={"clash_type": "CLASH", "value_mm": -15.514},
            ),),
        )

    def test_finding_json_round_trip(self) -> None:
        finding = self._finding()
        encoded = json.dumps(finding.to_dict(), ensure_ascii=False)
        restored = CheckFinding.from_dict(json.loads(encoded))
        self.assertEqual(restored, finding)
        self.assertEqual(restored.status, CheckStatus.FAIL)
        self.assertEqual(restored.evidence[0].kind, EvidenceKind.CATIA_CLASH)

    def test_measurement_requires_unit(self) -> None:
        with self.assertRaisesRegex(ValueError, "unit is required"):
            CheckFinding(
                issue_id="X-1",
                rule_id="X",
                status=CheckStatus.WARN,
                severity=Severity.S2,
                title="测量缺单位",
                message="无效输入",
                measured_value=1.0,
            )

    def test_confidence_budget_exposes_incomplete_scope(self) -> None:
        budget = ConfidenceBudget(
            checked=("DMU 全装配干涉",),
            not_checked=("运动包络",),
            assumptions=("试运行阈值尚未批准",),
        )
        self.assertFalse(budget.is_complete)
        self.assertEqual(budget.to_dict()["not_checked"], ["运动包络"])

    def test_build_llm_payload_counts_rule_statuses(self) -> None:
        payload = build_llm_payload(
            "Product4.CATProduct",
            [self._finding()],
            ConfidenceBudget(checked=("DMU 全装配干涉",)),
        )
        self.assertEqual(payload["counts"]["FAIL"], 1)
        self.assertEqual(payload["counts"]["WARN"], 0)
        self.assertEqual(payload["findings"][0]["measured_value"], -15.514)
        self.assertTrue(payload["confidence_budget"]["is_complete"])


if __name__ == "__main__":
    unittest.main()
