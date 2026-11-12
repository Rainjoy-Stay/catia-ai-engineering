import unittest

from catia_checker.geometry_executor import execute_precision_queue, precision_plan


def candidate(a, b, kind_a, kind_b):
    return {"pair_id": f"{a}|{b}", "object_a": a, "object_b": b,
            "entity_kind_a": kind_a, "entity_kind_b": kind_b}


class GeometryExecutorTests(unittest.TestCase):
    def test_solid_pair_uses_native_dmu(self):
        entities = {"A": {"capabilities": ["EXACT_BREP"]}, "B": {"capabilities": ["EXACT_BREP"]}}
        plan = precision_plan(candidate("A", "B", "SOLID", "SOLID"), entities)
        self.assertEqual(plan["method"], "CATIA_DMU_SOLID_CLASH")
        self.assertTrue(plan["requires_closed_volume"])

    def test_surface_pair_uses_brep_intersection(self):
        entities = {"A": {"capabilities": ["EXACT_BREP"]}, "B": {"capabilities": ["EXACT_BREP"]}}
        plan = precision_plan(candidate("A", "B", "SOLID", "SURFACE"), entities)
        self.assertEqual(plan["method"], "OCCT_BREP_EXACT")
        self.assertTrue(plan["requires_intersection_points"])

    def test_missing_capability_is_not_silently_dropped(self):
        result = execute_precision_queue([candidate("A", "B", "SOLID", "SURFACE")],
                                         [{"object_id": "A"}, {"object_id": "B"}], lambda _: {})
        self.assertEqual(result["not_executable_count"], 1)
        self.assertEqual(result["execution_log"][0]["reason"], "NO_COMMON_PRECISE_GEOMETRY_CAPABILITY")

    def test_provider_failure_requires_review(self):
        entities = [{"object_id": "A", "capabilities": ["EXACT_BREP"]},
                    {"object_id": "B", "capabilities": ["EXACT_BREP"]}]
        result = execute_precision_queue([candidate("A", "B", "SOLID", "SURFACE")], entities,
                                         lambda _: (_ for _ in ()).throw(RuntimeError("kernel")))
        self.assertEqual(result["review_count"], 1)
        self.assertEqual(result["facts"], [])


if __name__ == "__main__":
    unittest.main()
