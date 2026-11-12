import unittest
from catia_checker.face_traceability import bind_single_body_faces

class FaceTraceabilityTests(unittest.TestCase):
    def test_binds_faces_only_after_one_solid_validation(self):
        manifest={"shapes":[{"shape_id":"STEP_ROOT","solid_count":1},{"shape_id":"STEP_FACE_000001","surface_features":{"surface_type":"PLANE"}}]}
        result=bind_single_body_faces(manifest,{"source_body_index":7,"source_body_name":"Host"})
        self.assertTrue(result["coverage_complete"]); self.assertEqual(result["faces"][0]["face_id"],"BODY_000007::STEP_FACE_000001")
        self.assertEqual(result["faces"][0]["source_body_name"],"Host")
    def test_rejects_multi_solid_export(self):
        manifest={"shapes":[{"shape_id":"STEP_ROOT","solid_count":2},{"shape_id":"STEP_FACE_000001"}]}
        result=bind_single_body_faces(manifest,{"source_body_index":7,"source_body_name":"Host"})
        self.assertFalse(result["coverage_complete"]); self.assertEqual(result["faces"],[])
        self.assertEqual(result["error"]["code"],"BODY_SOLID_MAPPING_COUNT_MISMATCH")
if __name__=="__main__": unittest.main()
