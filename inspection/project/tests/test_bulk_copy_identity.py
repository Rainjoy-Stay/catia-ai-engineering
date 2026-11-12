import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('batch_copy_benchmark',ROOT/'vendor/catia-v5-mcp-server/catia_mcp/tools/batch_copy_benchmark.py')
MODULE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)

class IdentityTests(unittest.TestCase):
    def test_body_names_take_precedence_over_renumbered_features(self):
        copied=[{'original_body_name':'A','identity_names':['A','B']},
                {'original_body_name':'B','identity_names':['B','C']}]
        result=MODULE.unique_copy_matches([{'source_body_name':'B'},{'source_body_name':'A'}],copied)
        self.assertEqual(result[0][1]['original_body_name'],'B')

    def test_reversed_copy_order_uses_names(self):
        result=MODULE.unique_copy_matches([{'source_body_name':'A'},{'source_body_name':'B'}],
            [{'identity_names':['B']},{'identity_names':['A']}])
        self.assertEqual(result[0][1]['identity_names'],['A'])

    def test_ambiguous_names_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_copy_matches([{'source_body_name':'A'}],
                [{'identity_names':['A']},{'identity_names':['A']}])

    def test_extra_body_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.unique_copy_matches([{'source_body_name':'A'}],
                [{'identity_names':['A']},{'identity_names':['B']}])

    def test_geometry_difference_and_nonfinite_rejected(self):
        first={'volume_mm3':1,'surface_area_mm2':6}
        self.assertTrue(MODULE.same_measurements(first,dict(first)))
        self.assertFalse(MODULE.same_measurements(first,{'volume_mm3':2,'surface_area_mm2':6}))
        self.assertFalse(MODULE.same_measurements(first,{'volume_mm3':float('nan'),'surface_area_mm2':6}))

    def test_centroid_shift_or_missing_output_rejected(self):
        first={'volume_mm3':1,'surface_area_mm2':6,'centroid_verified':True,'centroid_mm':[1,2,3]}
        second={**first,'centroid_mm':[2,2,3]}
        self.assertFalse(MODULE.same_measurements(first,second))
        self.assertFalse(MODULE.same_measurements(first,{'volume_mm3':1,'surface_area_mm2':6}))

if __name__=='__main__':unittest.main()
