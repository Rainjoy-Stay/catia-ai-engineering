import unittest
from catia_checker.integration_stability import assess_integrations
class StabilityTests(unittest.TestCase):
    def test_small_reported_error_does_not_override_change(self):
        samples=[{'volume_mm3':v,'centroid_mm':[0,0,0],'estimated_relative_error':1e-10} for v in (1,1.1)]
        self.assertFalse(assess_integrations(samples)['stable'])
    def test_converged(self):
        samples=[{'volume_mm3':v,'centroid_mm':[0,0,0]} for v in (1,1.0000001)]
        self.assertTrue(assess_integrations(samples)['stable'])
    def test_single_not_enough(self):self.assertFalse(assess_integrations([{}])['stable'])
