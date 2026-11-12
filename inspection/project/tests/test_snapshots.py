import json
from pathlib import Path
import tempfile
import unittest

from catia_checker.snapshots import (
    compare_snapshots, create_snapshot, load_snapshot, write_snapshot,
)


def result(findings):
    return {
        "document": "Product1.CATProduct",
        "ruleset_id": "rules-v1",
        "source": {
            "method": "BETWEEN_ALL_NATIVE",
            "computation_type": "BETWEEN_ALL",
            "clearance_mm": 0.1,
            "scope_component_count": 10,
            "accuracy_note": "volatile prose excluded",
        },
        "findings": findings,
        "generated_at": "ignored",
    }


def finding(issue_id, status="WARN", measured=1.0):
    return {
        "issue_id": issue_id, "rule_id": "DMU.CLEARANCE",
        "status": status, "severity": "S2",
        "object_a": "B.1", "object_b": "A.1",
        "measured_value": measured, "limit_value": 2.0, "unit": "mm",
        "message": "volatile report prose",
    }


def opening_finding(issue_id, geometry_disposition, offset):
    value = finding(issue_id, status="WARN", measured=0.2)
    value["rule_id"] = "GEOMETRY.OPENING_INTERFACE"
    value["metadata"] = {
        "geometry_disposition": geometry_disposition,
        "opening_interface": {"opening_id": "OPEN-1", "nozzle_id": "NOZZLE-1",
                              "measurements": {"axis_offset_mm": offset},
                              "reason_labels": []},
    }
    return value


class SnapshotTests(unittest.TestCase):
    def test_snapshot_keeps_only_stable_fields(self) -> None:
        snapshot = create_snapshot(result([finding("I-1")]))
        self.assertNotIn("generated_at", snapshot)
        self.assertNotIn("message", snapshot["findings"]["I-1"])
        self.assertEqual(snapshot["findings"]["I-1"]["objects"], ["A.1", "B.1"])

    def test_compare_classifies_added_resolved_and_persistent(self) -> None:
        baseline = create_snapshot(result([finding("OLD"), finding("SAME")]))
        current = create_snapshot(result([finding("SAME"), finding("NEW", "FAIL")]))
        comparison = compare_snapshots(current, baseline)
        self.assertEqual(comparison["added"], ["NEW"])
        self.assertEqual(comparison["resolved"], ["OLD"])
        self.assertEqual(comparison["persistent"], ["SAME"])
        self.assertEqual(comparison["regressions"], ["NEW"])

    def test_status_change_is_regression_or_improvement(self) -> None:
        baseline = create_snapshot(result([finding("WORSE", "WARN"), finding("BETTER", "FAIL")]))
        current = create_snapshot(result([finding("WORSE", "FAIL"), finding("BETTER", "WARN")]))
        comparison = compare_snapshots(current, baseline)
        self.assertEqual(comparison["regressions"], ["WORSE"])
        self.assertEqual(comparison["improvements"], ["BETTER"])
        self.assertEqual(comparison["summary"]["changed"], 2)

    def test_measurement_tolerance_avoids_numeric_noise(self) -> None:
        baseline = create_snapshot(result([finding("I-1", measured=1.0)]))
        current = create_snapshot(result([finding("I-1", measured=1.00001)]))
        comparison = compare_snapshots(current, baseline, measurement_tolerance=0.001)
        self.assertEqual(comparison["persistent"], ["I-1"])

    def test_snapshot_file_round_trip(self) -> None:
        snapshot = create_snapshot(result([finding("I-1")]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            write_snapshot(snapshot, path)
            loaded = load_snapshot(path)
        self.assertEqual(loaded, json.loads(json.dumps(snapshot)))

    def test_duplicate_issue_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate issue_id"):
            create_snapshot(result([finding("I-1"), finding("I-1")]))

    def test_unapproved_warning_still_tracks_geometry_regression(self) -> None:
        baseline = create_snapshot(result([opening_finding("OPENING-1", "PASS", 0.2)]))
        current = create_snapshot(result([opening_finding("OPENING-1", "FAIL", 0.8)]))
        comparison = compare_snapshots(current, baseline)
        self.assertEqual(comparison["regressions"], ["OPENING-1"])
        self.assertIn("opening_interface", comparison["changed"][0]["changes"])

    def test_opening_measurement_tolerance_avoids_numeric_noise(self) -> None:
        baseline = create_snapshot(result([opening_finding("OPENING-1", "PASS", 0.2)]))
        current = create_snapshot(result([opening_finding("OPENING-1", "PASS", 0.20001)]))
        comparison = compare_snapshots(current, baseline, measurement_tolerance=0.001)
        self.assertEqual(comparison["persistent"], ["OPENING-1"])


if __name__ == "__main__":
    unittest.main()
