import unittest

from catia_checker.route_interfaces import resolve_unique_route_port


class RouteInterfaceTests(unittest.TestCase):
    def test_resolves_unique_interface_and_derives_diameter(self):
        result = resolve_unique_route_port(
            "P1", "equipment", (0,0,0), (1,0,0),
            [{"interface_id":"I1", "center_mm":[0.1,0,0],
              "normal":[-1,0,0], "radius_mm":3}],
        )
        self.assertEqual(result.source_interface_id, "I1")
        self.assertEqual(result.diameter_candidates_mm, (6.0,))
        self.assertGreater(result.normal[0], 0)

    def test_rejects_ambiguous_interface(self):
        candidates = [
            {"interface_id":name, "center_mm":[0,0,0], "normal":[1,0,0], "radius_mm":2}
            for name in ("A", "B")]
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            resolve_unique_route_port("P", "host", (0,0,0), (1,0,0), candidates)


if __name__ == "__main__":
    unittest.main()
