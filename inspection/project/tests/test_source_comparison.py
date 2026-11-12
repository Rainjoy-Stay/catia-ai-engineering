import unittest
from catia_checker.source_comparison import classify_source_comparison as classify
class SourceComparisonTests(unittest.TestCase):
    def test_zero_does_not_auto_pass(self):
        r=classify({'details':{'input_valid':[True,True],'common_valid':True,'common_volume_raw_mm3':0}},{},{})
        self.assertEqual(r['classification'],'SOURCE_DIFFERENCE_CANDIDATE');self.assertFalse(r['screen_pass'])
    def test_invalid_original_unknown(self):self.assertEqual(classify({'details':{'input_valid':[False,True]}},{},{})['classification'],'UNRESOLVED')
    def test_explicit_contact_pass(self):
        f={'surface':{'exact_brep':True,'intersection_type':'CONTACT','boundary_contact':True,'surface_intersection':False}}
        d={'details':{'input_valid':[True,True],'common_valid':True}}
        self.assertTrue(classify({},f,d)['screen_pass'])
        f['surface']['penetration_confirmed']=True
        self.assertFalse(classify({},f,d)['screen_pass'])
