import unittest

from catia_checker.route_planning import (
    AABB,
    OrthogonalRoutePlanner,
    PlanningRequest,
    Port,
    request_from_dict,
    result_to_dict,
)


class OrthogonalRoutePlannerTests(unittest.TestCase):
    def test_routes_around_inflated_obstacle_and_returns_candidates(self) -> None:
        request = PlanningRequest(
            start=Port((0, 0, 0), (1, 0, 0), 20),
            goal=Port((200, 0, 0), (-1, 0, 0), 20),
            obstacles=(AABB((80, -20, -20), (120, 20, 20), "equipment"),),
            grid_size_mm=10,
            pipe_outer_diameter_mm=20,
            clearance_mm=5,
            minimum_straight_mm=20,
            bend_radius_mm=20,
            candidate_count=2,
        )
        result = OrthogonalRoutePlanner().plan(request)
        self.assertEqual(result.status, "OK")
        self.assertGreaterEqual(len(result.candidates), 1)
        inflated = request.obstacles[0].inflated(15)
        for candidate in result.candidates:
            self.assertEqual(candidate.points[0], request.start.point)
            self.assertEqual(candidate.points[-1], request.goal.point)
            self.assertTrue(all(not inflated.contains(p) for p in candidate.points[1:-1]))
            self.assertEqual(len(candidate.bend_radii_mm), candidate.bends)
            self.assertEqual(candidate.bends, len(candidate.points) - 2)

    def test_enforces_goal_approach_direction(self) -> None:
        request = PlanningRequest(
            start=Port((0, 0, 0), (1, 0, 0)),
            goal=Port((40, 20, 0), (0, -1, 0)),
            grid_size_mm=10,
            minimum_straight_mm=10,
            bend_radius_mm=10,
            candidate_count=1,
        )
        candidate = OrthogonalRoutePlanner().plan(request).candidates[0]
        before, goal = candidate.points[-2:]
        self.assertEqual((goal[0] - before[0], goal[1] - before[1], goal[2] - before[2]), (0, 20, 0))

    def test_rejects_blocked_mandatory_exit(self) -> None:
        request = PlanningRequest(
            start=Port((0, 0, 0), (1, 0, 0), 20),
            goal=Port((100, 0, 0), (-1, 0, 0), 10),
            obstacles=(AABB((5, -2, -2), (10, 2, 2)),),
            grid_size_mm=5,
            pipe_outer_diameter_mm=2,
            clearance_mm=0,
        )
        result = OrthogonalRoutePlanner().plan(request)
        self.assertEqual(result.status, "NO_ROUTE")
        self.assertIn("port exit", result.message)

    def test_json_boundary_is_arrangement_run_compatible(self) -> None:
        request = request_from_dict({
            "start": {"point": [0, 0, 0], "direction": [1, 0, 0]},
            "goal": {"point": [50, 0, 0], "direction": [-1, 0, 0]},
            "grid_size_mm": 10,
            "bend_radius_mm": 10,
            "candidate_count": 1,
        })
        payload = result_to_dict(OrthogonalRoutePlanner().plan(request))
        self.assertEqual(payload["schema_version"], "1.0.0")
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["candidates"][0]["catia_target"], "native Arrangement Run centerline")

    def test_rejects_off_grid_exit_point_instead_of_creating_diagonal(self) -> None:
        request = PlanningRequest(
            start=Port((1, 0, 0), (1, 0, 0)),
            goal=Port((50, 0, 0), (-1, 0, 0)),
            grid_size_mm=10,
        )
        with self.assertRaisesRegex(ValueError, "align with grid_size_mm"):
            OrthogonalRoutePlanner().plan(request)


if __name__ == "__main__":
    unittest.main()
