import unittest

from catia_checker.geometry_candidates import build_geometry_candidates


def entity(name, kind, bounds, **extra):
    return {"object_id": name, "geometry_kind": kind, "geometry_state": "AVAILABLE",
            "coordinate_space": "WORLD", "bounds_mm": bounds, **extra}


class GeometryCandidateTests(unittest.TestCase):
    def test_surface_is_retained_in_broad_phase(self):
        result = build_geometry_candidates([
            entity("Pipe", "SOLID", [0, 0, 0, 10, 2, 2]),
            entity("Bulkhead", "SURFACE", [9, -5, -5, 9, 5, 5]),
        ], search_margin_mm=1)
        self.assertEqual(result["candidate_pair_count"], 1)
        self.assertEqual(result["candidates"][0]["entity_kind_b"], "SURFACE")

    def test_separated_pair_is_not_precise_candidate(self):
        result = build_geometry_candidates([
            entity("A", "SOLID", [0, 0, 0, 1, 1, 1]),
            entity("B", "SURFACE", [20, 0, 0, 20, 1, 1]),
        ], search_margin_mm=5)
        self.assertEqual(result["candidate_pair_count"], 0)

    def test_missing_world_bounds_is_traceable(self):
        result = build_geometry_candidates([{"object_id": "LocalSurface", "geometry_kind": "SURFACE",
                                              "geometry_state": "AVAILABLE"}], search_margin_mm=1)
        self.assertEqual(result["skip_log"], [{"object_id": "LocalSurface", "why_skipped": "NO_WORLD_BOUNDS"}])

    def test_same_logical_component_never_self_pairs(self):
        result = build_geometry_candidates([
            entity("PipeSegment1", "SOLID", [0, 0, 0, 2, 2, 2], logical_component_id="PIPE-1"),
            entity("PipeSegment2", "SOLID", [1, 0, 0, 3, 2, 2], logical_component_id="PIPE-1"),
        ], search_margin_mm=1)
        self.assertEqual(result["candidate_pair_count"], 0)
        self.assertEqual(result["skip_log"][0]["why_skipped"], "SAME_LOGICAL_COMPONENT")


if __name__ == "__main__":
    unittest.main()
