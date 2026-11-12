import math
import unittest
from OCP.Geom import Geom_CylindricalSurface,Geom_RectangularTrimmedSurface,Geom_Plane
from OCP.GeomConvert import GeomConvert
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.gp import gp_Ax3,gp_Pnt,gp_Dir
from standalone.step_pipe_semantics.surface_recovery import recover_surface_support


class SurfaceRecoveryAcceptance(unittest.TestCase):
    def bspline(self,axis=None):
        axis=axis or gp_Ax3(gp_Pnt(0,0,0),gp_Dir(0,0,1))
        source=Geom_RectangularTrimmedSurface(Geom_CylindricalSurface(axis,2),0,2*math.pi,0,10)
        return GeomConvert.SurfaceToBSplineSurface_s(source)

    def face(self,surface): return BRepBuilderAPI_MakeFace(surface,1e-7).Face()

    def test_exact_bspline_cylinder_recovered(self):
        result=recover_surface_support(self.face(self.bspline()))
        self.assertTrue(result['support_recovered'])
        self.assertEqual(result['recovered_support']['surface_type'],'CYLINDER')
        self.assertAlmostEqual(result['recovered_support']['radius_mm'],2)
        self.assertFalse(result['design_cavity_confirmed'])
        self.assertIsNone(result['wall_thickness_mm'])

    def test_rotated_translated_cylinder(self):
        result=recover_surface_support(self.face(self.bspline(gp_Ax3(gp_Pnt(12,-8,9),gp_Dir(1,2,3)))))
        self.assertTrue(result['support_recovered'])
        self.assertAlmostEqual(result['recovered_support']['radius_mm'],2)

    def test_deformed_bspline_not_misclassified_as_exact_cylinder(self):
        surface=self.bspline(); pole=surface.Pole(2,2)
        surface.SetPole(2,2,gp_Pnt(pole.X()+.2,pole.Y(),pole.Z()))
        result=recover_surface_support(self.face(surface))
        self.assertFalse(result['support_recovered'])

    def test_bspline_plane_is_not_cylinder(self):
        source=Geom_RectangularTrimmedSurface(Geom_Plane(gp_Ax3(gp_Pnt(0,0,0),gp_Dir(0,0,1))),0,10,0,10)
        result=recover_surface_support(self.face(GeomConvert.SurfaceToBSplineSurface_s(source)))
        self.assertTrue(result['support_recovered'])
        self.assertEqual(result['recovered_support']['surface_type'],'PLANE')


if __name__=='__main__': unittest.main()
