import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_outline_module():
    module_path = ROOT / "gpt_researcher" / "skills" / "outline_execution.py"
    if not module_path.exists():
        raise AssertionError("outline execution helpers are not implemented")

    spec = importlib.util.spec_from_file_location("outline_execution", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OutlineExecutionTests(unittest.TestCase):
    def test_research_questions_preserve_confirmed_order(self):
        module = _load_outline_module()
        outline = [
            {"id": "section-1", "title": "行业现状", "description": "市场规模与格局"},
            {"id": "section-2", "title": "核心挑战", "description": "风险与限制"},
            {"id": "section-3", "title": "未来趋势", "description": "未来三年变化"},
        ]

        self.assertEqual(
            module.outline_to_research_questions(outline),
            [
                "行业现状：市场规模与格局",
                "核心挑战：风险与限制",
                "未来趋势：未来三年变化",
            ],
        )

    def test_report_instruction_requires_exact_section_order(self):
        module = _load_outline_module()
        outline = [
            {"id": "section-1", "title": "行业现状", "description": "市场规模与格局"},
            {"id": "section-2", "title": "未来趋势", "description": "未来三年变化"},
        ]

        instruction = module.format_outline_report_instruction(outline)

        self.assertIn("confirmed by the user", instruction)
        self.assertIn("1. 行业现状：市场规模与格局", instruction)
        self.assertIn("2. 未来趋势：未来三年变化", instruction)
        self.assertLess(instruction.index("行业现状"), instruction.index("未来趋势"))


if __name__ == "__main__":
    unittest.main()
