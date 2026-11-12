import unittest

from standalone.opening_interface_analysis import (
    analyze_interface, analyze_interfaces, match_openings_to_nozzles,
    analyze_opening_network,
    adapt_exact_geometry,
    merge_coaxial_cylinders,
    infer_wall_thickness_from_opening_pairs,
)


def opening(**changes):
    value = {"opening_id": "O-1", "center_mm": [100, 0, 50],
             "normal": [1, 0, 0], "radius_mm": 20.2,
             "host_wall_thickness_mm": 10.0, "boundary_complete": True,
             "host_discontinuity_confirmed": True, "exact_brep": True}
    value.update(changes)
    return value


def nozzle(**changes):
    value = {"nozzle_id": "N-1", "axis_point_mm": [50, 0, 50],
             "axis_direction": [1, 0, 0], "outer_radius_mm": 20.0,
             "axis_start_mm": 0.0, "axis_end_mm": 70.0, "exact_brep": True}
    value.update(changes)
    return value


class OpeningInterfaceAnalysisTests(unittest.TestCase):
    def test_complete_aligned_interface_passes(self):
        result = analyze_interface(opening(), nozzle())
        self.assertEqual(result["disposition"], "PASS")
        self.assertAlmostEqual(result["measurements"]["radial_clearance_mm"], 0.2)
        self.assertTrue(result["measurements"]["spans_host_wall"])

    def test_offset_nozzle_fails(self):
        result = analyze_interface(opening(), nozzle(axis_point_mm=[50, 2, 50]))
        self.assertEqual(result["disposition"], "FAIL")
        self.assertIn("AXIS_OFFSET_OUT_OF_TOLERANCE", result["failure_codes"])

    def test_nozzle_stopping_before_wall_fails(self):
        result = analyze_interface(opening(), nozzle(axis_end_mm=40))
        self.assertEqual(result["disposition"], "FAIL")
        self.assertIn("NOZZLE_DOES_NOT_CROSS_OPENING_PLANE", result["failure_codes"])

    def test_missing_opening_proof_is_review(self):
        result = analyze_interface(opening(host_discontinuity_confirmed=False), nozzle())
        self.assertEqual(result["disposition"], "REVIEW")
        self.assertIn("HOST_WALL_DISCONTINUITY_REQUIRED", result["review_codes"])

    def test_batch_keeps_all_three_dispositions(self):
        result = analyze_interfaces([
            {"opening": opening(opening_id="PASS"), "nozzle": nozzle()},
            {"opening": opening(opening_id="FAIL"),
             "nozzle": nozzle(axis_point_mm=[50, 2, 50])},
            {"opening": opening(opening_id="REVIEW", boundary_complete=False),
             "nozzle": nozzle()},
        ])
        self.assertEqual(result["disposition_counts"], {"PASS": 1, "FAIL": 1, "REVIEW": 1})

    def test_spatial_matching_avoids_remote_pairs(self):
        result = match_openings_to_nozzles(
            [opening(opening_id="O-NEAR"),
             opening(opening_id="O-FAR", center_mm=[1000, 0, 50])],
            [nozzle(nozzle_id="N-NEAR")])
        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["unmatched_opening_ids"], ["O-FAR"])
        self.assertEqual(result["broad_phase"]["total_possible_pairs"], 2)
        self.assertEqual(result["broad_phase"]["spatial_candidate_pairs"], 1)

    def test_similar_duplicate_nozzles_are_review_not_auto_assigned(self):
        result = match_openings_to_nozzles(
            [opening()], [nozzle(nozzle_id="N-1"), nozzle(nozzle_id="N-2")])
        self.assertEqual(result["match_count"], 0)
        self.assertEqual(result["ambiguities"][0]["disposition"], "REVIEW")
        self.assertEqual(result["unmatched_nozzle_ids"], ["N-1", "N-2"])

    def test_network_reports_unopened_nozzle_and_orphan_opening(self):
        result = analyze_opening_network(
            [opening(opening_id="O-GOOD"),
             opening(opening_id="O-ORPHAN", center_mm=[1000, 0, 50])],
            [nozzle(nozzle_id="N-GOOD"),
             nozzle(nozzle_id="N-NO-OPENING", axis_point_mm=[50, 500, 50])])
        self.assertEqual(result["disposition_counts"], {"PASS": 1, "FAIL": 1, "REVIEW": 1})
        self.assertTrue(any("NO_MATCHING_OPENING" in item["failure_codes"]
                            for item in result["results"]))
        self.assertTrue(any("ORPHAN_OPENING_WITHOUT_NOZZLE" in item["review_codes"]
                            for item in result["results"]))
        self.assertFalse(result["source_model_modified"])

    def test_exact_adapter_accepts_complete_analytic_records(self):
        result = adapt_exact_geometry(
            source="CATIA_SPA",
            opening_face_records=[{
                "face_id": "HOST-F1", "normal": [1, 0, 0],
                "host_wall_thickness_mm": 10, "host_discontinuity_confirmed": True,
                "exact_brep": True, "circular_inner_boundaries": [{
                    "boundary_id": "OPEN-1", "center_mm": [100, 0, 50],
                    "radius_mm": 20.2, "closed": True, "exact_brep": True}]}],
            cylindrical_surface_records=[{
                "surface_id": "NOZ-CYL-1", "component_id": "NOZZLE-1",
                "surface_type": "CYLINDER", "axis_origin_mm": [50, 0, 50],
                "axis_direction": [1, 0, 0], "radius_mm": 20,
                "axis_limits_mm": [0, 70], "exact_brep": True}])
        self.assertTrue(result["ready_for_analysis"])
        self.assertEqual(result["rejected_count"], 0)
        self.assertEqual(result["openings"][0]["opening_id"], "OPEN-1")

    def test_adapter_rejects_incomplete_or_nonanalytic_records(self):
        result = adapt_exact_geometry(
            source="OCCT_BREP",
            opening_face_records=[{"face_id": "F-BAD", "circular_inner_boundaries": []}],
            cylindrical_surface_records=[{"surface_id": "S-BAD", "surface_type": "BSPLINE"}])
        self.assertFalse(result["ready_for_analysis"])
        self.assertEqual(result["rejected_count"], 2)
        self.assertEqual({item["reason"] for item in result["rejected"]},
                         {"NO_CIRCULAR_INNER_BOUNDARIES", "NOT_ANALYTIC_CYLINDER"})

    def test_inner_and_outer_cylinders_merge_into_one_nozzle(self):
        common = {"component_id": "N-1", "axis_point_mm": [0, 5, 5],
                  "axis_direction": [1, 0, 0], "axis_start_mm": 0,
                  "axis_end_mm": 70, "exact_brep": True}
        result = merge_coaxial_cylinders([
            {**common, "surface_id": "OUTER", "surface_radius_mm": 20},
            {**common, "surface_id": "INNER", "surface_radius_mm": 15},
        ])
        self.assertEqual(result["nozzle_count"], 1)
        merged = result["nozzles"][0]
        self.assertEqual(merged["outer_radius_mm"], 20)
        self.assertEqual(merged["inner_radius_mm"], 15)
        self.assertEqual(merged["review_codes"], [])

    def test_separated_collinear_cylinders_are_not_merged(self):
        common = {"component_id": "PIPE-LINE", "axis_point_mm": [0, 0, 0],
                  "axis_direction": [1, 0, 0], "surface_radius_mm": 20,
                  "exact_brep": True}
        result = merge_coaxial_cylinders([
            {**common, "surface_id": "A", "axis_start_mm": 0, "axis_end_mm": 50},
            {**common, "surface_id": "B", "axis_start_mm": 100, "axis_end_mm": 150},
        ])
        self.assertEqual(result["nozzle_count"], 2)

    def test_opposite_hole_boundaries_prove_wall_thickness_and_collapse(self):
        faces = []
        for face_id, x, normal in (("FRONT", 95, [-1, 0, 0]),
                                   ("BACK", 105, [1, 0, 0])):
            faces.append({"face_id": face_id, "normal": normal, "exact_brep": True,
                          "circular_inner_boundaries": [{
                              "boundary_id": face_id + "-HOLE", "center_mm": [x, 0, 0],
                              "normal": normal, "radius_mm": 20.2,
                              "closed": True, "exact_brep": True}]})
        result = infer_wall_thickness_from_opening_pairs(faces)
        self.assertEqual(result["accepted_pair_count"], 1)
        self.assertAlmostEqual(result["accepted_pairs"][0]["wall_thickness_mm"], 10.0)
        self.assertEqual(len(result["analysis_opening_face_records"]), 1)
        logical = result["analysis_opening_face_records"][0]
        self.assertEqual(logical["circular_inner_boundaries"][0]["center_mm"], [100.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
