import json
import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from catia_checker.occt_session_cache import load_batch, identity, preview_valid, mark_preview, ResidentControl
from catia_checker.occt_brep import OCCTBRepModel
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

class SessionCacheTests(unittest.TestCase):
    def build(self,root):
        source=root/'model.stp';source.write_bytes(b'fake source for cache unit test')
        model=OCCTBRepModel()
        model.register_shape('ROOT',BRepPrimAPI_MakeBox(1,1,1).Shape())
        record=model.register_shape('SOLID',BRepPrimAPI_MakeBox(2,2,2).Shape())
        manifest={'root_shape_id':'ROOT','shapes':[{'shape_id':'ROOT'},record]}
        def transfer(*args,**kwargs):
            model.register_shape('ROOT',BRepPrimAPI_MakeBox(1,1,1).Shape())
            model.register_shape('SOLID',BRepPrimAPI_MakeBox(2,2,2).Shape())
            return manifest
        model.load_step=Mock(side_effect=transfer)
        load_batch(model,source,root/'cache')
        return source
    def test_brep_hit_does_not_transfer_step(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.build(root);model=OCCTBRepModel()
            model.load_step=Mock(side_effect=AssertionError('Unexpected STEP reload'))
            cached=load_batch(model,source,root/'cache')
            self.assertEqual(cached['shapes'][1]['shape_id'],'SOLID')
            self.assertAlmostEqual(model.describe('SOLID')['volume_mm3'],8)
    def test_source_content_change_invalidates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.build(root);before=identity([source])
            source.write_bytes(b'changed source')
            self.assertNotEqual(identity([source]),before)
    def test_corrupt_brep_rebuilds_only_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.build(root)
            next((root/'cache').rglob('*.brep')).write_bytes(b'corrupt')
            model=OCCTBRepModel();model.register_shape('S',BRepPrimAPI_MakeBox(1,1,1).Shape())
            def transfer(*args,**kwargs):
                model.register_shape('S',BRepPrimAPI_MakeBox(1,1,1).Shape())
                return {'root_shape_id':'ROOT','shapes':[{'shape_id':'S'}]}
            model.load_step=Mock(side_effect=transfer)
            load_batch(model,source,root/'cache');model.load_step.assert_called_once()
    def test_mesh_hash_and_model_identity_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'preview.json').write_text('{}');mark_preview(root,'model1')
            self.assertTrue(preview_valid(root,'model1'));self.assertFalse(preview_valid(root,'model2'))
            (root/'preview.json').write_text('corrupt');self.assertFalse(preview_valid(root,'model1'))
    def test_resident_pause_saves_and_keeps_same_pid(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);marker=root/'pause-request.json';marker.write_text('{}')
            (root/'resume-settings.json').write_text(json.dumps({'workers':1,'budget_minutes':20}))
            events=[];save=Mock();verify=Mock(return_value=True)
            control=ResidentControl(root,events.append,verify,sleep=lambda seconds:marker.unlink())
            workers,budget=control.hold(2,save)
            self.assertEqual((workers,budget),(1,20));save.assert_called_once_with(force=True)
            self.assertEqual([e['stage'] for e in events],['PAUSED','RESIDENT_RESUMED'])
            self.assertEqual(json.loads(control.state.read_text())['status'],'RUNNING')

    def test_real_engine_pause_resize_and_cold_cache_resume(self):
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCP.gp import gp_Pnt
        from catia_checker.large_single_part import inspect_large_single_part_batches_isolated
        from catia_checker.occt_session_cache import atomic_json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);paths=[]
            for index,x in enumerate((0,1)):
                path=root/f'box{index}.stp';writer=STEPControl_Writer()
                writer.Transfer(BRepPrimAPI_MakeBox(gp_Pnt(x,0,0),2,2,2).Shape(),STEPControl_AsIs)
                writer.Write(str(path));paths.append(path)
            marker=root/'pause-request.json';marker.write_text('{}')
            events=[]
            def progress(event):
                events.append(event)
                if event.get('stage')=='PAUSED':
                    state=json.loads((root/'resident-state.json').read_text())
                    self.assertEqual(state['pid'],os.getpid())
                    self.assertTrue((root/'checkpoint.json').exists())
                    atomic_json(root/'resume-settings.json',{'workers':1,'budget_minutes':1})
                    marker.unlink()
            rules={'large_single_part':{'max_pair_workers':2,'persistent_pair_workers':True}}
            with patch.dict(os.environ,{'CATIA_MONITOR_DIRECTORY':str(root),'CATIA_OCCT_KEEP_RESIDENT':'1'}):
                first=inspect_large_single_part_batches_isolated(paths,rules=rules,progress=progress,
                    checkpoint_path=root/'checkpoint.json',pair_timeout_seconds=15)
                self.assertEqual(first['max_pair_workers'],1)
                self.assertEqual(len(first['analysis']['errors']),0)
                self.assertIn('RESIDENT_RESUMED',[e['stage'] for e in events])
                mesh_mtime=(root/'preview.json').stat().st_mtime_ns;events.clear()
                with patch.object(OCCTBRepModel,'load_step',side_effect=AssertionError('STEP must not reload')):
                    second=inspect_large_single_part_batches_isolated(paths,rules=rules,progress=events.append,
                        checkpoint_path=root/'checkpoint.json',pair_timeout_seconds=15)
                self.assertEqual(second['resumed_pair_count'],1)
                self.assertEqual((root/'preview.json').stat().st_mtime_ns,mesh_mtime)
                self.assertEqual(sum(e['stage']=='OCCT_BREP_CACHE_HIT' for e in events),2)
                self.assertIn('PREVIEW_CACHE_HIT',[e['stage'] for e in events])
