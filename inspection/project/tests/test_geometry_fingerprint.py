import unittest

from catia_checker.geometry_fingerprint import (geometry_fingerprint, match_geometry_records,
                                                match_geometry_records_with_labels)


def record(identity, x, volume=100.0, area=150.0, faces=6):
    return {"shape_id": identity, "body_index": identity, "volume_mm3": volume,
            "surface_area_mm2": area, "centroid_mm": [x, 0, 0],
            "bounds_mm": {"min": [x - 1, -1, -1], "max": [x + 1, 1, 1]},
            "face_count": faces}


class GeometryFingerprintTests(unittest.TestCase):
    def test_fingerprint_ignores_identity_names(self):
        first, second = record("A", 10), record("B", 10)
        self.assertEqual(geometry_fingerprint(first), geometry_fingerprint(second))

    def test_permuted_records_map_by_geometry_not_order(self):
        sources = [record("S1", 10), record("S2", 30, volume=200)]
        targets = [record(2, 30, volume=200), record(1, 10)]
        result = match_geometry_records(sources, targets)
        self.assertTrue(result["is_complete"])
        self.assertEqual({x["source_id"]: x["target_id"] for x in result["matches"]},
                         {"S1": "1", "S2": "2"})

    def test_identical_repeated_geometry_is_rejected_as_ambiguous(self):
        sources = [record("S1", 10), record("S2", 10)]
        targets = [record(1, 10), record(2, 10)]
        result = match_geometry_records(sources, targets)
        self.assertFalse(result["is_complete"])
        self.assertEqual({x["reason"] for x in result["unresolved"]},
                         {"AMBIGUOUS_REPEATED_GEOMETRY"})

    def test_single_feature_is_insufficient(self):
        sources = [{"shape_id": "S", "volume_mm3": 100}]
        targets = [{"body_index": 1, "volume_mm3": 100}]
        result = match_geometry_records(sources, targets)
        self.assertFalse(result["is_complete"])
        self.assertEqual(result["unresolved"][0]["reason"], "NO_COMPATIBLE_TARGET")

    def test_preserved_label_and_volume_alone_cannot_verify_identity(self):
        sources = [
            {"shape_id": "S1", "source_name": "BODY-B", "volume_mm3": 200},
            {"shape_id": "S2", "source_name": "BODY-A", "volume_mm3": 100},
        ]
        targets = [
            {"body_index": 1, "source_body_name": "BODY-A", "volume_mm3": 100.05},
            {"body_index": 2, "source_body_name": "BODY-B", "volume_mm3": 199.9},
        ]
        result = match_geometry_records_with_labels(sources, targets)
        self.assertFalse(result['is_complete'])
        self.assertEqual(result['matches'], [])

    def test_wrong_equal_volume_label_cannot_override_position(self):
        source = record('S', 7); source['source_name'] = 'BODY-A'
        a, b = record(1, 0), record(2, 7)
        a['source_body_name'], b['source_body_name'] = 'BODY-A', 'BODY-B'
        result = match_geometry_records_with_labels([source], [a, b])
        self.assertEqual(result['matches'][0]['target_id'], '2')
        self.assertEqual(result['rejected_labels'][0]['reason'], 'SPATIAL_MULTI_FEATURE_VERIFICATION_FAILED')

    def test_correct_label_requires_unique_spatial_geometry(self):
        source, target = record('S', 7), record(1, 7)
        source['source_name'] = target['source_body_name'] = 'BODY-A'
        result = match_geometry_records_with_labels([source], [target])
        self.assertEqual(result['matches'][0]['mapping_method'], 'STABLE_SOURCE_LABEL_SPATIAL_MULTI_FEATURE_VERIFIED')

    def test_labels_cannot_resolve_coincident_duplicate_geometry(self):
        a, b, target = record('A', 7), record('B', 7), record(1, 7)
        a['source_name'], b['source_name'], target['source_body_name'] = 'BODY-A', 'BODY-B', 'BODY-A'
        result = match_geometry_records_with_labels([a,b], [target])
        self.assertEqual(result['matches'], [])

    def test_two_sources_competing_for_one_target_are_ambiguous(self):
        result = match_geometry_records([record('S1', 7), record('S2', 7)], [record(1, 7)])
        self.assertEqual(result['matches'], [])

    def test_unverified_centroid_and_no_bounds_cannot_verify_identity(self):
        a, b = record('S', 7), record(1, 7)
        for r in (a,b):
            r.pop('bounds_mm'); r['centroid_verified'] = False
        self.assertFalse(match_geometry_records([a], [b])['is_complete'])

    def test_label_with_wrong_volume_is_rejected(self):
        result = match_geometry_records_with_labels(
            [{"shape_id": "S", "source_name": "SAME", "volume_mm3": 100}],
            [{"body_index": 1, "source_body_name": "SAME", "volume_mm3": 200}])
        self.assertFalse(result["is_complete"])
        self.assertEqual("VOLUME_VERIFICATION_FAILED", result["rejected_labels"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
