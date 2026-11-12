import unittest
from pathlib import Path

from catia_checker.occt_brep import OCCTBRepModel, backend_status, sweep_and_prune_pairs
from catia_checker.semantic_interactions import assess_solid_interactions
from catia_checker.large_single_part import inspect_large_single_part_batches_isolated


FIXTURE = (Path(__file__).resolve().parents[1] / "test_models" /
           "interface_semantics" / "AI_Check_Interface_Case_01_v2.step")


@unittest.skipUnless(backend_status()["available"] and FIXTURE.exists(),
                     "OCCT or CATIA-generated STEP fixture unavailable")
class InterfaceSemanticsFixtureTests(unittest.TestCase):
    def test_body_mapping_count_mismatch_closes_coverage(self):
        rules={"large_single_part":{"pair_timeout_seconds":5,"pair_retry_timeout_seconds":5,"max_pair_retries":0,"max_pair_workers":1,"max_exact_pairs":10}}
        result=inspect_large_single_part_batches_isolated([FIXTURE],rules=rules,body_mapping=[{"batch_id":"BATCH_0001","source_body_index":1,"source_body_name":"Only one"}])
        self.assertFalse(result["body_traceability"]["is_complete"])
        self.assertFalse(result["analysis"]["coverage_complete"])
        self.assertEqual(result["body_traceability"]["mapping_errors"][0]["code"],"BODY_SOLID_MAPPING_COUNT_MISMATCH")

    def test_lightweight_manifest_preserves_exact_candidates(self):
        full_model = OCCTBRepModel(); full = full_model.load_step(FIXTURE)
        light_model = OCCTBRepModel(); light = light_model.load_step(FIXTURE, lightweight=True)
        full_shapes = [x for x in full["shapes"] if x["shape_id"] != full["root_shape_id"]]
        light_shapes = [x for x in light["shapes"] if x["shape_id"] != light["root_shape_id"]]
        self.assertEqual(sweep_and_prune_pairs(full_shapes)["pairs"],
                         sweep_and_prune_pairs(light_shapes)["pairs"])
        self.assertTrue(all(x["valid"] is None and x["face_count"] is None for x in light_shapes))

    def test_opening_passes_and_unopened_nozzle_fails(self):
        model = OCCTBRepModel()
        manifest = model.load_step(FIXTURE)
        shapes = [item for item in manifest["shapes"]
                  if item["shape_id"] != manifest["root_shape_id"]]
        candidates = sweep_and_prune_pairs(shapes)["pairs"]
        facts = [model.pair_fact(
            first, second,
            entity_a={"geometry_kind": "SOLID", "capabilities": ["EXACT_BREP"]},
            entity_b={"geometry_kind": "SOLID", "capabilities": ["EXACT_BREP"]},
        ) for first, second in candidates]
        result = assess_solid_interactions(facts)

        self.assertEqual(len(shapes), 3)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(result["disposition_counts"], {"PASS": 1, "FAIL": 1})
        passed = next(item for item in result["assessments"]
                      if item["disposition"] == "PASS")
        failed = next(item for item in result["assessments"]
                      if item["disposition"] == "FAIL")
        self.assertAlmostEqual(passed["minimum_distance_mm"], 0.2, delta=0.01)
        self.assertGreater(failed["intersection_volume_mm3"], 5000.0)
        self.assertGreater(failed["section_edge_count"], 0)


if __name__ == "__main__":
    unittest.main()
