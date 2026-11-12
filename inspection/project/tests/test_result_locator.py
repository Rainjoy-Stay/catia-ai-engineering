import unittest

from catia_checker.result_locator import (location_capability, resolve_issue_bodies,
    resolve_issue_target, select_issue_bodies, select_issue_target)


class _Body:
    def __init__(self, name): self.Name = name


class _Bodies:
    def __init__(self, names): self._items = [_Body(x) for x in names]; self.Count = len(names)
    def Item(self, index): return self._items[index - 1]


class _Selection:
    def __init__(self): self.items = []
    @property
    def Count(self): return len(self.items)
    def Clear(self): self.items.clear()
    def Add(self, value): self.items.append(value)


class _Document:
    def __init__(self):
        self.Name = "sample.CATPart"
        self.Part = type("Part", (), {"Bodies": _Bodies(["A", "B", "C"])})()
        self.Selection = _Selection()


class _Product:
    def __init__(self, name, children=(), part_number=""):
        self.Name=name; self.PartNumber=part_number; self.Products=_ProductCollection(children)


class _ProductCollection:
    def __init__(self, items): self.items=list(items); self.Count=len(self.items)
    def Item(self, index): return self.items[index-1]


class _ProductDocument:
    def __init__(self, children):
        self.Name="assembly.CATProduct"; self.Product=_Product("Root",children); self.Selection=_Selection()


class ResultLocatorTests(unittest.TestCase):
    def report(self):
        return {"document": "sample.CATPart", "findings": [{
            "issue_id": "ISSUE-1", "metadata": {
                "source_body_a": {"source_body_index": 1, "source_body_name": "A"},
                "source_body_b": {"source_body_index": 3, "source_body_name": "C"},
            }}]}

    def test_resolves_and_selects_exact_indexes(self):
        resolved = resolve_issue_bodies(self.report(), "ISSUE-1")
        result = select_issue_bodies(_Document(), resolved)
        self.assertEqual(result["selected_count"], 2)
        self.assertEqual([x["index"] for x in result["selected_bodies"]], [1, 3])
        self.assertFalse(result["source_modified"])

    def test_rejects_document_mismatch(self):
        resolved = resolve_issue_bodies(self.report(), "ISSUE-1")
        resolved["document"] = "other.CATPart"
        with self.assertRaisesRegex(ValueError, "report belongs"):
            select_issue_bodies(_Document(), resolved)

    def test_rejects_body_name_mismatch(self):
        report = self.report()
        report["findings"][0]["metadata"]["source_body_a"]["source_body_name"] = "Wrong"
        with self.assertRaisesRegex(ValueError, "name mismatch"):
            select_issue_bodies(_Document(), resolve_issue_bodies(report, "ISSUE-1"))

    def test_selects_unique_dmu_components_recursively(self):
        report={"document":"assembly.CATProduct","findings":[{"issue_id":"DMU-1","rule_id":"DMU.CLASH","object_a":"A.1","object_b":"B.1"}]}
        nested=_Product("Group.1",[_Product("B.1",part_number="B")])
        document=_ProductDocument([_Product("A.1",part_number="A"),nested])
        result=select_issue_target(document,resolve_issue_target(report,"DMU-1"))
        self.assertEqual(result["selected_count"],2)
        self.assertEqual(result["location_kind"],"CATPRODUCT_COMPONENT")

    def test_rejects_ambiguous_component_names(self):
        report={"document":"assembly.CATProduct","findings":[{"issue_id":"DMU-1","rule_id":"DMU.CLASH","object_a":"A.1"}]}
        document=_ProductDocument([_Product("A.1"),_Product("A.1")])
        with self.assertRaisesRegex(ValueError,"ambiguous"):
            select_issue_target(document,resolve_issue_target(report,"DMU-1"))

    def test_face_without_mapping_is_explicitly_unavailable(self):
        finding={"issue_id":"FACE-1","rule_id":"GEOMETRY.SURFACE","object_a":"FACE_1"}
        self.assertEqual(location_capability(finding)["kind"],"UNAVAILABLE")

    def test_opening_face_locates_verified_host_body_context(self):
        report={"document":"sample.CATPart","findings":[{"issue_id":"OPEN-1",
            "rule_id":"GEOMETRY.OPENING_INTERFACE","metadata":{"opening_interface":{
                "source_locators":{"opening":{"source_body_index":2,"source_body_name":"B",
                    "face_id":"FACE_9","face_centroid_mm":[1,2,3]},"nozzle":None}}}}]}
        resolved=resolve_issue_target(report,"OPEN-1")
        self.assertEqual(resolved["kind"],"CATPART_BODY_CONTEXT")
        result=select_issue_target(_Document(),resolved)
        self.assertEqual(result["selected_bodies"][0]["index"],2)
        self.assertEqual(result["precision"],"BODY_CONTEXT_ONLY")


if __name__ == "__main__":
    unittest.main()
