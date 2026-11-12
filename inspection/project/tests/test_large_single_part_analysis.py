import unittest
from pathlib import Path
import tempfile

from standalone.large_single_part_analysis import (
    analyze_large_single_part, build_spatial_candidates, inspect_via_temporary_step,
)


class FakeBackend:
    def __init__(self, facts): self.facts = facts; self.common_calls = 0
    def distance(self, a, b):
        return {"minimum_distance_mm": self.facts[tuple(sorted((a, b)))][0],
                "exact_brep": True}
    def common_volume(self, a, b):
        self.common_calls += 1
        return {"intersection_volume_mm3": self.facts[tuple(sorted((a, b)))][1],
                "exact_brep": True}


def shape(name, minimum, maximum, solid=1, valid=True):
    return {"shape_id": name, "bounds_mm": {"min": minimum, "max": maximum},
            "solid_count": solid, "valid": valid}


class LargeSinglePartAnalysisTests(unittest.TestCase):
    def test_broad_phase_avoids_remote_pairs(self):
        result = build_spatial_candidates([
            shape("A", [0, 0, 0], [2, 2, 2]),
            shape("B", [1, 1, 1], [3, 3, 3]),
            shape("FAR", [100, 0, 0], [101, 1, 1])])
        self.assertEqual(result["total_possible_pairs"], 3)
        self.assertEqual(result["pairs"], [["A", "B"]])
        self.assertFalse(result["mesh_used"])

    def test_positive_common_volume_is_interference(self):
        manifest = {"root_shape_id": "ROOT", "shapes": [
            shape("ROOT", [0, 0, 0], [3, 3, 3]),
            shape("A", [0, 0, 0], [2, 2, 2]), shape("B", [1, 0, 0], [3, 2, 2])]}
        result = analyze_large_single_part(FakeBackend({("A", "B"): (0, 4)}), manifest)
        self.assertEqual(result["disposition_counts"]["FAIL"], 1)
        self.assertEqual(result["findings"][0]["code"], "INTERNAL_SOLID_INTERFERENCE")

    def test_zero_volume_zero_distance_is_contact_review(self):
        manifest = {"shapes": [shape("A", [0, 0, 0], [1, 1, 1]),
                               shape("B", [1, 0, 0], [2, 1, 1])]}
        result = analyze_large_single_part(FakeBackend({("A", "B"): (0, 0)}), manifest)
        self.assertEqual(result["disposition_counts"]["REVIEW"], 1)

    def test_positive_gap_skips_common_volume(self):
        manifest = {"shapes": [shape("A", [0, 0, 0], [2, 2, 2]),
                               shape("B", [1, 1, 1], [3, 3, 3])]}
        backend = FakeBackend({("A", "B"): (0.25, 99)})
        result = analyze_large_single_part(backend, manifest)
        self.assertEqual(backend.common_calls, 0)
        self.assertEqual(result["findings"][0]["intersection_volume_mm3"], 0.0)
        self.assertFalse(result["findings"][0]["common_volume_evidence"]["boolean_computed"])

    def test_open_shell_is_not_sent_to_solid_common_volume(self):
        manifest = {"shapes": [shape("SHELL", [0, 0, 0], [1, 1, 1], solid=0)]}
        result = analyze_large_single_part(FakeBackend({}), manifest)
        self.assertEqual(result["exact_pair_count"], 0)
        self.assertEqual(result["health_findings"][0]["code"], "OPEN_SHELL_OR_SURFACE")

    def test_pair_limit_fails_coverage_closed(self):
        shapes = [shape(name, [0, 0, 0], [2, 2, 2]) for name in ("A", "B", "C")]
        result = analyze_large_single_part(FakeBackend({("A", "B"): (0, 0)}),
                                           {"shapes": shapes}, max_exact_pairs=1)
        self.assertTrue(result["truncated"])
        self.assertFalse(result["coverage_complete"])

    def test_temporary_export_is_deleted_after_inspection(self):
        observed = {}
        def exporter(path):
            path.write_bytes(b"ISO-10303-21;")
            observed["path"] = path
        def inspector(path):
            self.assertTrue(path.exists())
            return {"analysis": {}}
        result = inspect_via_temporary_step(exporter, inspector)
        self.assertFalse(Path(observed["path"]).exists())
        self.assertTrue(result["temporary_export_audit"]["temporary_file_deleted"])

    def test_temporary_export_failure_also_cleans_directory(self):
        observed = {}
        def exporter(path):
            path.write_bytes(b"bad"); observed["path"] = path
        with self.assertRaisesRegex(RuntimeError, "inspection failed"):
            inspect_via_temporary_step(exporter,
                                       lambda path: (_ for _ in ()).throw(RuntimeError("inspection failed")))
        self.assertFalse(Path(observed["path"]).exists())


if __name__ == "__main__":
    unittest.main()
