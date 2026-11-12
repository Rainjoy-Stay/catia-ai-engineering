import unittest

from catia_checker.geometry_candidates import build_geometry_candidates
from catia_checker.geometry_coordinates import normalize_entity_world_bounds, transform_bounds_to_world


class GeometryCoordinateTests(unittest.TestCase):
    def test_rotated_bounds_uses_all_eight_corners(self):
        # 90 degree Z rotation then +10 mm X translation.
        matrix = [0, -1, 0, 10, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        self.assertEqual(transform_bounds_to_world([0, 0, 0, 2, 1, 3], matrix), [9, 0, 0, 10, 2, 3])

    def test_local_bounds_without_transform_stay_unavailable(self):
        result = normalize_entity_world_bounds({"reference_bounds_mm": [0, 0, 0, 1, 1, 1],
                                                "reference_bounds_coordinate_space": "LOCAL"})
        self.assertEqual(result["world_bounds_reason"], "NO_WORLD_TRANSFORM")

    def test_transformed_step_entity_enters_candidate_queue(self):
        local = {"object_id": "Surface", "geometry_kind": "SURFACE", "geometry_state": "AVAILABLE",
                 "reference_bounds_mm": [0, 0, 0, 1, 1, 1],
                 "reference_bounds_coordinate_space": "LOCAL_STEP_REPRESENTATION",
                 "assembly_transform": {"matrix": [1, 0, 0, 5, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}}
        solid = {"object_id": "Solid", "geometry_kind": "SOLID", "geometry_state": "AVAILABLE",
                 "coordinate_space": "WORLD", "bounds_mm": [5.5, 0, 0, 6, 1, 1]}
        result = build_geometry_candidates([local, solid], search_margin_mm=0)
        self.assertEqual(result["candidate_pair_count"], 1)


if __name__ == "__main__":
    unittest.main()
