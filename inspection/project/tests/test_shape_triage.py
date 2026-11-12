import unittest
from catia_checker.shape_triage import classify
class ShapeTriageTests(unittest.TestCase):
    def test_coincident_never_excluded(self):
        obj={'volume_mm3':10,'bounds_mm':{'min':[0,0,0],'max':[2,2,2]}}
        value=classify(obj,obj,{'common':{'exact_brep':True,'intersection_volume_mm3':10}})
        self.assertEqual(value['category'],'COINCIDENT_SOLID_CANDIDATE');self.assertFalse(value['excluded'])
    def test_missing_volume_not_duplicate(self):
        self.assertEqual(classify({},{},{'common':{'exact_brep':True,'intersection_volume_mm3':2}})['category'],'SOLID_OVERLAP')
    def test_small_overlap_not_conversion(self):
        v=classify({'volume_mm3':10},{'volume_mm3':20},{'common':{'exact_brep':True,'intersection_volume_mm3':.001}})
        self.assertEqual(v['category'],'SMALL_OVERLAP_CANDIDATE');self.assertFalse(v['conversion_confirmed'])
    def test_surface_priority(self):
        v=classify({},{},{'surface':{'exact_brep':True,'coincident_surface_overlap':True,'penetration_evidence_available':True,'penetration_confirmed':True}})
        self.assertEqual(v['category'],'SURFACE_CROSSING')
    def test_unknown_never_passes(self):
        self.assertEqual(classify({},{},{})['category'],'UNRESOLVED')
