import unittest

from catia_checker.model_understanding.pipeline import normalize_standalone_coordinate_space


class StandaloneCoordinateTests(unittest.TestCase):
    def test_single_root_gets_explicit_identity_world_transform(self):
        model = {"bodies": [{"reference_bounds_coordinate_space": "LOCAL_STEP_REPRESENTATION"}]}
        self.assertTrue(normalize_standalone_coordinate_space(model))
        body = model["bodies"][0]
        self.assertEqual(body["reference_bounds_coordinate_space"], "WORLD")
        self.assertEqual(body["assembly_transform"]["assumption"], "STANDALONE_ROOT_IDENTITY")

    def test_multiple_unplaced_bodies_are_not_assumed_coincident(self):
        model = {"bodies": [{}, {}]}
        self.assertFalse(normalize_standalone_coordinate_space(model))
        self.assertNotIn("assembly_transform", model["bodies"][0])


if __name__ == "__main__":
    unittest.main()
