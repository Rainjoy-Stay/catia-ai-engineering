import unittest

from catia_checker.engineering_roles import classify_tubular_roles


def tube(component_id, radius, bounds, direction=(1, 0, 0), kind="TUBULAR_COMPONENT_CANDIDATE"):
    return {"logical_component_id": component_id, "engineering_object_type": kind,
            "representative_radius_mm": radius,
            "bounds_mm": {"min": bounds[:3], "max": bounds[3:]},
            "axis_directions": [list(direction)]}


class EngineeringRoleTests(unittest.TestCase):
    def test_slender_cylinder_is_pipe_candidate(self):
        logical = {"components": [tube("P", 25, [0, -25, -25, 500, 25, 25])],
                   "face_to_component": {"FP": "P"}}
        result = classify_tubular_roles(logical, [])
        self.assertEqual(result["candidates"][0]["engineering_role"], "PIPE")

    def test_large_cylinder_is_vessel_candidate(self):
        logical = {"components": [tube("V", 400, [-400, -400, 0, 400, 400, 1000], (0, 0, 1))],
                   "face_to_component": {"FV": "V"}}
        result = classify_tubular_roles(logical, [])
        self.assertEqual(result["candidates"][0]["engineering_role"], "VESSEL_SHELL")

    def test_small_tube_intersecting_large_host_is_nozzle(self):
        logical = {"components": [
            tube("N", 30, [0, -30, -30, 200, 30, 30]),
            tube("V", 400, [-400, -400, -400, 400, 400, 400], (0, 0, 1))],
            "face_to_component": {"FN": "N", "FV": "V"}}
        facts = [{"object_a": "FN", "object_b": "FV", "intersects": True,
                  "surface_intersection": True}]
        result = classify_tubular_roles(logical, facts)
        roles = {item["logical_component_id"]: item["engineering_role"]
                 for item in result["candidates"]}
        self.assertEqual(roles["N"], "NOZZLE")
        self.assertEqual(roles["V"], "VESSEL_SHELL")

    def test_torus_is_bend_candidate(self):
        logical = {"components": [tube("B", 30, [0, 0, 0, 100, 100, 60],
                                               kind="PIPE_BEND_CANDIDATE")],
                   "face_to_component": {"FB": "B"}}
        result = classify_tubular_roles(logical, [])
        self.assertEqual(result["candidates"][0]["engineering_role"], "PIPE_BEND")


if __name__ == "__main__":
    unittest.main()
