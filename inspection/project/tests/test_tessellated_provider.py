import unittest

from catia_checker.tessellated_provider import evaluate_tessellated_plan


def mesh(vertices, triangles):
    return {"capabilities": ["TESSELLATED"], "mesh": {"vertices_mm": vertices, "triangles": triangles}}


class TessellatedProviderTests(unittest.TestCase):
    def test_solid_crossing_surface_returns_intersection_points(self):
        surface = mesh([(0, 0, 0), (2, 0, 0), (0, 2, 0)], [(0, 1, 2)])
        surface["geometry_kind"] = "SURFACE"
        solid_patch = mesh([(0.5, .5, -1), (.5, .5, 1), (1.5, .5, 0)], [(0, 1, 2)])
        solid_patch["geometry_kind"] = "SOLID"
        fact = evaluate_tessellated_plan({"method": "TESSELLATED_SURFACE_INTERSECTION",
                                         "object_a": "Pipe", "object_b": "Wall",
                                         "entity_a": solid_patch, "entity_b": surface})
        self.assertTrue(fact["intersects"])
        self.assertEqual(fact["mesh_closed"], [True, False])

    def test_open_surfaces_do_not_run_containment_test(self):
        first = mesh([(0, 0, 0), (2, 0, 0), (0, 2, 0)], [(0, 1, 2)]); first["geometry_kind"] = "SURFACE"
        second = mesh([(0, 0, 1), (2, 0, 1), (0, 2, 1)], [(0, 1, 2)]); second["geometry_kind"] = "SURFACE"
        fact = evaluate_tessellated_plan({"method": "TESSELLATED_SURFACE_INTERSECTION",
                                         "object_a": "A", "object_b": "B", "entity_a": first, "entity_b": second})
        self.assertFalse(fact["contained"])
        self.assertFalse(fact["intersects"])


if __name__ == "__main__":
    unittest.main()
