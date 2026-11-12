import json
import unittest
from pathlib import Path

from OCP.BRep import BRep_Builder
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS_Shape

from standalone.step_pipe_semantics.exterior import exterior_candidate
from tools.scan_new_export_batch import bend_finding


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'artifacts' / 'spatial_local_15' / 'exterior_scan'


class BSplineSweepIntegrationTests(unittest.TestCase):
    def candidate(self, body):
        detail = json.loads((DATA / f'BODY_{body:06d}.json').read_text(encoding='utf-8'))
        record = detail['records'][0]
        shape = TopoDS_Shape()
        self.assertTrue(BRepTools.Read_s(shape, str(DATA / f'BODY_{body:06d}_SOLID_0001.brep'), BRep_Builder()))
        return exterior_candidate(record['solid'], record['faces'], shape=shape)

    def test_recovers_body_840_centerline_and_radius(self):
        result = self.candidate(840)
        self.assertEqual(result['geometry_kind'], 'BSPLINE_CIRCULAR_SWEEP_EXTERIOR_CANDIDATE')
        self.assertAlmostEqual(result['outer_diameter_mm'], 0.4750541886, places=8)
        self.assertAlmostEqual(result['minimum_radius_ratio_r_over_d'], 3.5659657426, places=7)
        self.assertFalse(result['engineering_pipe_confirmed'])
        self.assertFalse(result['design_cavity_confirmed'])

    def test_recovers_body_841_but_rule_refuses_dn_extrapolation(self):
        result = self.candidate(841)
        self.assertAlmostEqual(result['minimum_radius_ratio_r_over_d'], 2.35156, places=5)
        finding = bend_finding(result, 841)
        self.assertEqual(finding['status'], 'NOT_EVALUATED')
        self.assertIn('不在当前标准配置的公称外径表内', finding['message'])


if __name__ == '__main__':
    unittest.main()
