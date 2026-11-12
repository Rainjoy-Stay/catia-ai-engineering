import unittest

from catia_checker.mesh_instances import instantiate_part_mesh


class MeshInstanceTests(unittest.TestCase):
    def test_instance_mesh_and_bounds_are_world_transformed(self):
        tessellation = {"document": "Sleeve.CATPart", "mesh": {"vertices_mm": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                       "triangles": [[0, 1, 2]], "bounds_mm": [0, 0, 0, 1, 1, 0]}}
        instances = [{"instance_id": "Sleeve.2", "part_number": "SLEEVE",
                      "world_transform": {"matrix": [1, 0, 0, 10, 0, 1, 0, 2, 0, 0, 1, 0, 0, 0, 0, 1]}}]
        result = instantiate_part_mesh(tessellation, instances)[0]
        self.assertEqual(result["mesh"]["vertices_mm"][1], [11.0, 2.0, 0.0])
        self.assertEqual(result["bounds_mm"], [10.0, 2.0, 0.0, 11.0, 3.0, 0.0])
        self.assertEqual(result["coordinate_space"], "WORLD")
