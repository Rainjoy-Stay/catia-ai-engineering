import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from monitor_data import dashboard_data,revoke_attribution

class AttributionMonitorTests(unittest.TestCase):
    def test_scope_fingerprint_and_measurements_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);fact={'distance':{'minimum_distance_mm':0},'common':{'intersection_volume_mm3':1e-9}}
            cp={'geometry_fingerprint':'fp','completed_pairs':[{'pair':['A','B'],'fact':fact}]}
            registry={'objects':{},'candidates':[['A','B']], 'catia_bodies':[{'source_body_index':1}]}
            review={'geometry_fingerprint':'fp','scope_count':1,'rows':[{'pair':['A','B'],'excluded':False,'geometry_result':'PENETRATION','attribution_result':'CAUSE_UNKNOWN'}]}
            for name,value in [('checkpoint.json',cp),('registry.json',registry),('check.json',{}),('attribution-review.json',review)]:
                (p/name).write_text(json.dumps(value),encoding='utf-8')
            before=copy.deepcopy(cp);data=dashboard_data(p,p/'checkpoint.json',p/'check.json',[])
            self.assertEqual(data['rows'][0]['fact'],fact);self.assertFalse(data['rows'][0]['attribution_review']['excluded'])
            self.assertEqual(json.loads((p/'checkpoint.json').read_text()),before)
            review['geometry_fingerprint']='other';(p/'attribution-review.json').write_text(json.dumps(review),encoding='utf-8')
            self.assertIsNone(dashboard_data(p,p/'checkpoint.json',p/'check.json',[])['rows'][0]['attribution_review'])
    def test_revoke_retains_measurement_and_certificate_history(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);value={'geometry_fingerprint':'fp','rows':[{'pair':['A','B'],'excluded':True,
                'attribution_result':'VERIFIED_CONVERSION_ARTIFACT','measurement':{'volume':2}}]}
            (p/'attribution-review.json').write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaises(ValueError):revoke_attribution(p,['A','B'],'wrong')
            with self.assertRaises(ValueError):revoke_attribution(p,['A','C'],'fp')
            self.assertTrue(revoke_attribution(p,['B','A'],'fp')['revoked'])
            after=json.loads((p/'attribution-review.json').read_text());self.assertEqual(after['rows'][0]['measurement'],{'volume':2})
            self.assertEqual(len(after['rows'][0]['revocation_history']),1);self.assertEqual(after['unresolved_count'],1)
if __name__=='__main__':unittest.main()
