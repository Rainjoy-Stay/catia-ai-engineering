import unittest,math
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Pnt
from catia_checker.occt_brep import _mass_properties

def face(points):
 p=BRepBuilderAPI_MakePolygon()
 for v in points:p.Add(gp_Pnt(*v))
 p.Close();return BRepBuilderAPI_MakeFace(p.Wire()).Face()
class PhysicalMassPropertiesTest(unittest.TestCase):
 def check_center(self,actual,expected):
  for a,b in zip(actual,expected):self.assertAlmostEqual(a,b,places=9)
 def test_offset_plane_and_reversed_plane(self):
  s=face([(0,0,3),(2,0,3),(2,2,3),(0,2,3)])
  for surface in [s,s.Reversed()]:
   p=_mass_properties(surface);self.assertEqual(p['volume_mm3'],0);self.assertAlmostEqual(p['surface_area_mm2'],4);self.check_center(p['centroid_mm'],[1,1,3])
 def test_tilted_plane(self):
  p=_mass_properties(face([(0,0,1),(2,0,3),(2,2,3),(0,2,1)]));self.assertEqual(p['volume_mm3'],0);self.assertAlmostEqual(p['surface_area_mm2'],4*math.sqrt(2));self.check_center(p['centroid_mm'],[1,1,2])
 def test_solid_preserved(self):
  p=_mass_properties(BRepPrimAPI_MakeBox(gp_Pnt(10,20,30),2,3,4).Solid());self.assertAlmostEqual(p['volume_mm3'],24);self.assertAlmostEqual(p['surface_area_mm2'],52);self.check_center(p['centroid_mm'],[11,21.5,32])
 def test_free_face_does_not_change_compound_material_mass(self):
  b=BRep_Builder();c=TopoDS_Compound();b.MakeCompound(c);b.Add(c,BRepPrimAPI_MakeBox(gp_Pnt(10,20,30),2,3,4).Solid());b.Add(c,face([(0,0,3),(2,0,3),(2,2,3),(0,2,3)]));p=_mass_properties(c);self.assertAlmostEqual(p['volume_mm3'],24);self.assertAlmostEqual(p['surface_area_mm2'],56);self.check_center(p['centroid_mm'],[11,21.5,32])
if __name__=='__main__':unittest.main()
