import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools" / "rescue_body_solid_mapping.py"
SPEC = importlib.util.spec_from_file_location("rescue_body_solid_mapping", PATH)
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)


class BodySolidRescueTests(unittest.TestCase):
    def test_plan_only_probes_unmapped_bodies(self):
        probe = {"source": {"source_body_count_before": 3},
                 "large_single_part_analysis": {"batch_plan": {"shapes": [
                     {"shape_id": "A"}, {"shape_id": "B"}]}}}
        replay = {"result": {"matches": [{"source_id": "A", "target_id": "2"}]}}
        plan = MODULE.build_rescue_plan(probe, replay)
        self.assertEqual([1, 3], plan["body_indices"])
        self.assertEqual(["B"], [x["shape_id"] for x in plan["unresolved_shapes"]])

    def test_single_body_probe_maps_permuted_solids(self):
        feature = lambda identity, volume: {
            "shape_id": identity, "volume_mm3": volume,
            "surface_area_mm2": volume * 2, "centroid_mm": [volume, 0, 0]}
        manifests = [
            {"root_shape_id": "R1", "shapes": [{"shape_id": "R1"}, feature("P1", 20)]},
            {"root_shape_id": "R2", "shapes": [{"shape_id": "R2"}, feature("P2", 10)]},
        ]
        result = MODULE.resolve_probe_manifests(
            [feature("ORIGINAL-A", 10), feature("ORIGINAL-B", 20)], manifests, [7, 9])
        self.assertEqual({x["shape_id"]: x["source_body_index"] for x in result["assignments"]},
                         {"ORIGINAL-A": 9, "ORIGINAL-B": 7})
        self.assertFalse(result["sequence_fallback_used"])


if __name__ == "__main__": unittest.main()
