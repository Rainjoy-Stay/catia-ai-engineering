import unittest

from catia_checker.logical_components import (
    assemble_pipe_logical_components, recover_logical_components,
)


def shape(name, x):
    return {"shape_id": name, "face_count": 1,
            "bounds_mm": {"min": [x, 0, 0], "max": [x + 1, 1, 1]}}


class LogicalComponentTests(unittest.TestCase):
    def test_smooth_boundary_faces_form_one_patch(self):
        result = recover_logical_components(
            [shape("A", 0), shape("B", 1)],
            [{"object_a": "A", "object_b": "B", "boundary_contact": True,
              "continuous_surface_contact": True, "minimum_abs_normal_alignment": 1.0}])
        self.assertEqual(result["component_count"], 1)
        self.assertEqual(result["components"][0]["face_count"], 2)

    def test_plain_contact_does_not_merge_parts(self):
        result = recover_logical_components(
            [shape("PIPE", 0), shape("VESSEL", 1)],
            [{"object_a": "PIPE", "object_b": "VESSEL", "boundary_contact": True,
              "continuous_surface_contact": False}])
        self.assertEqual(result["component_count"], 2)
        self.assertEqual(result["unresolved_contact_count"], 1)

    def test_transitive_smooth_patch_is_supported(self):
        result = recover_logical_components(
            [shape("A", 0), shape("B", 1), shape("C", 2)],
            [{"object_a": "A", "object_b": "B", "boundary_contact": True,
              "continuous_surface_contact": True},
             {"object_a": "B", "object_b": "C", "boundary_contact": True,
              "continuous_surface_contact": True}])
        self.assertEqual(result["component_count"], 1)
        self.assertEqual(set(result["components"][0]["face_ids"]), {"A", "B", "C"})

    def test_cylinder_patch_is_tubular_candidate_without_guessing_role(self):
        cylinder = shape("CYL", 0)
        cylinder["surface_features"] = {"surface_type": "CYLINDER", "radius_mm": 25.4}
        result = recover_logical_components([cylinder], [])
        component = result["components"][0]
        self.assertEqual(component["engineering_object_type"], "TUBULAR_COMPONENT_CANDIDATE")
        self.assertEqual(component["candidate_roles"], ["PIPE", "NOZZLE", "VESSEL_SHELL"])

    def test_coaxial_equal_radius_patches_form_pipe_candidate(self):
        components = [
            {"logical_component_id": "C1", "engineering_object_type": "TUBULAR_COMPONENT_CANDIDATE",
             "representative_radius_mm": 25.0, "axis_origins_mm": [[0, 0, 0]],
             "axis_directions": [[1, 0, 0]]},
            {"logical_component_id": "C2", "engineering_object_type": "TUBULAR_COMPONENT_CANDIDATE",
             "representative_radius_mm": 25.1, "axis_origins_mm": [[10, 0, 0]],
             "axis_directions": [[1, 0, 0]]},
        ]
        logical = {"components": components, "face_to_component": {"F1": "C1", "F2": "C2"}}
        result = assemble_pipe_logical_components(logical, [
            {"object_a": "F1", "object_b": "F2", "boundary_contact": True}])
        self.assertEqual(result["pipe_candidate_count"], 1)
        self.assertEqual(result["pipe_candidates"][0]["component_count"], 2)

    def test_parallel_offset_tubes_do_not_merge(self):
        components = [
            {"logical_component_id": "C1", "engineering_object_type": "TUBULAR_COMPONENT_CANDIDATE",
             "representative_radius_mm": 25.0, "axis_origins_mm": [[0, 0, 0]],
             "axis_directions": [[1, 0, 0]]},
            {"logical_component_id": "C2", "engineering_object_type": "TUBULAR_COMPONENT_CANDIDATE",
             "representative_radius_mm": 25.0, "axis_origins_mm": [[0, 50, 0]],
             "axis_directions": [[1, 0, 0]]},
        ]
        logical = {"components": components, "face_to_component": {"F1": "C1", "F2": "C2"}}
        result = assemble_pipe_logical_components(logical, [
            {"object_a": "F1", "object_b": "F2", "boundary_contact": True}])
        self.assertEqual(result["pipe_candidate_count"], 2)
        self.assertEqual(result["joined_edge_count"], 0)

    def test_planar_transition_bridges_straight_and_bend(self):
        components = [
            {"logical_component_id": "STRAIGHT", "engineering_object_type": "TUBULAR_COMPONENT_CANDIDATE",
             "representative_radius_mm": 30.0, "axis_origins_mm": [[0, 0, 0]],
             "axis_directions": [[1, 0, 0]]},
            {"logical_component_id": "END", "engineering_object_type": "PLANAR_BOUNDARY_CANDIDATE"},
            {"logical_component_id": "BEND", "engineering_object_type": "PIPE_BEND_CANDIDATE",
             "representative_radius_mm": 30.1},
        ]
        logical = {"components": components,
                   "face_to_component": {"FS": "STRAIGHT", "FE": "END", "FB": "BEND"}}
        result = assemble_pipe_logical_components(logical, [
            {"object_a": "FS", "object_b": "FE", "boundary_contact": True},
            {"object_a": "FE", "object_b": "FB", "boundary_contact": True},
        ])
        joined = [item for item in result["pipe_candidates"] if item["component_count"] == 3]
        self.assertEqual(len(joined), 1)
        self.assertTrue(joined[0]["has_bend"])

    def test_torus_patch_is_pipe_bend_candidate(self):
        torus = shape("TORUS", 0)
        torus["surface_features"] = {"surface_type": "TORUS",
                                     "major_radius_mm": 100, "minor_radius_mm": 20}
        result = recover_logical_components([torus], [])
        self.assertEqual(result["components"][0]["engineering_object_type"],
                         "PIPE_BEND_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
