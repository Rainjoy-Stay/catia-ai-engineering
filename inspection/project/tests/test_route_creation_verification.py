import unittest

from catia_checker.route_creation_verification import verify_created_route


class RouteCreationVerificationTests(unittest.TestCase):
    def test_exact_native_readback_passes(self):
        inspection = {
            "SectionDiameter": 4.0,
            "nodes": [
                {"point":[0,0,0], "bend_radius":0},
                {"point":[20,0,0], "bend_radius":8},
                {"point":[20,20,0], "bend_radius":0},
            ],
        }
        result = verify_created_route(
            inspection, [(0,0,0),(20,0,0),(20,20,0)], [8], 4)
        self.assertEqual(result["status"], "PASS")

    def test_any_geometry_mismatch_fails(self):
        inspection = {
            "SectionDiameter": 5,
            "nodes": [
                {"point":[0,0,0]},
                {"point":[20.5,0,0], "bend_radius":7},
                {"point":[20,20,0]},
            ],
        }
        result = verify_created_route(
            inspection, [(0,0,0),(20,0,0),(20,20,0)], [8], 4)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("SECTION_DIAMETER_MISMATCH", result["issues"])
        self.assertTrue(any(item.startswith("NODE_POINT_MISMATCH") for item in result["issues"]))
        self.assertTrue(any(item.startswith("BEND_RADIUS_MISMATCH") for item in result["issues"]))


if __name__ == "__main__":
    unittest.main()
