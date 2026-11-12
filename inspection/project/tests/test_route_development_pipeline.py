import tempfile
import unittest

from catia_checker.route_design_constraints import RouteDesignCase
from catia_checker.route_development_pipeline import (
    RouteDevelopmentRequest, run_route_development_pipeline,
)
from catia_checker.route_interfaces import RoutePortConstraint
from catia_checker.route_interfaces import ReducerPolicy
from catia_checker.spatial_route_planning import SpatialRouteResult, TriangleMesh


class _Planner:
    def plan(self, request):
        points = ((0,0,0),(30,0,0),(30,30,10),(60,30,10))
        return SpatialRouteResult(
            "OK", points, objective_score=100, candidate_count=1,
            candidate_scores=(100,),
        )


class RouteDevelopmentPipelineTests(unittest.TestCase):
    def _request(self, goal_diameter=4.0):
        mesh = TriangleMesh("domain", ((0,0,0),), ())
        cases = tuple(RouteDesignCase(4, r, 0, 0, None, "REFERENCE_ONLY", False)
                      for r in (5, 10, 15))
        return RouteDevelopmentRequest(
            mesh, (),
            RoutePortConstraint("A", "host-a", (0,0,0), (1,0,0),
                                diameter_candidates_mm=(4,)),
            RoutePortConstraint("B", "host-b", (60,30,10), (-1,0,0),
                                diameter_candidates_mm=(goal_diameter,)),
            cases, 10, 5,
        )

    def test_runs_generic_pipeline_without_catia_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run_route_development_pipeline(self._request(), folder, _Planner())
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["catia_mutation"], "NONE")
        self.assertEqual(result["candidates"][0]["validation"]["status"], "NOT_EVALUATED")

    def test_rejects_mismatched_interface_diameters_without_reducer_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "reducer policy"):
                run_route_development_pipeline(self._request(6.0), folder, _Planner())

    def test_accepts_mismatched_interfaces_with_real_reducer_policy(self):
        request = self._request(6.0)
        request = RouteDevelopmentRequest(
            **{**request.__dict__, "reducer_policy": ReducerPolicy(
                True, start_length_mm=0, goal_length_mm=10,
                maximum_half_angle_deg=15)},
        )
        with tempfile.TemporaryDirectory() as folder:
            result = run_route_development_pipeline(request, folder, _Planner())
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["candidates"][0]["envelope"]["reducer_count"], 1)


if __name__ == "__main__":
    unittest.main()
