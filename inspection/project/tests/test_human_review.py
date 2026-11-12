import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from human_review import update_label_file

def fixture_file(tmp_path):
    path=tmp_path/'labels.json'
    value={'training_performed':False,'rules_promoted':False,'cases':[{'case_id':'L01','pair':['a','b'],'evidence_fingerprint':'e1','evidence_snapshot':{'volume':12},'human_label':None,'human_reason':None}]}
    path.write_text(json.dumps(value),encoding='utf-8')
    return path,value

class HumanReviewTests(unittest.TestCase):
    def test_save_and_revoke_preserve_measurements_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path,original=fixture_file(Path(folder))
            update_label_file(path,{'case_id':'L01','label':'PASS','reason':'Human judgement','evidence_fingerprint':'e1','revision':0})
            update_label_file(path,{'case_id':'L01','label':None,'reason':'Withdraw','evidence_fingerprint':'e1','revision':1})
            saved=json.loads(path.read_text(encoding='utf-8'));case=saved['cases'][0]
            self.assertEqual(case['evidence_snapshot'],original['cases'][0]['evidence_snapshot'])
            self.assertEqual(case['pair'],['a','b']);self.assertIsNone(case['human_label'])
            self.assertEqual(case['label_revision'],2);self.assertEqual(len(case['label_history']),2)
            self.assertFalse(saved['training_performed']);self.assertFalse(saved['rules_promoted'])

    def test_stale_or_invalid_requests_do_not_write(self):
        for patch in [{'revision':9},{'evidence_fingerprint':'wrong'},{'label':'AUTO_PASS'},{'case_id':'absent'}]:
            with self.subTest(patch=patch),tempfile.TemporaryDirectory() as folder:
                path,_=fixture_file(Path(folder));before=path.read_bytes()
                options={'case_id':'L01','label':'PASS','reason':'x','evidence_fingerprint':'e1','revision':0};options.update(patch)
                with self.assertRaises(ValueError):update_label_file(path,options)
                self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
