from pathlib import Path
import tempfile
import unittest

from catia_checker.permitted_volume import AxialSection, build_axisymmetric_permitted_volume


class PermittedVolumeTests(unittest.TestCase):
    def test_builds_closed_valid_volume_and_mesh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = build_axisymmetric_permitted_volume((
                AxialSection(0.0, 10.0, 5.0, 5.0),
                AxialSection(10.0, 20.0, 5.0, 8.0),
            ), root / "cavity.stp", root / "cavity.json", angular_segments=24)
            self.assertTrue(result["closed"])
            self.assertTrue(result["valid_brep"])
            self.assertGreater(result["volume_mm3"], 0.0)
            self.assertTrue((root / "cavity.stp").is_file())
            self.assertTrue((root / "cavity.json").is_file())


if __name__ == "__main__":
    unittest.main()
