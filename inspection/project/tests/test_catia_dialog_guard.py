import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[2] / "scripts" / "catia_dialog_guard.py"
SPEC = importlib.util.spec_from_file_location("catia_dialog_guard", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CatiaDialogGuardTests(unittest.TestCase):
    def test_exact_duplicate_identifier_prompt_is_safe(self):
        result = MODULE.classify_dialog("Open", "A document with the same identifier cannot be loaded")
        self.assertEqual("CLICK", result["action"])

    def test_save_and_unknown_prompts_are_blocked_by_default(self):
        self.assertEqual("BLOCK", MODULE.classify_dialog("CATIA", "Do you want to save changes?")["action"])
        prompt = "activate other documents to complete the save operation and continue"
        self.assertEqual("BLOCK", MODULE.classify_dialog("Save As", prompt)["action"])

    def test_save_as_reference_prompt_requires_explicit_scope(self):
        prompt = "activate other documents to complete the save operation and continue"
        self.assertEqual("CLICK", MODULE.classify_dialog("Save As", prompt, True)["action"])

    def test_neutral_translation_completion_is_safe(self):
        prompt = "完成转换\nC:\\Temp\\CATReport\\sample.rpt"
        result = MODULE.classify_dialog("超级输入消息", prompt)
        self.assertEqual("CLICK", result["action"])
        self.assertEqual("NEUTRAL_TRANSLATION_COMPLETED", result["rule"])


if __name__ == "__main__":
    unittest.main()
