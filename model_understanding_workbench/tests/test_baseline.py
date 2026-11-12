"""Behavioral ground truth for repeated instances, frames, coverage and refusal."""
from __future__ import annotations

from copy import deepcopy
import unittest
from types import SimpleNamespace as NS

from model_understanding_workbench.snapshot import (
    IDENTITY, build_snapshot, compare_snapshots, describe, find_objects, transform_point,
)
from model_understanding_workbench.catia_reader import catia_position, read_active
from model_understanding_workbench.mcp_tools import UnderstandingTools


def translation(x=0, y=0, z=0):
    value = list(IDENTITY)
    value[3], value[7], value[11] = x, y, z
    return value


def leaf(name="Bolt.1", x=0):
    return {"name": name, "part_number": "PN-TEST-BOLT", "definition_key": "fixture/bolt.CATPart",
            "children": [], "children_expected": 0, "local_transform": translation(x)}


def observation():
    return {"schema_version": "catia-understanding.observation.v1", "length_unit": "mm",
            "source": {"document": "SYNTHETIC_ONLY.CATProduct", "method": "HAND_AUTHORED_TEST_FIXTURE"},
            "definitions": {"fixture/bolt.CATPart": {"name": "bolt.CATPart", "read_status": "READ",
                            "method": "HAND_AUTHORED_TEST_FIXTURE", "bodies": [{"name": "Body.1"}]}},
            "root": {"name": "TestEngine", "children_expected": 2, "children": [
                {"name": "Module.1", "children_expected": 2,
                 "local_transform": [0., -1., 0., 100., 1., 0., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.],
                 "children": [leaf(x=10), leaf(x=20)]}, leaf(x=500)]}}


