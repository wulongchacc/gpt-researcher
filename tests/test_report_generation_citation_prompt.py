import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]


def _load_report_generation():
    package = types.ModuleType("gpt_researcher")
    package.__path__ = [str(ROOT / "gpt_researcher")]
    actions_package = types.ModuleType("gpt_researcher.actions")
    actions_package.__path__ = [str(ROOT / "gpt_researcher" / "actions")]

    config_module = types.ModuleType("gpt_researcher.config.config")
    config_module.Config = object
    llm_module = types.ModuleType("gpt_researcher.utils.llm")
    llm_module.create_chat_completion = AsyncMock(return_value="报告 [S1]")
    logger_module = types.ModuleType("gpt_researcher.utils.logger")
    logger_module.get_formatted_logger = lambda: SimpleNamespace(
        error=lambda *args, **kwargs: None
    )
    prompts_module = types.ModuleType("gpt_researcher.prompts")
    prompts_module.PromptFamily = object
    prompts_module.get_prompt_by_report_type = lambda *_: (
        lambda query, context, report_source, **kwargs: f"CONTEXT: {context}"
    )
    enum_module = types.ModuleType("gpt_researcher.utils.enum")
    enum_module.Tone = object

    module_name = "gpt_researcher.actions.report_generation"
    module_path = ROOT / "gpt_researcher" / "actions" / "report_generation.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    with patch.dict(
        sys.modules,
        {
            "gpt_researcher": package,
            "gpt_researcher.actions": actions_package,
            "gpt_researcher.config.config": config_module,
            "gpt_researcher.utils.llm": llm_module,
            "gpt_researcher.utils.logger": logger_module,
            "gpt_researcher.prompts": prompts_module,
            "gpt_researcher.utils.enum": enum_module,
            module_name: module,
        },
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module, llm_module.create_chat_completion


report_generation, create_chat_completion = _load_report_generation()


class ReportGenerationCitationPromptTests(unittest.IsolatedAsyncioTestCase):
    async def test_citation_whitelist_instruction_reaches_model_message(self):
        cfg = SimpleNamespace(
            report_format="APA",
            total_words=500,
            language="Chinese (Simplified)",
            smart_llm_model="qwen-plus",
            smart_llm_provider="dashscope",
            smart_token_limit=1000,
            llm_kwargs={},
        )
        instruction = "CITATION WHITELIST: cite only [S1]."

        await report_generation.generate_report(
            query="测试问题",
            context="[S1] 可靠证据",
            agent_role_prompt="研究员",
            report_type="research_report",
            tone=None,
            report_source="web",
            websocket=None,
            cfg=cfg,
            citation_instruction=instruction,
        )

        sent_prompt = create_chat_completion.await_args.kwargs["messages"][1]["content"]
        self.assertIn(instruction, sent_prompt)


if __name__ == "__main__":
    unittest.main()
