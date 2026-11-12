from pathlib import Path
import tempfile
import unittest

from catia_checker.model_understanding.cache import GeometryFeatureCache, changed_signatures


class GeometryCacheTests(unittest.TestCase):
    def test_round_trip_and_changed_body_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cache.json"
            cache = GeometryFeatureCache(path)
            cache.put("SIG-A", {"candidate_type": "PIPE", "confidence": 0.9})
            cache.save()
            loaded = GeometryFeatureCache(path)
        self.assertEqual(loaded.get("SIG-A")["candidate_type"], "PIPE")
        changes = changed_signatures({"a": "1", "b": "2"}, {"b": "3", "c": "4"})
        self.assertEqual(changes, {"added": ["c"], "removed": ["a"],
                                   "changed": ["b"], "unchanged": []})


if __name__ == "__main__":
    unittest.main()
