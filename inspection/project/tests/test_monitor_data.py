import json
import tempfile
import unittest
from pathlib import Path
from tools.monitor_data import dashboard_data


class MonitorDataTests(unittest.TestCase):
    def test_active_pairs_remove_only_matching_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            events=[{'stage':'EXACT_PAIR_PRIMARY_START','index':1,'object_a':'A','object_b':'B'},
                    {'stage':'EXACT_PAIR_PRIMARY_START','index':2,'object_a':'C','object_b':'D'},
                    {'stage':'EXACT_PAIR_PRIMARY_COMPLETE','index':1}]
            state=dashboard_data(tmp,None,None,events)
            self.assertEqual(len(state['active_pairs']),1)
            self.assertEqual(state['active_pairs'][0]['object_a'],'C')

    def test_facts_do_not_rewrite_formal_unknown_and_pending_has_no_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'registry.json').write_text(json.dumps({'candidates':[['A','B'],['C','D']]}))
            checkpoint=directory/'checkpoint.json'
            checkpoint.write_text(json.dumps({'completed_pairs':[{'pair':['A','B'],'fact':{
                'distance':{'minimum_distance_mm':0,'exact_brep':True},
                'common':{'intersection_volume_mm3':0,'exact_brep':True}}}]}))
            state=dashboard_data(directory,checkpoint,None,[])
            self.assertEqual(state['rows'][0]['formal_status'],'NOT_EVALUATED')
            self.assertIsNotNone(state['rows'][0]['fact'])
            self.assertIsNone(state['rows'][1]['fact'])
            self.assertFalse(state['screening_policy']['approved'])

    def test_partial_checkpoint_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint=Path(tmp)/'checkpoint.json';checkpoint.write_text('{')
            state=dashboard_data(tmp,checkpoint,None,[])
            self.assertEqual(state['checkpoint_count'],0)
