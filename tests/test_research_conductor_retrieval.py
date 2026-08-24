import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]


def _load_research_conductor():
    package = types.ModuleType("gpt_researcher")
    package.__path__ = [str(ROOT / "gpt_researcher")]
    skills_package = types.ModuleType("gpt_researcher.skills")
    skills_package.__path__ = [str(ROOT / "gpt_researcher" / "skills")]
    actions_package = types.ModuleType("gpt_researcher.actions")
    actions_package.__path__ = [str(ROOT / "gpt_researcher" / "actions")]
    utils_package = types.ModuleType("gpt_researcher.utils")
    utils_package.__path__ = [str(ROOT / "gpt_researcher" / "utils")]

    agent_creator = types.ModuleType("gpt_researcher.actions.agent_creator")
    agent_creator.choose_agent = AsyncMock()
    query_processing = types.ModuleType("gpt_researcher.actions.query_processing")
    query_processing.get_search_results = AsyncMock()
    query_processing.plan_research_outline = AsyncMock()
    action_utils = types.ModuleType("gpt_researcher.actions.utils")
    action_utils.stream_output = AsyncMock()
    document_module = types.ModuleType("gpt_researcher.document")
    for name in ("DocumentLoader", "LangChainDocumentLoader", "OnlineDocumentLoader"):
        setattr(document_module, name, type(name, (), {}))

    class _EnumValue:
        def __init__(self, value):
            self.value = value

    enum_module = types.ModuleType("gpt_researcher.utils.enum")
    enum_module.ReportSource = type(
        "ReportSource",
        (),
        {
            "Web": _EnumValue("web"),
            "Local": _EnumValue("local"),
            "Hybrid": _EnumValue("hybrid"),
            "Azure": _EnumValue("azure"),
            "LangChainDocuments": _EnumValue("langchain_documents"),
            "LangChainVectorStore": _EnumValue("langchain_vectorstore"),
        },
    )
    enum_module.ReportType = type("ReportType", (), {})
    logging_module = types.ModuleType("gpt_researcher.utils.logging_config")
    logging_module.get_json_handler = lambda: None

    outline_name = "gpt_researcher.skills.outline_execution"
    outline_path = ROOT / "gpt_researcher" / "skills" / "outline_execution.py"
    outline_spec = importlib.util.spec_from_file_location(outline_name, outline_path)
    outline_module = importlib.util.module_from_spec(outline_spec)
    assert outline_spec.loader is not None
    outline_spec.loader.exec_module(outline_module)

    module_name = "gpt_researcher.skills.researcher"
    module_path = ROOT / "gpt_researcher" / "skills" / "researcher.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    with patch.dict(
        sys.modules,
        {
            "gpt_researcher": package,
            "gpt_researcher.skills": skills_package,
            "gpt_researcher.actions": actions_package,
            "gpt_researcher.actions.agent_creator": agent_creator,
            "gpt_researcher.actions.query_processing": query_processing,
            "gpt_researcher.actions.utils": action_utils,
            "gpt_researcher.document": document_module,
            "gpt_researcher.utils": utils_package,
            "gpt_researcher.utils.enum": enum_module,
            "gpt_researcher.utils.logging_config": logging_module,
            outline_name: outline_module,
            module_name: module,
        },
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module.ResearchConductor


ResearchConductor = _load_research_conductor()


class FakeSnippetRetriever:
    def __init__(self, query, query_domains=None):
        self.query = query
        self.query_domains = query_domains or []

    def search(self, max_results=10):
        return [
            {
                "href": "https://example.com/one",
                "body": "A" * 180,
            },
            {
                "href": "https://example.com/two",
                "body": "B" * 220,
            },
        ]


class FakeFullContentRetriever:
    def __init__(self, query, query_domains=None):
        self.query = query
        self.query_domains = query_domains or []

    def search(self, max_results=10):
        return [
            {
                "href": "https://example.com/full",
                "body": "short summary",
                "raw_content": "C" * 500,
            }
        ]


class FakeSourceRegistry:
    def __init__(self):
        self.candidate_urls = []
        self._usable = []

    def record_candidate(self, url):
        canonical_url = url.split("?utm_", 1)[0]
        if canonical_url not in self.candidate_urls:
            self.candidate_urls.append(canonical_url)
        return canonical_url

    def add_usable(self, record):
        from dataclasses import replace

        for existing in self._usable:
            if existing.canonical_url == record.canonical_url:
                return existing
        stored = replace(record, source_id=f"S{len(self._usable) + 1}")
        self._usable.append(stored)
        return stored

    def usable_urls(self):
        return [record.canonical_url for record in self._usable]


