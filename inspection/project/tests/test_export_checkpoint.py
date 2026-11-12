import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from catia_checker.catia_body_batches import persist_export_batch
from catia_checker.catia_body_batches import iter_geometrical_elements
from types import SimpleNamespace

class ExportCheckpointTests(unittest.TestCase):
    def test_null_optional_collections_are_empty(self):
        body=SimpleNamespace(Name='solid',HybridBodies=None)
        collection=SimpleNamespace(Count=1,Item=lambda index:body)
        part=SimpleNamespace(HybridBodies=None,OrderedGeometricalSets=None,Bodies=collection)
        self.assertEqual(list(iter_geometrical_elements(part)),[])
    def test_nested_sets_keep_names_and_index_identity(self):
        class Collection:
            def __init__(self,items): self.items=items;self.Count=len(items)
            def Item(self,index): return self.items[index-1]
        def group(name,children=()):
            return SimpleNamespace(Name=name,HybridShapes=Collection([SimpleNamespace(Name='same name')]),HybridBodies=Collection(children))
        part=SimpleNamespace(HybridBodies=Collection([group('set',[group('nested')]),group('set')]),Bodies=Collection([]))
        records=[record for _,record in iter_geometrical_elements(part)]
        self.assertEqual(len(records),3)
        self.assertEqual(len({r['source_body_index'] for r in records}),3)
        self.assertEqual(records[1]['source_set_path'],'Part/set/nested')
    def test_receipt_has_exact_mapping_and_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); step=root/'BATCH_0001.stp'; step.write_bytes(b'STEP test')
            records=[{'source_body_index':7,'source_body_name':'real name'}]
            receipt=persist_export_batch(root,step,records,[],{'body_count':12},{'step_export':1})
            self.assertEqual(receipt['sha256'],hashlib.sha256(b'STEP test').hexdigest())
            saved=json.loads((root/'export-checkpoint.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['completed_batches'][0]['body_mapping'],records)
            self.assertTrue(saved['reuse_requires_source_verification'])
            self.assertFalse(list(root.glob('*.pending')))

    def test_second_commit_preserves_first_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); receipts=[]
            for number in (1,2):
                step=root/f'BATCH_{number:04d}.stp'; step.write_bytes(str(number).encode())
                receipts.append(persist_export_batch(root,step,[],receipts,{},{}))
            saved=json.loads((root/'export-checkpoint.json').read_text(encoding='utf-8'))
            self.assertEqual(len(saved['completed_batches']),2)

    def test_missing_step_does_not_publish_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises(FileNotFoundError):
                persist_export_batch(root,root/'missing.stp',[],[],{},{})
            self.assertFalse((root/'export-checkpoint.json').exists())

if __name__=='__main__': unittest.main()
