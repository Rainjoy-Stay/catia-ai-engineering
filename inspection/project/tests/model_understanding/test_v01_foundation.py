import json
import unittest

from catia_checker.model_understanding import SemanticLevel
from catia_checker.model_understanding.adapters import CATIAManifestAdapter
from catia_checker.model_understanding.semantic_level import evaluate_semantic_level
from catia_checker.model_understanding.features import normalize_basic_features, summarize_surfaces


def manifest(*, features=0, sketches=0, parameters=0, children=None):
    part_key = "C:/sample.CATPart"
    return {
        "active_document": "sample.CATProduct" if children else "sample.CATPart",
        "document_type": "CATProduct" if children else "CATPart",
        "assembly": {"name": "Root", "part_key": None if children else part_key,
                     "children": children or []},
        "parts": {part_key: {
            "document": "sample.CATPart",
            "bodies": [{"name": "PartBody", "shapes": [{}] * features, "sketches": [{}] * sketches}],
            "counts": {"bodies": 1, "features": features, "sketches": sketches,
                       "parameters": parameters, "relations": 0},
        }},
        "summary": {"unique_parts": 1, "total_bodies": 1, "total_features": features,
                    "total_sketches": sketches, "total_parameters": parameters},
    }


class V01FoundationTests(unittest.TestCase):
    def test_extension_is_not_used_to_force_dumb_level(self):
        value = manifest(features=4, sketches=2, parameters=5, children=[
            {"name": "Pipe.1", "part_key": "C:/sample.CATPart", "children": []}
        ])
        value["active_document"] = "supplier.step"
        self.assertNotEqual(evaluate_semantic_level(value).level, SemanticLevel.DUMB)

    def test_featureless_single_part_is_dumb(self):
        result = evaluate_semantic_level(manifest())
        self.assertEqual(result.level, SemanticLevel.DUMB)
        self.assertIn("no ordered feature history was observed", result.limitations)

    def test_adapter_assigns_stable_ids_and_structure_only_limit(self):
        adapter = CATIAManifestAdapter()
        first = adapter.adapt(manifest())
        second = adapter.adapt(manifest())
        self.assertEqual(first.model_id, second.model_id)
        self.assertEqual(set(first.bodies), set(second.bodies))
        self.assertEqual(len(first.bodies), 1)
        self.assertIn("structure only", " ".join(first.limitations))
        json.dumps(first.to_dict())

    def test_optional_geometry_is_attached_without_claiming_source_semantics(self):
        result = CATIAManifestAdapter().adapt(manifest(), geometry={
            "Root/PartBody": {
                "geometry_kind": "SOLID", "closure_state": "CLOSED",
                "capabilities": ["EXACT_BREP"], "volume_mm3": 125.0,
                "surface_area_mm2": 150.0,
            }
        })
        body = next(iter(result.bodies.values()))
        self.assertEqual(body.geometry_features["volume_mm3"], 125.0)
        self.assertEqual(body.closure_state.value, "CLOSED")

    def test_body_requires_existing_component(self):
        result = CATIAManifestAdapter().adapt(manifest())
        self.assertIn(next(iter(result.bodies.values())).parent_component_id, result.components)

    def test_basic_geometry_derives_two_aspect_ratios(self):
        result = normalize_basic_features({
            "bounding_box_mm": [0, 0, 0, 100, 10, 5],
            "center_of_gravity_mm": {"x": 50, "y": 5, "z": 2.5},
            "measurement_method": "CATIA_SPA", "measurement_quality": "EXACT",
        })
        self.assertEqual(result["aspect_ratio_max_second"], 10.0)
        self.assertEqual(result["aspect_ratio_max_min"], 20.0)
        self.assertEqual(result["centroid_mm"], [50.0, 5.0, 2.5])

    def test_degenerate_bbox_does_not_invent_infinite_ratio(self):
        result = normalize_basic_features({"bounding_box_mm": [0, 0, 0, 10, 0, 0]})
        self.assertIsNone(result["aspect_ratio_max_second"])
        self.assertIsNone(result["aspect_ratio_max_min"])

    def test_surface_statistics_include_unknown_as_other(self):
        result = summarize_surfaces([
            {"surface_type": "CYLINDER", "area_mm2": 80},
            {"surface_type": "PLANE", "area_mm2": 20},
            {"surface_type": "vendor_surface"},
        ])
        self.assertEqual(result["surface_type_counts"]["OTHER"], 1)
        self.assertAlmostEqual(result["surface_type_area_ratios"]["CYLINDER"], 0.8)
        self.assertEqual(result["unmeasured_face_count"], 1)

    def test_adapter_normalizes_surface_measurements(self):
        result = CATIAManifestAdapter().adapt(manifest(), geometry={
            "Root/PartBody": {
                "geometry_kind": "SHELL", "closure_state": "OPEN",
                "capabilities": ["EXACT_BREP"],
                "bounding_box_mm": [0, 0, 0, 30, 4, 4],
                "faces": [{"surface_type": "CYLINDER", "area_mm2": 100}],
                "measurement_method": "CATIA_SPA", "measurement_quality": "EXACT",
            }
        })
        features = next(iter(result.bodies.values())).geometry_features
        self.assertEqual(features["max_dimension_mm"], 30.0)
        self.assertEqual(features["surface_statistics"]["surface_type_counts"]["CYLINDER"], 1)

    def test_part_scope_measurements_cannot_be_silently_attached_to_body(self):
        with self.assertRaisesRegex(ValueError, "measurement_scope=BODY"):
            normalize_basic_features({
                "measurement_scope": "PART", "bounding_box_mm": [0, 0, 0, 1, 1, 1]
            })

    def test_missing_measurement_is_unavailable_not_empty(self):
        body = next(iter(CATIAManifestAdapter().adapt(manifest()).bodies.values()))
        self.assertEqual(body.geometry_state.value, "UNAVAILABLE")

    def test_explicit_empty_body_state_is_preserved(self):
        result = CATIAManifestAdapter().adapt(manifest(), geometry={
            "Root/PartBody": {
                "geometry_state": "EMPTY", "geometry_kind": "UNKNOWN",
                "closure_state": "UNKNOWN", "capabilities": ["STRUCTURE_ONLY"],
                "measurement_scope": "BODY", "measurement_method": "CATIA_SPA",
                "measurement_quality": "UNAVAILABLE",
            }
        })
        self.assertEqual(next(iter(result.bodies.values())).geometry_state.value, "EMPTY")

    def test_body_batch_attaches_only_to_matching_catpart(self):
        source = manifest()
        result = CATIAManifestAdapter().adapt_body_batch(source, {
            "schema_version": "catia.body-geometry.v0.1",
            "document": "sample.CATPart", "measurement_scope": "BODY",
            "bodies": [{
                "body_name": "PartBody", "geometry_state": "AVAILABLE",
                "geometry_kind": "SOLID", "closure_state": "CLOSED",
                "capabilities": ["EXACT_BREP"], "measurement_scope": "BODY",
                "measurement_method": "CATIA_SPA_BODY_REFERENCE",
                "measurement_quality": "EXACT", "volume_mm3": 1000,
            }],
        })
        body = next(iter(result.bodies.values()))
        self.assertEqual(body.geometry_features["volume_mm3"], 1000.0)

    def test_body_batch_rejects_document_mismatch(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            CATIAManifestAdapter().adapt_body_batch(manifest(), {
                "schema_version": "catia.body-geometry.v0.1",
                "document": "other.CATPart", "measurement_scope": "BODY", "bodies": [],
            })


if __name__ == "__main__":
    unittest.main()
