import unittest

from catia_checker.spatial_route_planning import (
    MeshFreeSpacePlanner,
    SpatialRouteRequest,
    SurfacePort,
    TriangleMesh,
)


def box_mesh(name, lo, hi):
    x0, y0, z0 = lo; x1, y1, z1 = hi
    v = ((x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
         (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1))
    t = ((0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
         (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7))
    return TriangleMesh(name, v, t)


class MeshFreeSpacePlannerTests(unittest.TestCase):
    def test_routes_from_arbitrary_surface_normals_around_mesh(self):
        boundary = box_mesh("boundary", (0, 0, 0), (100, 100, 100))
        obstacle = box_mesh("obstacle", (40, 30, 30), (60, 70, 70))
        request = SpatialRouteRequest(
            boundary, (obstacle,),
            SurfacePort((10, 20, 20), (1, 1, 0), 15),
            SurfacePort((90, 80, 80), (-1, -1, 0), 15),
            grid_size_mm=5, pipe_outer_diameter_mm=4, clearance_mm=1,
        )
        result = MeshFreeSpacePlanner().plan(request)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.points[0], request.start.point)
        self.assertEqual(result.points[-1], request.goal.point)
        self.assertNotEqual(result.start_normal_sign, 0)
        self.assertGreater(result.blocked_cells, 0)
        self.assertGreaterEqual(result.candidate_count, 2)
        self.assertEqual(result.objective_score, min(result.candidate_scores))

    def test_reports_no_route_when_mesh_wall_seals_domain(self):
        boundary = box_mesh("boundary", (0, 0, 0), (50, 50, 50))
        wall = box_mesh("wall", (20, 0, 0), (30, 50, 50))
        request = SpatialRouteRequest(
            boundary, (wall,),
            SurfacePort((5, 25, 25), (1, 0, 0), 5),
            SurfacePort((45, 25, 25), (-1, 0, 0), 5),
            grid_size_mm=5, pipe_outer_diameter_mm=4, clearance_mm=1,
        )
        self.assertEqual(MeshFreeSpacePlanner().plan(request).status, "NO_ROUTE")

    def test_hard_gate_rejects_route_whose_bends_do_not_fit(self):
        boundary = box_mesh("boundary", (0, 0, 0), (50, 50, 50))
        request = SpatialRouteRequest(
            boundary, (),
            SurfacePort((5, 10, 10), (1, 0, 0), 5),
            SurfacePort((40, 35, 10), (-1, 0, 0), 5),
            grid_size_mm=5, pipe_outer_diameter_mm=2, clearance_mm=0,
            bend_radius_mm=20,
        )
        self.assertEqual(MeshFreeSpacePlanner().plan(request).status, "UNMANUFACTURABLE")


if __name__ == "__main__":
    unittest.main()
