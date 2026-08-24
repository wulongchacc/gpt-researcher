import importlib
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]


def _load_report_generator():
    package = types.ModuleType("gpt_researcher")
    package.__path__ = [str(ROOT / "gpt_researcher")]
    skills_package = types.ModuleType("gpt_researcher.skills")
    skills_package.__path__ = [str(ROOT / "gpt_researcher" / "skills")]
    utils_package = types.ModuleType("gpt_researcher.utils")
    utils_package.__path__ = [str(ROOT / "gpt_researcher" / "utils")]

    actions_module = types.ModuleType("gpt_researcher.actions")
    actions_module.generate_draft_section_titles = AsyncMock()
    actions_module.generate_report = AsyncMock()
    actions_module.stream_output = AsyncMock()
    actions_module.write_conclusion = AsyncMock()
    actions_module.write_report_introduction = AsyncMock()

    llm_module = types.ModuleType("gpt_researcher.utils.llm")
    llm_module.construct_subtopics = AsyncMock()
    outline_module = types.ModuleType("gpt_researcher.skills.outline_execution")
    outline_module.format_outline_report_instruction = lambda outline: ""

    module_name = "gpt_researcher.skills.writer"
    module_path = ROOT / "gpt_researcher" / "skills" / "writer.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    with patch.dict(
        sys.modules,
        {
            "gpt_researcher": package,
            "gpt_researcher.skills": skills_package,
            "gpt_researcher.actions": actions_module,
            "gpt_researcher.utils": utils_package,
            "gpt_researcher.utils.llm": llm_module,
            "gpt_researcher.skills.outline_execution": outline_module,
            module_name: module,
        },
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module.ReportGenerator, actions_module.generate_report


root_package = types.ModuleType("gpt_researcher")
root_package.__path__ = [str(ROOT / "gpt_researcher")]
sys.modules.setdefault("gpt_researcher", root_package)
actions_package = types.ModuleType("gpt_researcher.actions")
actions_package.__path__ = [str(ROOT / "gpt_researcher" / "actions")]
sys.modules.setdefault("gpt_researcher.actions", actions_package)
markdown_dependency = types.ModuleType("markdown")
markdown_dependency.markdown = lambda value: value
sys.modules.setdefault("markdown", markdown_dependency)
importlib.import_module("gpt_researcher.actions.markdown_processing")
registry_module = importlib.import_module("gpt_researcher.sources.registry")
validator_module = importlib.import_module("gpt_researcher.sources.validator")
SourceRecord = registry_module.SourceRecord
SourceRegistry = registry_module.SourceRegistry
SourceValidationResult = validator_module.SourceValidationResult
ReportGenerator, generate_report = _load_report_generator()


def source_record(url: str, title: str = "可靠来源") -> SourceRecord:
    content = "第一句可靠事实。第二句可靠事实。" + "资料" * 100
    return SourceRecord(
        source_id="",
        original_url=url,
        canonical_url=url,
        title=title,
        clean_content=content,
        http_status=200,
        content_type="text/html",
        content_chars=len(content),
        sentence_count=2,
        checked_at="2026-08-21T00:00:00+00:00",
        is_usable=True,
        failure_reason="ok",
    )


class FakeSourceValidator:
    def __init__(self, results_by_url):
        self.results_by_url = results_by_url
        self.validated_urls = []

    async def validate_many(self, urls):
        self.validated_urls = list(urls)
        return [self.results_by_url[url] for url in self.validated_urls]


def validation(url: str, *, valid: bool, status_code: int = 200):
    return SourceValidationResult(
        original_url=url,
        final_url=url,
        status_code=status_code,
        is_valid=valid,
        status="valid" if valid else "invalid",
        failure_reason="ok" if valid else f"http_{status_code}",
        attempts=1,
    )


class FakeResearcher:
    def __init__(self, model_profile):
        self.query = "测试问题"
        self.cfg = SimpleNamespace(agent_role=None)
        self.role = "研究员"
        self.report_type = "research_report"
        self.report_source = "web"
        self.tone = None
        self.websocket = None
        self.headers = {}
        self.kwargs = {}
        self.context = ["旧上下文 https://untrusted.example/raw"]
        self.model_profile = model_profile
        self.outline = []
        self.verbose = False
        self.source_registry = SourceRegistry()
        first_url = "https://example.com/source"
        second_url = "https://example.com/evidence"
        self.source_registry.add_usable(source_record(first_url, "可靠来源"))
        self.source_registry.add_usable(source_record(second_url, "补充证据"))
        self.source_validator = FakeSourceValidator(
            {
                first_url: validation(first_url, valid=True),
                second_url: validation(second_url, valid=True),
            }
        )

    def get_research_images(self):
        return []

    def add_costs(self, *args, **kwargs):
        return None


class ReportSourceWhitelistTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        generate_report.reset_mock()

    async def test_simple_report_uses_id_only_context_and_whitelisted_output(self):
        researcher = FakeResearcher("simple")
        generate_report.return_value = (
            "# 报告\n\n"
            + ("这是经过来源支持的研究正文。" * 20)
            + "可靠结论 [S1]，补充结论 [S2]。"
            "[伪造链接](https://evil.example/fake)"
        )

        report = await ReportGenerator(researcher).write_report()

        call = generate_report.await_args.kwargs
        self.assertIn("[S1] 可靠来源", call["context"])
        self.assertNotIn("https://example.com/source", call["context"])
        self.assertNotIn("https://untrusted.example/raw", call["context"])
        self.assertIn("S1", call["citation_instruction"])
        self.assertIn("[S1](https://example.com/source)", report)
        self.assertIn("[S2](https://example.com/evidence)", report)
        self.assertNotIn("https://evil.example/fake", report)
        self.assertIn("## References", report)
        self.assertEqual(
            researcher.source_validator.validated_urls,
            ["https://example.com/source", "https://example.com/evidence"],
        )

    async def test_simple_report_abstains_when_online_check_keeps_fewer_than_two_sources(self):
        researcher = FakeResearcher("simple")
        second_url = "https://example.com/evidence"
        researcher.source_validator.results_by_url[second_url] = validation(
            second_url,
            valid=False,
            status_code=404,
        )
        generate_report.return_value = (
            "# 报告\n\n"
            + ("这是经过来源支持的研究正文。" * 20)
            + "可靠结论 [S1]，失效结论 [S2]。"
        )

        report = await ReportGenerator(researcher).write_report()

        self.assertIn("可靠来源不足", report)
        self.assertIn("至少需要 2 条", report)
        self.assertNotIn(second_url, report)

    async def test_simple_report_abstains_when_body_is_shorter_than_200_chars(self):
        researcher = FakeResearcher("simple")
        generate_report.return_value = "# 短报告\n\n结论 [S1]，补充 [S2]。"

        report = await ReportGenerator(researcher).write_report()

        self.assertIn("正文长度不足", report)
        self.assertIn("至少需要 200 字", report)

    async def test_deep_report_keeps_existing_context_and_output_behavior(self):
        researcher = FakeResearcher("deep")
        model_output = "原有行为 [链接](https://unmodified.example/source)"
        generate_report.return_value = model_output

        report = await ReportGenerator(researcher).write_report()

        call = generate_report.await_args.kwargs
        self.assertEqual(call["context"], researcher.context)
        self.assertEqual(call["citation_instruction"], "")
        self.assertEqual(report, model_output)


if __name__ == "__main__":
    unittest.main()
