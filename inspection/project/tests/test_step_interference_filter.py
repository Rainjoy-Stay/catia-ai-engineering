import unittest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Pnt
from catia_checker.occt_brep import OCCTBRepModel
from standalone.step_interference_filter import classify, provenance, filter_result


class FilterAcceptance(unittest.TestCase):
    def test_legacy_volume_label_cannot_establish_same_origin(self):
        p = provenance([{'shape_id': 'A', 'source_body_index': 1,
                         'mapping_method': 'STABLE_SOURCE_LABEL_VOLUME_VERIFIED'}], 'doc')
        self.assertIsNone(p['records']['A']['body_key'])
        self.assertEqual(p['rejected_legacy_label_solid_ids'], ['A'])
    def test_conflicting_connection_cannot_hide_crossing(self):
        result = self.evaluate(.5, non_design_overlap_confirmed=True,
                               connection_evidence={'verified': True, 'interface_id': 'end',
                                                    'overlap_within_interface': True})
        self.assertEqual(result['status'], 'NOT_EVALUATED')

    def test_replay_preserves_deferred_counts_and_raw_evidence(self):
        raw = {'issue_id': 'id', 'exact_brep': True, 'intersection_volume_mm3': 4,
               'minimum_distance_mm': 0}
        payload = {'document': 'doc', 'counts': {'FAIL': 1, 'NOT_EVALUATED': 7, 'ERROR': 2},
                   'large_single_part_analysis': {'analysis': {'findings': [raw]}},
                   'findings': [{'issue_id': 'id', 'status': 'FAIL',
                                 'metadata': {'large_single_part': True}}]}
        import copy
        before = copy.deepcopy(raw)
        filter_result(payload)
        once = copy.deepcopy(payload)
        filter_result(payload)
        self.assertEqual(payload, once)
        self.assertEqual(raw, before)
        self.assertEqual(payload['counts']['NOT_EVALUATED'], 8)
        self.assertEqual(payload['counts']['ERROR'], 2)
        self.assertEqual(payload['findings'][0]['metadata']['pre_filter_status'], 'FAIL')

    def test_step_roundtrip_records_faces_and_qualifies_batches(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from standalone.large_single_part_analysis.batching import merge_batch_manifests
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'box.step'
            writer = STEPControl_Writer()
            writer.Transfer(BRepPrimAPI_MakeBox(1, 1, 1).Shape(), STEPControl_AsIs)
            writer.Write(str(path))
            manifest = OCCTBRepModel().load_step(path, lightweight=True)
            solid = manifest['shapes'][1]
            self.assertEqual(len(solid['face_ids']), 6)
            self.assertTrue(solid['faces_complete'])
            merged = merge_batch_manifests([{'batch_id': 'B1', 'manifest': manifest}])
            self.assertTrue(all(f.startswith('B1::') for f in merged['shapes'][0]['face_ids']))

    def test_invalid_solid_and_sequence_identity_cannot_pass(self):
        fact = {'exact_brep': True, 'intersection_volume_mm3': 0, 'minimum_distance_mm': 2}
        self.assertEqual(classify(fact, {'valid': False}, {'valid': True})['status'], 'NOT_EVALUATED')
        p = provenance([{'shape_id': 'x', 'source_body_index': 1,
                         'mapping_method': 'SEQUENCE_FALLBACK'}], 'doc')
        self.assertIsNone(p['records']['x']['body_key'])

    def evaluate(self, x, *, same=False, **evidence):
        model = OCCTBRepModel()
        a = model.register_shape('A', BRepPrimAPI_MakeBox(1, 1, 1).Shape())
        b = model.register_shape('B', BRepPrimAPI_MakeBox(gp_Pnt(x, 0, 0), 1, 1, 1).Shape())
        a['body_key'], b['body_key'] = 'doc::1', 'doc::1' if same else 'doc::2'
        fact = {**model.distance('A', 'B'), **model.common_volume('A', 'B'), **evidence}
        return classify(fact, a, b)

    def test_true_crossing_not_suppressed(self):
        self.assertEqual(self.evaluate(.5, non_design_overlap_confirmed=True)['status'], 'FAIL')

    def test_overlap_without_intent_is_not_pass(self):
        self.assertEqual(self.evaluate(.5)['status'], 'NOT_EVALUATED')

    def test_same_source_large_overlap_is_not_pass(self):
        self.assertEqual(self.evaluate(.5, same=True, non_design_overlap_confirmed=True)['category'], 'SAME_SOURCE_FRAGMENTATION')

    def test_micro_overlap_is_not_pass(self):
        self.assertEqual(self.evaluate(1 - 5e-7)['status'], 'NOT_EVALUATED')

    def test_confirmed_tiny_penetration_is_not_filtered_by_volume(self):
        self.assertEqual(self.evaluate(1 - 5e-7, non_design_overlap_confirmed=True)['status'], 'FAIL')

    def test_missing_margin_witness_cannot_suppress_confirmed_crossing(self):
        self.assertEqual(self.evaluate(.5, non_design_overlap_confirmed=True,
                                      robust_interior_witness_found=False)['status'], 'FAIL')

    def test_original_overlap_is_not_called_conversion_artifact(self):
        decision = self.evaluate(1 - 5e-7, source_overlap_evidence={
            'exact_brep': True, 'entity_binding_verified': True,
            'intersection_volume_mm3': 5e-7})
        self.assertEqual(decision['category'], 'UNDETERMINED')
        self.assertEqual(decision['reason'], 'OVERLAP_REPRODUCED_IN_SOURCE_INTENT_UNCONFIRMED')

    def test_unverified_source_evidence_does_not_change_micro_classification(self):
        decision = self.evaluate(1 - 5e-7, source_overlap_evidence={
            'exact_brep': True, 'entity_binding_verified': False,
            'intersection_volume_mm3': 5e-7})
        self.assertEqual(decision['category'], 'MICRO_CONVERSION_ARTIFACT')

    def test_crossing_above_micro_threshold_retains_failure(self):
        self.assertEqual(self.evaluate(1 - 2e-6, non_design_overlap_confirmed=True)['status'], 'FAIL')

    def test_contact_requires_context(self):
        self.assertEqual(self.evaluate(1)['category'], 'CONTACT_OR_COPLANAR')

    def test_disjoint(self):
        self.assertEqual(self.evaluate(2)['status'], 'PASS')

    def test_normal_pipe_end_connection(self):
        model = OCCTBRepModel()
        def pipe(z):
            return BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(2, 4).Shape(),
                                   BRepPrimAPI_MakeCylinder(1, 4).Shape()).Shape()
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.gp import gp_Trsf, gp_Vec
        transform = gp_Trsf(); transform.SetTranslation(gp_Vec(0, 0, 4))
        a = model.register_shape('A', pipe(0))
        b = model.register_shape('B', BRepBuilderAPI_Transform(pipe(0), transform, True).Shape())
        fact = {**model.distance('A', 'B'), **model.common_volume('A', 'B'),
                'connection_evidence': {'verified': True, 'interface_id': 'CASE-END',
                                        'overlap_within_interface': True}}
        self.assertEqual(classify(fact, a, b)['category'], 'NORMAL_PIPE_CONNECTION')

    def test_invalid_and_nan_never_pass(self):
        for volume in (float('nan'), -1, float('inf')):
            self.assertEqual(classify({'exact_brep': True, 'intersection_volume_mm3': volume,
                                       'minimum_distance_mm': 0})['status'], 'NOT_EVALUATED')

    def test_provenance_does_not_guess(self):
        records = [{'shape_id': 'A', 'source_body_index': 45, 'mapping_method': 'VERIFIED'},
                   {'shape_id': 'B', 'source_body_index': 45, 'mapping_method': 'VERIFIED'},
                   {'shape_id': 'C', 'source_body_index': 45}]
        p = provenance(records, 'doc')
        self.assertEqual(p['one_to_many'], {'doc::BODY_45': ['A', 'B']})
        self.assertIsNone(p['records']['C']['body_key'])


if __name__ == '__main__':
    unittest.main()