class SnapshotTests(unittest.TestCase):
    def test_one_definition_three_occurrences(self):
        snap = build_snapshot(observation())
        self.assertEqual(snap["coverage"]["occurrences_seen"], 5)
        self.assertEqual(snap["coverage"]["definitions_loaded"], 1)
        ids = {o["definition_id"] for o in snap["objects"].values() if o.get("definition_id")}
        self.assertEqual(len(ids), 1)

    def test_nested_rotation_then_translation(self):
        snap = build_snapshot(observation())
        self.assertEqual(transform_point(snap, "OCC_0_1_1", [2, 0, 0])["point"], [100, 12, 0])
        self.assertEqual(transform_point(snap, "OCC_0_2", [2, 0, 0])["point"], [502, 0, 0])

    def test_missing_transform_propagates_unknown(self):
        data = observation()
        data["root"]["children"][0].pop("local_transform")
        snap = build_snapshot(data)
        self.assertEqual(snap["coverage"]["transforms_unknown"], 3)
        self.assertIsNone(transform_point(snap, "OCC_0_1_1", [2, 0, 0])["point"])

    def test_duplicate_name_is_ambiguous(self):
        result = find_objects(build_snapshot(observation()), "Bolt.1")
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertEqual(len(result["candidates"]), 3)

    def test_explicit_id_resolves_single_object(self):
        self.assertEqual(find_objects(build_snapshot(observation()), "OCC_0_1_1")["status"], "UNIQUE")

    def test_query_not_found_is_not_invented(self):
        self.assertEqual(find_objects(build_snapshot(observation()), "FuelPump")["status"], "NOT_FOUND")

    def test_partial_child_collection_not_complete(self):
        data = observation()
        data["root"]["children_expected"] = 10
        snap = build_snapshot(data)
        self.assertEqual(snap["coverage"]["children_missing"], 8)
        self.assertFalse(snap["objects"]["OCC_0"]["children_complete"])

    def test_unknown_collection_does_not_become_empty_leaf(self):
        data = observation()
        data["root"]["children"][0]["children"] = None
        data["root"]["children"][0]["children_expected"] = None
        snap = build_snapshot(data)
        self.assertEqual(snap["coverage"]["child_collections_unknown"], 1)

    def test_snapshot_does_not_claim_semantic_or_topology_knowledge(self):
        snap = build_snapshot(observation())
        self.assertFalse(snap["capabilities"]["engineering_semantics"])
        self.assertFalse(snap["capabilities"]["native_face_adjacency"])
        self.assertIn("engineering_role", describe(snap, "OCC_0_1_1")["unknown"])

    def test_evidence_resolves(self):
        snap = build_snapshot(observation())
        for obj in snap["objects"].values():
            for eid in obj["evidence_refs"]:
                self.assertIn(eid, snap["evidence"])
                self.assertEqual(snap["evidence"][eid]["snapshot_id"], snap["snapshot_id"])

    def test_same_content_repeats_snapshot(self):
        snap = build_snapshot(observation())
        self.assertEqual(compare_snapshots(snap, build_snapshot(observation()))["status"], "IDENTICAL")

    def test_rename_invalidates_evidence_but_does_not_move_geometry(self):
        data = observation()
        old = build_snapshot(data)
        data["root"]["children"][0]["children"][0]["name"] = "Renamed"
        new = build_snapshot(data)
        self.assertEqual(transform_point(old, "OCC_0_1_1", [0, 0, 0])["point"],
                         transform_point(new, "OCC_0_1_1", [0, 0, 0])["point"])
        self.assertFalse(compare_snapshots(old, new)["old_evidence_valid_for_after"])

    def test_only_moved_instance_changes_point(self):
        data = observation()
        old = build_snapshot(data)
        data["root"]["children"][0]["children"][0]["local_transform"] = translation(30)
        new = build_snapshot(data)
        self.assertEqual(transform_point(new, "OCC_0_1_1", [0, 0, 0])["point"], [100, 30, 0])
        self.assertEqual(transform_point(new, "OCC_0_1_2", [0, 0, 0])["point"],
                         transform_point(old, "OCC_0_1_2", [0, 0, 0])["point"])

    def test_input_is_not_modified(self):
        data = observation()
        before = deepcopy(data)
        build_snapshot(data)
        self.assertEqual(before, data)

    def test_malformed_nonfinite_scaled_and_reflected_transforms_rejected(self):
        for value in ([0]*3, [float("nan")]*16,
                      [2*x if i == 0 else x for i, x in enumerate(IDENTITY)],
                      [-x if i == 0 else x for i, x in enumerate(IDENTITY)]):
            with self.subTest(value=value):
                data = observation()
                data["root"]["children"][0]["local_transform"] = value
                with self.assertRaises(ValueError):
                    build_snapshot(data)

    def test_unknown_units_rejected(self):
        data = observation()
        data["length_unit"] = "unknown"
        with self.assertRaises(ValueError):
            build_snapshot(data)

    def test_duplicate_ordinal_rejected(self):
        data = observation()
        for child in data["root"]["children"]:
            child["collection_index"] = 1
        with self.assertRaises(ValueError):
            build_snapshot(data)

    def test_read_failures_keep_original_indices(self):
        data = observation()
        data["root"]["children"] = [leaf()]
        data["root"]["children"][0]["collection_index"] = 2
        snap = build_snapshot(data)
        self.assertIn("OCC_0_2", snap["objects"])
        self.assertEqual(snap["coverage"]["children_missing"], 1)

    def test_unavailable_definition_not_claimed_as_read(self):
        data = observation()
        data["definitions"]["fixture/bolt.CATPart"]["read_status"] = "PARTIAL"
        self.assertEqual(build_snapshot(data)["coverage"]["definitions_unavailable"], 1)


class Collection:
    def __init__(self, *values, fail_at=None):
        self.values, self.fail_at = values, fail_at

    @property
    def Count(self):
        return len(self.values)

    def Item(self, index):
        if index == self.fail_at:
            raise RuntimeError("not loaded")
        return self.values[index-1]


def fake_app():
    part_doc = NS(Name="bolt.CATPart", FullName="C:/fixtures/bolt.CATPart", Saved=True,
                  Part=NS(Bodies=Collection(NS(Name="Body.1", Shapes=Collection(NS(Name="Pad.1")))),
                          HybridBodies=Collection()))
    def product(name, children=()):
        return NS(Name=name, PartNumber="TEST", ReferenceProduct=NS(Parent=part_doc),
                  Products=Collection(*children))
    root = product("Root", [product("Bolt.1"), product("Bolt.1")])
    doc = NS(Name="Test.CATProduct", FullName="C:/fixtures/Test.CATProduct", Saved=False, Product=root)
    return NS(ActiveDocument=doc, SystemConfiguration=NS(Release="TEST_ONLY"))


