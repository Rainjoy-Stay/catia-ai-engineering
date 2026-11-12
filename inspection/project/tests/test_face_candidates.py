import unittest
from catia_checker.face_candidates import select_face_body_indices

def finding(issue,status,a,b=None):
    metadata={"source_body_a":{"source_body_index":a}}
    if b: metadata["source_body_b"]={"source_body_index":b}
    return {"issue_id":issue,"status":status,"metadata":metadata}

class FaceCandidateTests(unittest.TestCase):
    def test_prioritizes_fail_and_deduplicates(self):
        report={"findings":[finding("W","WARN",4),finding("F","FAIL",2,4),finding("P","PASS",1)]}
        result=select_face_body_indices(report,2)
        self.assertEqual(result["body_indices"],[2,4]); self.assertFalse(result["truncated"])
    def test_limit_is_explicit(self):
        report={"findings":[finding("A","FAIL",1),finding("B","FAIL",2),finding("C","WARN",3)]}
        result=select_face_body_indices(report,2)
        self.assertEqual(result["body_indices"],[1,2]); self.assertTrue(result["truncated"])
    def test_rejects_invalid_limit(self):
        with self.assertRaises(ValueError): select_face_body_indices({},0)
if __name__=="__main__": unittest.main()
