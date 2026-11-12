import importlib.util
from pathlib import Path
import tempfile
import unittest
from PIL import Image


PATH = Path(__file__).resolve().parents[2] / "scripts" / "capture_finding_evidence.py"
SPEC = importlib.util.spec_from_file_location("capture_finding_evidence", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CaptureFindingEvidenceTests(unittest.TestCase):
    def test_review_state_is_captured_but_pass_is_not(self):
        self.assertTrue(MODULE.is_screenshot_candidate({"status": "NOT_EVALUATED"}))
        self.assertTrue(MODULE.is_screenshot_candidate({"status": "FAIL"}))
        self.assertFalse(MODULE.is_screenshot_candidate({"status": "PASS"}))

    def test_offline_manifest_exposes_solid_records(self):
        payload = {"large_single_part_analysis": {"manifest": {
            "root_shape_id": "ROOT", "shapes": [
                {"shape_id": "ROOT"}, {"shape_id": "S1"}, {"shape_id": "S2"}]}}}
        finding = {"issue_id": "I1", "metadata": {
            "geometry_object_a": "S1", "geometry_object_b": "S2"}}
        self.assertEqual(["S1", "S2"], MODULE.offline_shape_ids(payload))
        self.assertEqual(["S1", "S2"], [item["shape_id"] for item in MODULE.offline_solid_records(payload)])
        self.assertEqual(["S1", "S2"], MODULE.offline_finding_shape_ids(finding))

    def test_geometry_mapping_ignores_body_order(self):
        solids = [
            {"shape_id": "S1", "volume_mm3": 10, "surface_area_mm2": 20, "centroid_mm": [1, 0, 0]},
            {"shape_id": "S2", "volume_mm3": 30, "surface_area_mm2": 40, "centroid_mm": [2, 0, 0]},
        ]
        bodies = [
            {"body_index": 1, "volume_mm3": 30, "surface_area_mm2": 40, "centroid_mm": [2, 0, 0]},
            {"body_index": 2, "volume_mm3": 10, "surface_area_mm2": 20, "centroid_mm": [1, 0, 0]},
        ]
        mapping, audit = MODULE.build_offline_body_mapping(
            solids, bodies, {"1": "BODY-1", "2": "BODY-2"})
        self.assertEqual({"S1": "BODY-2", "S2": "BODY-1"}, mapping)
        self.assertTrue(audit["is_complete"])
        self.assertFalse(audit["sequence_fallback_used"])

    def test_repeated_geometry_is_not_mapped_by_order(self):
        solids = [{"shape_id": value, "volume_mm3": 10, "surface_area_mm2": 20,
                   "centroid_mm": [0, 0, 0]} for value in ("S1", "S2")]
        bodies = [{"body_index": value, "volume_mm3": 10, "surface_area_mm2": 20,
                   "centroid_mm": [0, 0, 0]} for value in (1, 2)]
        mapping, audit = MODULE.build_offline_body_mapping(
            solids, bodies, {"1": "BODY-1", "2": "BODY-2"})
        self.assertEqual({}, mapping)
        self.assertFalse(audit["is_complete"])
        self.assertTrue(all(item["reason"] == "AMBIGUOUS_REPEATED_GEOMETRY"
                            for item in audit["unresolved"]))

    def test_insufficient_features_are_rejected(self):
        mapping, audit = MODULE.build_offline_body_mapping(
            [{"shape_id": "S1", "volume_mm3": 10}],
            [{"body_index": 1, "volume_mm3": 10}], {"1": "BODY-1"})
        self.assertEqual({}, mapping)
        self.assertEqual("INSUFFICIENT_GEOMETRY_FEATURES", audit["unresolved"][0]["reason"])
        self.assertFalse(audit["sequence_fallback_used"])

    def test_offline_mapping_rejects_missing_shape_ids(self):
        with self.assertRaises(ValueError):
            MODULE.offline_finding_shape_ids({"metadata": {}})

    def test_brightness_delta_fallback_locates_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            before = Image.new("RGB", (400, 200), (30, 30, 30))
            selected = before.copy()
            for x in range(150, 210):
                for y in range(70, 130):
                    selected.putpixel((x, y), (55, 55, 55))
            a, b = Path(directory) / "a.png", Path(directory) / "b.png"
            before.save(a); selected.save(b)
            box = MODULE.highlight_bounds(a, b)
            self.assertIsNotNone(box)
            self.assertLessEqual(box[0], 150); self.assertGreaterEqual(box[2], 208)


if __name__ == "__main__":
    unittest.main()