class ResearchConductorRetrievalTests(unittest.IsolatedAsyncioTestCase):
    def make_researcher(self, retriever_class):
        class FakeResearcher:
            def __init__(self):
                self.retrievers = [retriever_class]
                self.cfg = SimpleNamespace(
                    max_search_results_per_query=5,
                    min_source_content_chars=200,
                    min_source_sentences=2,
                )
                self.verbose = False
                self.websocket = None
                self.visited_urls = set()
                self.research_sources = []
                self.source_registry = FakeSourceRegistry()
                self.scraper_manager = SimpleNamespace(
                    browse_urls=AsyncMock(return_value=[])
                )
                self.vector_store = None

            def add_research_sources(self, sources):
                self.research_sources.extend(sources)

        return FakeResearcher()

    async def test_snippet_only_results_are_sent_to_scraper(self):
        researcher = self.make_researcher(FakeSnippetRetriever)
        conductor = ResearchConductor(researcher)

        urls, prefetched = await conductor._search_relevant_source_urls("rust async runtimes")

        self.assertCountEqual(
            urls,
            ["https://example.com/one", "https://example.com/two"],
        )
        self.assertEqual(prefetched, [])

    async def test_raw_content_results_stay_prefetched(self):
        researcher = self.make_researcher(FakeFullContentRetriever)
        conductor = ResearchConductor(researcher)

        urls, prefetched = await conductor._search_relevant_source_urls("pubmed article")

        self.assertEqual(urls, [])
        self.assertEqual(
            prefetched,
            [{"url": "https://example.com/full", "raw_content": "C" * 500}],
        )

    async def test_prefetched_full_content_is_admitted_before_context(self):
        class SentenceContentRetriever:
            def __init__(self, query, query_domains=None):
                self.query = query

            def search(self, max_results=10):
                return [
                    {
                        "href": "https://example.com/full?utm_source=test",
                        "raw_content": "第一句是完整内容。第二句提供更多事实。" + "资料" * 100,
                    },
                    {
                        "href": "https://example.com/short",
                        "raw_content": "内容过短。",
                    },
                ]

        researcher = self.make_researcher(SentenceContentRetriever)
        conductor = ResearchConductor(researcher)

        scraped = await conductor._scrape_data_by_urls("可靠来源")

        self.assertEqual(len(scraped), 1)
        self.assertEqual(scraped[0]["url"], "https://example.com/full")
        self.assertEqual(scraped[0]["source_id"], "S1")
        self.assertEqual(researcher.research_sources, scraped)
        self.assertEqual(
            researcher.source_registry.candidate_urls,
            [
                "https://example.com/full",
                "https://example.com/short",
            ],
        )
        self.assertEqual(
            researcher.source_registry.usable_urls(),
            ["https://example.com/full"],
        )

    async def test_confirmed_simple_outline_drives_three_section_queries_plus_original(self):
        researcher = self.make_researcher(FakeSnippetRetriever)
        researcher.outline = [
            {"id": "section-1", "title": "应用现状", "description": "典型场景"},
            {"id": "section-2", "title": "主要风险", "description": "现实约束"},
            {"id": "section-3", "title": "未来趋势", "description": "三年展望"},
        ]
        researcher.model_profile = "simple"
        researcher.report_type = "research_report"
        conductor = ResearchConductor(researcher)
        conductor.plan_research = AsyncMock(return_value=["不应使用的自动查询"])
        conductor._process_sub_query = AsyncMock(
            side_effect=lambda query, *_: f"context:{query}"
        )

        context = await conductor._get_context_by_web_search(
            "生成式人工智能与高等教育"
        )

        executed_queries = [
            call.args[0] for call in conductor._process_sub_query.await_args_list
        ]
        self.assertEqual(
            executed_queries,
            [
                "应用现状：典型场景",
                "主要风险：现实约束",
                "未来趋势：三年展望",
                "生成式人工智能与高等教育",
            ],
        )
        conductor.plan_research.assert_not_awaited()
        self.assertIn("context:应用现状：典型场景", context)

    async def test_simple_without_outline_keeps_automatic_query_planning(self):
        researcher = self.make_researcher(FakeSnippetRetriever)
        researcher.outline = []
        researcher.model_profile = "simple"
        researcher.report_type = "research_report"
        conductor = ResearchConductor(researcher)
        conductor.plan_research = AsyncMock(return_value=["自动查询"])
        conductor._process_sub_query = AsyncMock(
            side_effect=lambda query, *_: f"context:{query}"
        )

        await conductor._get_context_by_web_search("原始问题")

        executed_queries = [
            call.args[0] for call in conductor._process_sub_query.await_args_list
        ]
        self.assertEqual(executed_queries, ["自动查询", "原始问题"])
        conductor.plan_research.assert_awaited_once()

    async def test_confirmed_simple_outline_keeps_other_context_when_one_query_fails(self):
        researcher = self.make_researcher(FakeSnippetRetriever)
        researcher.outline = [
            {"id": "section-1", "title": "应用现状", "description": "典型场景"},
            {"id": "section-2", "title": "主要风险", "description": "现实约束"},
            {"id": "section-3", "title": "未来趋势", "description": "三年展望"},
        ]
        researcher.model_profile = "simple"
        researcher.report_type = "research_report"
        conductor = ResearchConductor(researcher)

        async def process_query(query, *_):
            if query.startswith("主要风险"):
                raise RuntimeError("temporary retriever failure")
            return f"context:{query}"

        conductor._process_sub_query = AsyncMock(side_effect=process_query)

        context = await conductor._get_context_by_web_search(
            "生成式人工智能与高等教育"
        )

        self.assertIn("context:应用现状：典型场景", context)
        self.assertIn("context:未来趋势：三年展望", context)
        self.assertIn("context:生成式人工智能与高等教育", context)
        self.assertNotIn("主要风险", context)


if __name__ == "__main__":
    unittest.main()
