import unittest
from catia_checker.source_provenance import trace_identity
class ProvenanceTests(unittest.TestCase):
    def data(self):
        return {'A':{'source_name':'COPY1','batch_id':'B1','geometry_kind':'SOLID','identity_source':'STEP_TRANSFER_ENTITY_SHAPE_ASSOCIATION'}},[{'batch_id':'B1','batch_body_name':'COPY1','source_kind':'BODY','mapping_method':'UNIQUE_COPIED_NAME_AND_SPA_VOLUME_AREA','target_original_name':'SRC','source_body_name':'SRC','source_body_index':1,'source_path':'Part/Body1'}]
    def test_unique_identity_not_equivalence(self):
        o,r=self.data();v=trace_identity('A',o,r);self.assertTrue(v['source_identity_traced']);self.assertFalse(v['geometry_equivalence_verified'])
    def test_duplicate_label_blocks(self):
        o,r=self.data();o['B']=dict(o['A']);self.assertFalse(trace_identity('A',o,r)['source_identity_traced'])
    def test_duplicate_receipt_blocks(self):
        o,r=self.data();r.append(dict(r[0]));self.assertFalse(trace_identity('A',o,r)['source_identity_traced'])
