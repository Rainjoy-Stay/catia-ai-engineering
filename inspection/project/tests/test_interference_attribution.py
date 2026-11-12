import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from catia_checker.interference_attribution import adjudicate,fingerprint

class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.package={'pair':['A','B'],'measurements':{'volume_mm3':1e-9}}
        self.proposal={'category':'DUPLICATE_EXPORT','confidence':1,'looks_duplicate':True}
    def test_ai_confidence_small_volume_and_name_never_exclude(self):
        before=copy.deepcopy(self.package)
        decision=adjudicate(self.package,self.proposal)
        self.assertFalse(decision['excluded']);self.assertEqual(before,self.package)
    def certificate(self,root):
        path=root/'proof.json';path.write_text('{}',encoding='utf-8')
        return {'pair':['A','B'],'measurement_fingerprint':fingerprint(self.package['measurements']),
            'kind':'DUPLICATE_EXPORT','verifier_method':'TRACKED_COPY_AND_EXACT_EQUIVALENCE',
            'tracked_same_original_object':True,'independent_original_objects':False,'exact_equivalence_verified':True,
            'three_layer_bindings':[{'side':s,'transition':t,'unique':True,
                'independent_features':['position','bounds','local_geometry']} for s in ('a','b') for t in ('STEP_TO_CATIA','CATIA_TO_EXPORT')],
            'evidence':[{'path':'proof.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}
    def test_unregistered_certificate_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);c=self.certificate(root)
            self.assertFalse(adjudicate(self.package,self.proposal,evidence_root=root,certificate=c)['excluded'])
    def test_verified_duplicate_revocable_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);c=self.certificate(root);trusted=[fingerprint(c)]
            args={'evidence_root':root,'certificate':c,'trusted_certificate_digests':trusted}
            self.assertTrue(adjudicate(self.package,self.proposal,**args)['excluded'])
            self.assertFalse(adjudicate(self.package,self.proposal,revoked=True,**args)['excluded'])
            (root/'proof.json').write_text('changed',encoding='utf-8')
            self.assertFalse(adjudicate(self.package,self.proposal,**args)['excluded'])
    def test_two_independent_original_objects_cannot_be_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);c=self.certificate(root);c['independent_original_objects']=True
            self.assertFalse(adjudicate(self.package,self.proposal,evidence_root=root,certificate=c,
                trusted_certificate_digests=[fingerprint(c)])['excluded'])
    def test_mapping_ambiguous_and_pair_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);c=self.certificate(root);c['pair']=['A','C'];c['three_layer_bindings'][0]['unique']=False
            self.assertFalse(adjudicate(self.package,self.proposal,evidence_root=root,certificate=c,
                trusted_certificate_digests=[fingerprint(c)])['excluded'])
    def test_source_timeout_is_not_absence_of_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);c=self.certificate(root)
            c.update(kind='ADDED_GEOMETRY',verifier_method='BOUND_SOURCE_LOCAL_SYMMETRIC_DIFFERENCE',
                source_pair_measurement={'state':'TIMEOUT','common_volume_mm3':0},
                derived_pair_measurement={'state':'COMPLETE','exact_brep':True,'input_valid':[True,True],
                    'result_valid':True,'common_volume_mm3':1,'distance_mm':0},new_geometry_contains_entire_overlap=True)
            self.assertFalse(adjudicate(self.package,self.proposal,evidence_root=root,certificate=c,
                trusted_certificate_digests=[fingerprint(c)])['excluded'])
if __name__=='__main__':unittest.main()
