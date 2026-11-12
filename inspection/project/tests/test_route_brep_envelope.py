import tempfile
import unittest
from pathlib import Path

from catia_checker.occt_brep import OCCTBRepModel
from catia_checker.route_brep_envelope import build_route_envelope_step


class RouteBRepEnvelopeTests(unittest.TestCase):
    def test_builds_valid_non_orthogonal_swept_solid(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "route.stp"
            result = build_route_envelope_step(
                [(0,0,0),(30,0,0),(50,20,10)], [8], 4, target)
            self.assertTrue(result["valid_brep"])
            manifest = OCCTBRepModel().load_step(target, lightweight=True)
            solids = [item for item in manifest["shapes"] if item["shape_id"] != "STEP_ROOT"]
            self.assertEqual(len(solids), 1)
            self.assertEqual(solids[0]["solid_count"], 1)
            self.assertGreater(solids[0]["volume_mm3"], 0)

    def test_builds_exact_endpoint_reducers(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "reduced.stp"
            result = build_route_envelope_step(
                [(0,0,0),(80,0,0)], [], 4, target,
                start_interface_diameter_mm=8, goal_interface_diameter_mm=6,
                start_reducer_length_mm=20, goal_reducer_length_mm=10,
            )
            self.assertEqual(result["reducer_count"], 2)
            solids = [item for item in OCCTBRepModel().load_step(target, lightweight=True)["shapes"]
                      if item["shape_id"] != "STEP_ROOT"]
            self.assertEqual(len(solids), 1)
            self.assertGreater(solids[0]["volume_mm3"], 0)

    def test_rejects_reducer_with_excessive_half_angle(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "half-angle"):
                build_route_envelope_step(
                    [(0,0,0),(80,0,0)], [], 4, Path(folder)/"bad.stp",
                    start_interface_diameter_mm=20, start_reducer_length_mm=2,
                )


if __name__ == "__main__":
    unittest.main()
