import unittest

from catia_checker.route_design_constraints import RouteDesignCase
from catia_checker.route_design_optimizer import optimize_route_design_space
from catia_checker.spatial_route_planning import (
    SpatialRouteRequest, SpatialRouteResult, SurfacePort, TriangleMesh,
)


class _Planner:
    def plan(self, request):
        points = ((0,0,0),(30,0,0),(30,15,0),(60,15,0))
        return SpatialRouteResult(
            "OK", points, objective_score=100.0,
            candidate_count=1, candidate_scores=(100.0,),
        )


class RouteDesignOptimizerTests(unittest.TestCase):
    def test_joint_optimizer_assigns_each_bend_and_keeps_diameters_separate(self):
        mesh = TriangleMesh("box", ((0,0,0),), ())
        request = SpatialRouteRequest(
            mesh, (), SurfacePort((0,0,0),(1,0,0),1),
            SurfacePort((1,1,1),(-1,0,0),1),
        )
        cases = tuple(
            RouteDesignCase(diameter, radius, 0, 0, None, "REFERENCE_ONLY", False)
            for diameter in (4.0, 6.0) for radius in (5.0, 10.0, 15.0)
        )
        result = optimize_route_design_space(request, cases, planner=_Planner())
        self.assertEqual(result.status, "REVIEW_DIAMETER_SELECTION")
        self.assertEqual(len(result.best_by_diameter), 2)
        self.assertEqual(result.best_by_diameter[0].bend_radii_mm, (10.0, 5.0))


if __name__ == "__main__":
    unittest.main()
