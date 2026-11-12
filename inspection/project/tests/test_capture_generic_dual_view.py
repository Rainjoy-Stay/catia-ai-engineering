import importlib.util
import sys
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "tools" / "capture_generic_dual_view.py"
SPEC = importlib.util.spec_from_file_location("capture_generic_dual_view", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeShapes:
    Count = 0


class FakeObject:
    def __init__(self, name):
        self.Name = name
        self.Shapes = FakeShapes()


class FakeProperties:
    def __init__(self):
        self.show = 0
        self.color = (10, 20, 30)
        self.opacity = 200
        self.inheritance = {0: 1, 1: 0}

    def GetShow(self): return (0, self.show)
    def GetRealColor(self): return (0, *self.color)
    def GetRealOpacity(self): return (0, self.opacity)
    def GetRealInheritance(self, kind): return (0, self.inheritance[kind])
    def SetShow(self, value): self.show = value
    def SetRealColor(self, r, g, b, inheritance):
        self.color = (r, g, b); self.inheritance[0] = inheritance
    def SetRealOpacity(self, value, inheritance):
        self.opacity = value; self.inheritance[1] = inheritance


class FakeSelection:
    def __init__(self):
        self.selected = None
        self.properties = {}

    def Clear(self): self.selected = None
    def Add(self, obj):
        self.selected = obj
        self.properties.setdefault(id(obj), FakeProperties())

    @property
    def VisProperties(self): return self.properties[id(self.selected)]


def item(index, name):
    obj = FakeObject(name)
    return MODULE.Item(index, name, name, "body", obj, obj)


class GenericDualViewTests(unittest.TestCase):
    def setUp(self):
        self.items = [item(1, "Body.1"), item(2, "重复"), item(3, "重复")]

    def test_resolves_exact_unique_name(self):
        self.assertEqual(MODULE.resolve_selector("Body.1", self.items).index, 1)

    def test_resolves_explicit_index(self):
        self.assertEqual(MODULE.resolve_selector("body-index:3", self.items).name, "重复")
        self.assertEqual(MODULE.resolve_selector("2", self.items).index, 2)

    def test_rejects_duplicate_name(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            MODULE.resolve_selector("重复", self.items)

    def test_rejects_missing_name(self):
        with self.assertRaisesRegex(ValueError, "did not match"):
            MODULE.resolve_selector("不存在", self.items)

    def test_deduplicates_selectors(self):
        resolved = MODULE.resolve_many(["1", "Body.1", "3"], self.items)
        self.assertEqual([1, 3], [x.index for x in resolved])

    def test_color_parser(self):
        self.assertEqual((220, 40, 40), MODULE.parse_color("red"))
        self.assertEqual((1, 2, 3), MODULE.parse_color("1,2,3"))

    def test_out_values_accept_status_prefix(self):
        self.assertEqual((52,), MODULE._out_values((0, 52), 1, "opacity"))
        self.assertEqual((1, 2, 3), MODULE._out_values((0, 1, 2, 3), 3, "color"))

    def test_display_snapshot_and_restore(self):
        selection = FakeSelection()
        current = self.items[0]
        original = MODULE.snapshot_display(selection, current)
        MODULE.set_display(selection, current, show=1, color=(255, 0, 0), opacity=52)
        MODULE.restore_display(selection, current, original)
        restored = MODULE.snapshot_display(selection, current)
        self.assertEqual(original, restored)


if __name__ == "__main__":
    unittest.main()
