import unittest

from catia_checker.intersection_events import aggregate_intersection_events


def fact(a, b, center):
    return {"object_a": a, "object_b": b, "surface_intersection": True,
            "intersection_type": "SURFACE_INTERSECTION", "section_center_mm": center,
            "section_bounds_mm": {"min": [v - 1 for v in center], "max": [v + 1 for v in center]},
            "section_edge_count": 1}


class IntersectionEventTests(unittest.TestCase):
    def test_merges_local_records_with_a_shared_face(self):
        result = aggregate_intersection_events([
            fact("PIPE-A", "VESSEL-1", [0, 0, 0]),
            fact("PIPE-B", "VESSEL-1", [4, 0, 0]),
        ], merge_tolerance_mm=5)
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["events"][0]["face_pair_count"], 2)

    def test_does_not_merge_remote_records_on_same_vessel_face(self):
        result = aggregate_intersection_events([
            fact("PIPE-A", "VESSEL-1", [0, 0, 0]),
            fact("PIPE-B", "VESSEL-1", [1000, 0, 0]),
        ], merge_tolerance_mm=25)
        self.assertEqual(result["event_count"], 2)

    def test_does_not_merge_nearby_unrelated_faces(self):
        result = aggregate_intersection_events([
            fact("A", "B", [0, 0, 0]), fact("C", "D", [1, 0, 0])])
        self.assertEqual(result["event_count"], 2)

    def test_ignores_contacts_and_preserves_face_fact_count(self):
        contact = fact("A", "B", [0, 0, 0])
        contact.update({"surface_intersection": False, "intersection_type": "CONTACT"})
        result = aggregate_intersection_events([contact])
        self.assertEqual(result["input_face_pair_count"], 0)
        self.assertTrue(result["face_facts_preserved"])


if __name__ == "__main__":
    unittest.main()
