import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


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


def _load_outline_planner_module():
    package = types.ModuleType("gpt_researcher")
    package.__path__ = [str(ROOT / "gpt_researcher")]
    skills_package = types.ModuleType("gpt_researcher.skills")
    skills_package.__path__ = [str(ROOT / "gpt_researcher" / "skills")]
    utils_package = types.ModuleType("gpt_researcher.utils")
    utils_package.__path__ = [str(ROOT / "gpt_researcher" / "utils")]
    llm_module = types.ModuleType("gpt_researcher.utils.llm")
    llm_module.create_chat_completion = AsyncMock()

    module_name = "gpt_researcher.skills.outline"
    sys.modules.pop(module_name, None)
    with patch.dict(
        sys.modules,
        {
            "gpt_researcher": package,
            "gpt_researcher.skills": skills_package,
            "gpt_researcher.utils": utils_package,
            "gpt_researcher.utils.llm": llm_module,
        },
    ):
        module_path = ROOT / "gpt_researcher" / "skills" / "outline.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
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

    def test_simple_report_instruction_preserves_all_confirmed_chinese_headings(self):
        module = _load_outline_module()
        outline = [
            {"id": "section-1", "title": "应用现状", "description": "典型场景"},
            {"id": "section-2", "title": "主要风险", "description": "现实约束"},
            {"id": "section-3", "title": "未来趋势", "description": "三年展望"},
        ]

        instruction = module.format_outline_report_instruction(outline)

        positions = [instruction.index(section["title"]) for section in outline]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("1. 应用现状：典型场景", instruction)
        self.assertIn("2. 主要风险：现实约束", instruction)
        self.assertIn("3. 未来趋势：三年展望", instruction)

    def test_simple_search_queries_use_three_sections_plus_original_question(self):
        module = _load_outline_module()
        self.assertTrue(
            hasattr(module, "build_simple_outline_search_queries"),
            "simple outline search query helper is not implemented",
        )
        outline = [
            {"id": "section-1", "title": "应用现状", "description": "典型场景"},
            {"id": "section-2", "title": "主要风险", "description": "现实约束"},
            {"id": "section-3", "title": "未来趋势", "description": "三年展望"},
            {"id": "section-4", "title": "实施建议", "description": "落地路径"},
        ]

        self.assertEqual(
            module.build_simple_outline_search_queries(outline, "生成式人工智能与高等教育"),
            [
                "应用现状：典型场景",
                "主要风险：现实约束",
                "未来趋势：三年展望",
                "生成式人工智能与高等教育",
            ],
        )

    def test_simple_search_queries_remove_duplicates_without_reordering(self):
        module = _load_outline_module()
        self.assertTrue(
            hasattr(module, "build_simple_outline_search_queries"),
            "simple outline search query helper is not implemented",
        )
        outline = [
            {"id": "section-1", "title": "应用现状", "description": "典型场景"},
            {"id": "section-2", "title": "应用现状", "description": "典型场景"},
            {"id": "section-3", "title": "未来趋势", "description": "三年展望"},
        ]

        self.assertEqual(
            module.build_simple_outline_search_queries(outline, "  应用现状：典型场景  "),
            ["应用现状：典型场景", "未来趋势：三年展望"],
        )


class SimpleOutlinePlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_simple_planner_returns_exactly_three_sections(self):
        module = _load_outline_planner_module()
        completion = AsyncMock(
            return_value=json.dumps(
                {
                    "sections": [
                        {"title": f"章节{index}", "description": "研究范围"}
                        for index in range(1, 6)
                    ]
                },
                ensure_ascii=False,
            )
        )
        module.create_chat_completion = completion
        planner = module.OutlinePlanner(
            SimpleNamespace(
                strategic_llm_provider="dashscope",
                strategic_llm_model="qwen-plus",
                reasoning_effort=None,
                strategic_token_limit=2000,
                llm_kwargs={},
            )
        )
        planner.section_count = 3

        result = await planner.generate("研究主题", "Chinese (Simplified)")

        self.assertEqual(len(result), 3)
        prompt = completion.await_args.kwargs["messages"][1]["content"]
        self.assertIn("exactly 3 non-overlapping sections", prompt)


if __name__ == "__main__":
    unittest.main()
