import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('scope_derivative', ROOT/'vendor/catia-v5-mcp-server/catia_mcp/tools/scope_derivative.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ScopeSafetyTests(unittest.TestCase):
    def test_wrong_document_rejected_before_copy(self):
        conn=Mock(); conn.active_document.Name='Other.CATPart'
        with self.assertRaises(ValueError):
            MODULE.export_scope_derivative(conn,'Source.CATPart',['Failed'],'trial.stp','audit.json')
        conn.app.Documents.Add.assert_not_called()

    def test_existing_export_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            conn=Mock(); conn.active_document.Name='Source.CATPart'
            output=Path(folder)/'trial.stp'; output.write_text('original')
            with self.assertRaises(ValueError):
                MODULE.export_scope_derivative(conn,'Source.CATPart',['Failed'],str(output),str(Path(folder)/'audit.json'))
            self.assertEqual(output.read_text(),'original')
            conn.app.Documents.Add.assert_not_called()

    def test_exact_exclusions_must_resolve_uniquely(self):
        with tempfile.TemporaryDirectory() as folder:
            conn=Mock(); conn.active_document.Name='Source.CATPart'
            conn.active_document.Part.Bodies.Count=0
            conn.active_document.Part.HybridBodies.Count=0
            with self.assertRaises(ValueError):
                MODULE.export_scope_derivative(conn,'Source.CATPart',['Absent'],str(Path(folder)/'trial.stp'),str(Path(folder)/'audit.json'))
            conn.app.Documents.Add.assert_not_called()


if __name__=='__main__': unittest.main()
