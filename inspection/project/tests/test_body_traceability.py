import unittest
from catia_checker.body_traceability import merge_verified_body_mapping

class BodyTraceabilityTests(unittest.TestCase):
    def test_merges_primary_rescue_and_group_without_order_fallback(self):
        payload={"large_single_part_analysis":{"batch_plan":{"shapes":[{"shape_id":"A"},{"shape_id":"B"},{"shape_id":"C"}]}},"findings":[],"confidence_budget":{"degraded":[]}}
        replay={"matches":[{"source_id":"A","target_id":"1","mapping_method":"LABEL"}],"target_records":{"1":{"source_body_name":"One"},"2":{"source_body_name":"Two"}}}
        rescue={"assignments":[{"shape_id":"B","source_body_index":2,"mapping_method":"PROBE"},{"shape_id":"C","source_body_index":2,"mapping_method":"PROBE"}]}
        audit=merge_verified_body_mapping(payload,replay,rescue)
        self.assertTrue(audit["is_complete"]); self.assertEqual(["B","C"],audit["one_to_many_body_groups"]["2"]); self.assertFalse(audit["sequence_fallback_used"])

if __name__=="__main__": unittest.main()