class CollectorTests(unittest.TestCase):
    def test_catia_axis_columns_are_not_transposed_incorrectly(self):
        values = [0, 1, 0, -1, 0, 0, 0, 0, 1, 100, 0, 0]
        self.assertEqual(catia_position(values), observation()["root"]["children"][0]["local_transform"])

    def test_reader_deduplicates_reference_and_preserves_saved_state(self):
        app = fake_app()
        obs = read_active(app, position_reader=lambda _: translation(10))
        self.assertEqual(len(obs["definitions"]), 1)
        self.assertFalse(app.ActiveDocument.Saved)
        self.assertTrue(obs["source_state"]["active_document_unchanged"])
        self.assertFalse(obs["source_state"]["selection_used"])

    def test_unavailable_position_is_unknown(self):
        def fail(_):
            raise RuntimeError("position unavailable")
        snap = build_snapshot(read_active(fake_app(), position_reader=fail))
        self.assertEqual(snap["coverage"]["transforms_unknown"], 2)

    def test_global_budget_records_omitted_children(self):
        obs = read_active(fake_app(), position_reader=lambda _: list(IDENTITY), max_occurrences=1)
        snap = build_snapshot(obs)
        self.assertEqual(snap["coverage"]["occurrences_seen"], 1)
        self.assertEqual(snap["coverage"]["children_missing"], 2)

    def test_failed_component_read_keeps_index_and_coverage(self):
        app = fake_app()
        app.ActiveDocument.Product.Products.fail_at = 1
        snap = build_snapshot(read_active(app, position_reader=lambda _: list(IDENTITY)))
        self.assertIn("OCC_0_2", snap["objects"])
        self.assertEqual(snap["coverage"]["children_missing"], 1)

    def test_missing_collection_is_not_empty(self):
        app = fake_app()
        del app.ActiveDocument.Product.Products
        snap = build_snapshot(read_active(app, position_reader=lambda _: list(IDENTITY)))
        self.assertEqual(snap["coverage"]["child_collections_unknown"], 1)

    def test_active_part_has_explicit_root_frame(self):
        app = fake_app()
        app.ActiveDocument = app.ActiveDocument.Product.ReferenceProduct.Parent
        snap = build_snapshot(read_active(app))
        self.assertEqual(snap["coverage"]["occurrences_seen"], 1)
        self.assertEqual(snap["objects"]["OCC_0"]["world_transform"], IDENTITY)

    def test_saved_state_change_discards_capture(self):
        app = fake_app()
        def mutate(_):
            app.ActiveDocument.Saved = True
            return list(IDENTITY)
        with self.assertRaises(RuntimeError):
            read_active(app, position_reader=mutate)

    def test_non_cad_document_rejected(self):
        app = fake_app()
        app.ActiveDocument.Name = "Drawing.CATDrawing"
        with self.assertRaises(ValueError):
            read_active(app)


class StructuredToolTests(unittest.TestCase):
    def test_tools_query_only_the_requested_snapshot(self):
        tools = UnderstandingTools(capture_reader=lambda **_: observation())
        result = tools.execute("catia_understanding_capture", {})
        sid = result["snapshot_id"]
        answer = tools.execute("catia_understanding_query_snapshot", {"snapshot_id": sid, "text": "Bolt"})
        self.assertEqual(answer["status"], "AMBIGUOUS")
        self.assertEqual(answer["temporal_scope"], "CAPTURED_SNAPSHOT_NOT_LIVE_STATE")
        with self.assertRaises(ValueError):
            tools.execute("catia_understanding_query_snapshot", {"snapshot_id": "older", "text": "Bolt"})

    def test_failed_recapture_clears_previous_snapshot(self):
        tools = UnderstandingTools(capture_reader=lambda **_: observation())
        sid = tools.execute("catia_understanding_capture", {})["snapshot_id"]
        def fail(**_):
            raise RuntimeError("CATIA unavailable")
        tools.capture_reader = fail
        with self.assertRaises(RuntimeError):
            tools.execute("catia_understanding_capture", {})
        with self.assertRaises(ValueError):
            tools.execute("catia_understanding_describe_snapshot", {"snapshot_id": sid, "object_id": "OCC_0"})

    def test_excess_budget_and_extra_arguments_rejected(self):
        tools = UnderstandingTools(capture_reader=lambda **_: observation())
        for args in ({"max_items": 0}, {"max_depth": 200}, {"save": True}, {"max_items": True}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                tools.execute("catia_understanding_capture", args)

    def test_unknown_operation_rejected(self):
        with self.assertRaises(ValueError):
            UnderstandingTools().execute("catia_save", {})


if __name__ == "__main__":
    unittest.main()
