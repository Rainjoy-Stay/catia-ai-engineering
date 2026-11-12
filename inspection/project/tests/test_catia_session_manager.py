import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[2] / "scripts" / "catia_session_manager.py"
SPEC = importlib.util.spec_from_file_location("catia_session_manager", PATH)
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)


class Document:
    def __init__(self, name): self.Name, self.closed, self.activated = name, False, False
    def Close(self): self.closed = True
    def Activate(self): self.activated = True


class CATIASessionManagerTests(unittest.TestCase):
    @patch.object(MODULE.win32gui, "SetWindowPlacement")
    @patch.object(MODULE.win32gui, "GetWindowPlacement", return_value=(0, 1, (0, 0), (0, 0), (1, 2, 3, 4)))
    @patch.object(MODULE, "find_visible_catia_window", return_value=100)
    def test_restore_closes_only_registered_temporary_document(self, _, __, set_placement):
        original, temporary, unrelated = Document("Original"), Document("Temporary"), Document("Unrelated")
        manager = MODULE.CATIASessionManager(SimpleNamespace(ActiveDocument=original))
        manager.register_temporary_document(temporary); manager.restore(); manager.restore()
        self.assertTrue(temporary.closed); self.assertFalse(unrelated.closed)
        self.assertTrue(original.activated); set_placement.assert_called_once()


if __name__ == "__main__": unittest.main()
