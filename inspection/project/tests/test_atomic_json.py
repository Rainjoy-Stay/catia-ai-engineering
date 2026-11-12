import concurrent.futures,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from catia_checker.occt_session_cache import atomic_json

class AtomicJsonTests(unittest.TestCase):
    def test_transient_reader_lock_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';original=Path.replace;calls=[]
            def replace(source,target):
                calls.append(source)
                if len(calls)<3:raise PermissionError('reader lock')
                return original(source,target)
            with patch.object(Path,'replace',replace),patch('catia_checker.occt_session_cache.time.sleep'):
                atomic_json(path,{'value':'中文'})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),{'value':'中文'})
            self.assertEqual(len(calls),3)
            self.assertEqual(list(Path(directory).glob('*.pending')),[])
    def test_concurrent_writers_do_not_share_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i:atomic_json(path,{'value':i}),range(80)))
            self.assertIn(json.loads(path.read_text())['value'],range(80))
            self.assertEqual(list(Path(directory).glob('*.pending')),[])
    def test_persistent_lock_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';atomic_json(path,{'old':True})
            with patch.object(Path,'replace',side_effect=PermissionError('locked')),patch('catia_checker.occt_session_cache.time.sleep'):
                with self.assertRaises(PermissionError):atomic_json(path,{'new':True})
            self.assertEqual(json.loads(path.read_text()),{'old':True})
