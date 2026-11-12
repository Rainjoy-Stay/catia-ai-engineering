import unittest

from catia_checker.model_understanding.features import (
    analytic_centerline_primitives, build_composite_centerline, derive_step_pipe_features,
)


class AnalyticCenterlineTests(unittest.TestCase):
    def test_coaxial_cylinder_faces_merge_into_one_axis(self):
        body = {"faces": [
            {"face_id": "#1", "surface_type": "CYLINDER", "parameters": {"radius": 5.0},
             "placement": {"origin_mm": [0, 0, 0], "axis_direction": [0, 0, 1]}},
            {"face_id": "#2", "surface_type": "CYLINDER", "parameters": {"radius": 5.01},
             "placement": {"origin_mm": [0.01, 0, 20], "axis_direction": [0, 0, -1]}},
        ]}
        result = analytic_centerline_primitives(body)
        self.assertEqual(result["line_axis_count"], 1)
        self.assertEqual(result["primitives"][0]["source_face_ids"], ["#1", "#2"])
        self.assertEqual(result["primitives"][0]["trim_state"], "UNTRIMMED")

    def test_offset_axes_remain_separate(self):
        body = {"faces": [
            {"face_id": "#1", "surface_type": "CYLINDER", "parameters": {"radius": 5},
             "placement": {"origin_mm": [0, 0, 0], "axis_direction": [1, 0, 0]}},
            {"face_id": "#2", "surface_type": "CYLINDER", "parameters": {"radius": 5},
             "placement": {"origin_mm": [0, 1, 0], "axis_direction": [1, 0, 0]}},
        ]}
        self.assertEqual(analytic_centerline_primitives(body)["line_axis_count"], 2)

    def test_torus_creates_center_circle_not_straight_axis(self):
        body = {"faces": [{
            "face_id": "#3", "surface_type": "TORUS",
            "parameters": {"major_radius": 50, "minor_radius": 5},
            "placement": {"origin_mm": [10, 20, 30], "axis_direction": [0, 1, 0]},
        }]}
        result = analytic_centerline_primitives(body)
        self.assertEqual(result["circle_count"], 1)
        self.assertEqual(result["primitives"][0]["centerline_radius_mm"], 50)

    def test_matching_circular_boundaries_trim_a_cylinder_axis(self):
        face = {
            "face_id": "#1", "surface_type": "CYLINDER", "parameters": {"radius": 5},
            "placement": {"origin_mm": [0, 0, 0], "axis_direction": [0, 0, 1]},
            "boundary_curves": [
                {"curve_type": "CIRCLE", "radius_mm": 5,
                 "placement": {"origin_mm": [0, 0, 10], "axis_direction": [0, 0, 1]}},
                {"curve_type": "CIRCLE", "radius_mm": 5,
                 "placement": {"origin_mm": [0, 0, 30], "axis_direction": [0, 0, -1]}},
            ],
        }
        primitive = analytic_centerline_primitives({"faces": [face]})["primitives"][0]
        self.assertEqual(primitive["trim_state"], "TRIMMED")
        self.assertEqual(primitive["length_mm"], 20.0)
        derived = derive_step_pipe_features({
            "faces": [face],
            "tubular_features": {"dominant_radius": 5, "diameter_variation": 0,
                                 "tubular_surface_ratio": 1.0},
        })
        self.assertEqual(derived["terminal_count"], 2)
        self.assertEqual(derived["centerline_continuity"], 1.0)
        self.assertEqual(derived["aspect_ratio_max_second"], 2.0)

    def test_multiple_axes_do_not_invent_terminal_count(self):
        faces = []
        for index, origin in enumerate(([0, 0, 0], [0, 5, 0]), 1):
            faces.append({"face_id": f"#{index}", "surface_type": "CYLINDER",
                          "parameters": {"radius": 2},
                          "placement": {"origin_mm": origin, "axis_direction": [1, 0, 0]},
                          "boundary_curves": []})
        result = derive_step_pipe_features({"faces": faces,
            "tubular_features": {"dominant_radius": 2}})
        self.assertIsNone(result["terminal_count"])

    def test_two_tangent_lines_trim_a_torus_center_arc(self):
        def line(face_id, start, end, direction):
            return {"face_id": face_id, "surface_type": "CYLINDER", "parameters": {"radius": 1},
                    "placement": {"origin_mm": start, "axis_direction": direction},
                    "boundary_curves": [
                        {"curve_type": "CIRCLE", "radius_mm": 1,
                         "placement": {"origin_mm": start, "axis_direction": direction}},
                        {"curve_type": "CIRCLE", "radius_mm": 1,
                         "placement": {"origin_mm": end, "axis_direction": direction}},
                    ]}
        faces = [
            line("#1", [-10, 10, 0], [0, 10, 0], [1, 0, 0]),
            line("#2", [10, 0, 0], [10, -10, 0], [0, -1, 0]),
            {"face_id": "#3", "surface_type": "TORUS",
             "parameters": {"major_radius": 10, "minor_radius": 1},
             "placement": {"origin_mm": [0, 0, 0], "axis_direction": [0, 0, 1]}},
        ]
        result = build_composite_centerline({"faces": faces})
        arc = next(item for item in result["segments"] if item["primitive_type"] == "ARC")
        self.assertAlmostEqual(arc["turn_angle_deg"], 90.0)
        self.assertEqual(result["terminal_count"], 2)
        self.assertTrue(result["complete"])


if __name__ == "__main__":
    unittest.main()
