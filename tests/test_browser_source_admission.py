import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]


def _load_browser_manager():
    package = types.ModuleType("gpt_researcher")
    package.__path__ = [str(ROOT / "gpt_researcher")]
    skills_package = types.ModuleType("gpt_researcher.skills")
    skills_package.__path__ = [str(ROOT / "gpt_researcher" / "skills")]

    class FakeWorkerPool:
        def __init__(self, workers, delay):
            self.workers = workers
            self.delay = delay

    workers_module = types.ModuleType("gpt_researcher.utils.workers")
    workers_module.WorkerPool = FakeWorkerPool
    action_utils = types.ModuleType("gpt_researcher.actions.utils")
    action_utils.stream_output = AsyncMock()
    web_scraping = types.ModuleType("gpt_researcher.actions.web_scraping")
    web_scraping.scrape_urls = AsyncMock()
    scraper_utils = types.ModuleType("gpt_researcher.scraper.utils")
    scraper_utils.get_image_hash = lambda url: None

    module_name = "gpt_researcher.skills.browser"
    module_path = ROOT / "gpt_researcher" / "skills" / "browser.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            "gpt_researcher": package,
            "gpt_researcher.skills": skills_package,
            "gpt_researcher.utils.workers": workers_module,
            "gpt_researcher.actions.utils": action_utils,
            "gpt_researcher.actions.web_scraping": web_scraping,
            "gpt_researcher.scraper.utils": scraper_utils,
            module_name: module,
        },
    ):
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return module


browser_module = _load_browser_manager()
BrowserManager = browser_module.BrowserManager

source_package_root = types.ModuleType("gpt_researcher")
source_package_root.__path__ = [str(ROOT / "gpt_researcher")]
sources_package = types.ModuleType("gpt_researcher.sources")
sources_package.__path__ = [str(ROOT / "gpt_researcher" / "sources")]
sys.modules["gpt_researcher"] = source_package_root
sys.modules["gpt_researcher.sources"] = sources_package
SourceRegistry = importlib.import_module(
    "gpt_researcher.sources.registry"
).SourceRegistry


class FakeResearcher:
    def __init__(self):
        self.cfg = SimpleNamespace(
            max_scraper_workers=2,
            scraper_rate_limit_delay=0,
            min_source_content_chars=200,
            min_source_sentences=2,
        )
        self.verbose = False
        self.websocket = None
        self.source_registry = SourceRegistry()
        self.research_sources = []
        self.research_images = []

    def add_research_sources(self, sources):
        self.research_sources.extend(sources)

    def add_research_images(self, images):
        self.research_images.extend(images)

    def get_research_images(self):
        return self.research_images


class BrowserSourceAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_admitted_scraper_results_enter_research_sources(self):
        researcher = FakeResearcher()
        manager = BrowserManager(researcher)
        valid_content = ("有效正文" * 50) + "。第二个完整句子。"
        scraped = [
            {
                "url": "https://example.com/valid",
                "title": "有效来源",
                "raw_content": valid_content,
                "image_urls": [],
            },
            {
                "url": "https://example.com/short",
                "title": "过短来源",
                "raw_content": "短内容。第二句。",
                "image_urls": [],
            },
            {
                "url": "https://example.com/captcha",
                "title": "验证页面",
                "raw_content": ("请输入验证码" * 40) + "。再次验证。",
                "image_urls": [],
            },
        ]

        browser_module.scrape_urls = AsyncMock(return_value=(scraped, []))
        result = await manager.browse_urls([item["url"] for item in scraped])

        self.assertEqual(
            [item["url"] for item in result],
            ["https://example.com/valid"],
        )
        self.assertEqual(
            [item["url"] for item in researcher.research_sources],
            ["https://example.com/valid"],
        )
        self.assertEqual(researcher.source_registry.usable_urls(), ["https://example.com/valid"])
        self.assertEqual(
            researcher.source_registry.candidate_urls,
            [
                "https://example.com/valid",
                "https://example.com/short",
                "https://example.com/captcha",
            ],
        )


if __name__ == "__main__":
    unittest.main()
