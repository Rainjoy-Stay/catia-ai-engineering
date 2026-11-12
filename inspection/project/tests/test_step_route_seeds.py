import unittest
from standalone.step_pipe_semantics.route_seeds import tangent_route_seeds


def cylinder(origin=(10,0,0),direction=(0,1,0),radius=2):
    return {'shape_id':'C','surface_features':{'surface_type':'CYLINDER','radius_mm':radius,
        'axis_origin_mm':list(origin),'axis_direction':list(direction),'area_mm2':10}}


def torus(radius=2):
    return {'shape_id':'T','surface_features':{'surface_type':'TORUS','major_radius_mm':10,
        'minor_radius_mm':radius,'axis_origin_mm':[0,0,0],'axis_direction':[0,0,1]}}


class RouteSeedAcceptance(unittest.TestCase):
    def test_tangent_support_remains_unverified(self):
        seeds=tangent_route_seeds([cylinder(),torus()])
        self.assertEqual(len(seeds),1)
        self.assertEqual(seeds[0]['support_tangent_point_mm'],[10,0,0])
        self.assertFalse(seeds[0]['topology_verified'])
        self.assertFalse(seeds[0]['outer_surface_confirmed'])

    def test_secant_axis_rejected(self):
        self.assertEqual(tangent_route_seeds([cylinder(origin=(9,0,0)),torus()]),[])

    def test_axis_above_circle_plane_rejected(self):
        self.assertEqual(tangent_route_seeds([cylinder(origin=(10,0,1)),torus()]),[])

    def test_coaxial_rounding_rejected(self):
        self.assertEqual(tangent_route_seeds([cylinder(direction=(0,0,1)),torus()]),[])

    def test_section_radius_mismatch_rejected(self):
        self.assertEqual(tangent_route_seeds([cylinder(),torus(radius=.025)]),[])


if __name__=='__main__': unittest.main()
