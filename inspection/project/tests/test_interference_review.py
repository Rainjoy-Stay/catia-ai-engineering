import unittest
from catia_checker.interference_review import assess

class ReviewTests(unittest.TestCase):
    def row(self):
        return {'pair': ['A', 'B'], 'category': 'SMALL_OVERLAP_CANDIDATE'}
    def test_invalid_input_has_priority(self):
        result = assess(self.row(), {'details': {'input_valid': [False, True], 'common_valid': True}})
        self.assertEqual(result['status'], 'INVALID_INPUT_GEOMETRY')
        self.assertFalse(result['excluded'])
    def test_known_invalid_propagates_without_exclusion(self):
        result = assess(self.row(), invalid_objects={'A'})
        self.assertEqual(result['invalid_objects'], ['A'])
        self.assertFalse(result['conversion_confirmed'])
    def test_recomputed_does_not_confirm_real_or_pseudo(self):
        result = assess(self.row(), {'details': {'input_valid': [True, True], 'common_valid': True}})
        self.assertEqual(result['status'], 'GEOMETRY_REPRODUCED')
        self.assertFalse(result['real_interference_confirmed'])
    def test_timeout_stays_unresolved(self):
        self.assertEqual(assess(self.row(), {'status': 'TIMEOUT'})['status'], 'REVIEW_INCOMPLETE')
    def test_invalid_common(self):
        self.assertEqual(assess(self.row(), {'details': {'common_valid': False}})['status'], 'INVALID_COMMON_GEOMETRY')
