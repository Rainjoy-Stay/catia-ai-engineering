import importlib.util
import tempfile
import unittest
from pathlib import Path

from docx import Document


PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "full_report_module_generator", PROJECT / "tools" / "generate_check_report.py"
)
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


class FullReportModuleCoverageTests(unittest.TestCase):
    def test_full_module_fixture_renders_every_new_report_section(self):
        fixture = PROJECT / "tests" / "fixtures" / "full_report_modules.json"
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "full-report.docx"
            REPORT.build_report(fixture, output)
            document = Document(output)
            text = "\n".join(p.text for p in document.paragraphs)
            for heading in (
                "4. 检查模块覆盖",
                "5. 模型几何质量与转换可靠性",
                "5.1 几何健康问题",
                "5.2 转换可靠性信号",
                "6. 工程对象与连接关系识别",
                "6.1 逻辑组件明细",
                "6.2 工程角色候选",
                "7. 问题总览",
                "10. 问题明细",
                "11. 管路候选复核",
                "12. 审计与只读声明",
            ):
                self.assertIn(heading, text)
            table_text = "\n".join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
            for label in ("模型几何预检", "逻辑组件恢复", "工程角色识别", "接管与开孔接口判定"):
                self.assertIn(label, table_text)
            self.assertIn("外网开发验证环境 CATIA P3 V5-6R2022", table_text)
            self.assertIn("32", table_text)


if __name__ == "__main__":
    unittest.main()
