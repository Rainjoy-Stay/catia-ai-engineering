import unittest

from catia_checker.route_manufacturability import optimize_bend_radii, validate_polyline_route


class RouteManufacturabilityTests(unittest.TestCase):
    def test_rejects_adjacent_r10_bends_on_ten_mm_segment(self):
        result = validate_polyline_route([(0,0,0),(20,0,0),(20,10,0),(40,10,0)], [10])
        self.assertFalse(result.ok)
        self.assertTrue(any(e.startswith("INSUFFICIENT_TANGENT_LENGTH:1") for e in result.errors))


    def test_accepts_bends_with_enough_tangent_length(self):
        result = validate_polyline_route([(0,0,0),(20,0,0),(20,25,0),(40,25,0)], [10])
        self.assertTrue(result.ok)


    def test_rejects_centerline_self_intersection(self):
        result = validate_polyline_route([(0,0,0),(10,10,0),(0,10,0),(10,0,0),(20,0,0)], [1])
        self.assertFalse(result.ok)
        self.assertTrue(any(e.startswith("CENTERLINE_SELF_INTERSECTION") for e in result.errors))


    def test_builds_non_orthogonal_bend_geometry(self):
        result = validate_polyline_route([(0,0,0),(20,0,0),(40,20,10)], [10])
        self.assertTrue(result.ok)
        bend = result.bends[0]
        self.assertTrue(0 < bend.angle_deg < 90)
        self.assertAlmostEqual(sum(value * value for value in bend.axis), 1.0)
        self.assertAlmostEqual(bend.radius_mm, 10.0)
        for tangent in (bend.tangent_start, bend.tangent_end):
            self.assertAlmostEqual(sum((tangent[i]-bend.center[i])**2 for i in range(3)), 100.0)

    def test_optimizes_each_bend_radius_under_coupled_tangent_limits(self):
        result = optimize_bend_radii(
            [(0,0,0),(30,0,0),(30,15,0),(60,15,0)],
            [5, 10, 15], preferred_radii_mm=[10],
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.radii_mm, (10, 5))


if __name__ == "__main__":
    unittest.main()
