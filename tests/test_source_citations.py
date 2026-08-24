import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("gpt_researcher")
package.__path__ = [str(ROOT / "gpt_researcher")]
actions_package = types.ModuleType("gpt_researcher.actions")
actions_package.__path__ = [str(ROOT / "gpt_researcher" / "actions")]
sys.modules.setdefault("gpt_researcher", package)
sys.modules.setdefault("gpt_researcher.actions", actions_package)
markdown_dependency = types.ModuleType("markdown")
markdown_dependency.markdown = lambda value: value
sys.modules.setdefault("markdown", markdown_dependency)

markdown_processing = importlib.import_module(
    "gpt_researcher.actions.markdown_processing"
)
registry_module = importlib.import_module("gpt_researcher.sources.registry")

extract_cited_source_ids = markdown_processing.extract_cited_source_ids
render_source_context = markdown_processing.render_source_context
render_validated_references = markdown_processing.render_validated_references
SourceRecord = registry_module.SourceRecord
SourceRegistry = registry_module.SourceRegistry


def usable_record(url: str, title: str, content: str) -> SourceRecord:
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


class SourceCitationTests(unittest.TestCase):
    def make_registry(self):
        registry = SourceRegistry()
        first = registry.add_usable(
            usable_record(
                "https://example.com/policy",
                "政策文件",
                "第一条政策事实。第二条政策事实。",
            )
        )
        second = registry.add_usable(
            usable_record(
                "https://example.com/report",
                "行业报告",
                "第一项行业数据。第二项行业数据。",
            )
        )
        return registry, first, second

    def test_source_context_exposes_ids_and_content_but_not_urls(self):
        registry, first, second = self.make_registry()

        context = render_source_context(registry.usable_records())

        self.assertIn("[S1] 政策文件", context)
        self.assertIn("第一条政策事实。第二条政策事实。", context)
        self.assertIn("[S2] 行业报告", context)
        self.assertNotIn(first.canonical_url, context)
        self.assertNotIn(second.canonical_url, context)

    def test_extract_cited_source_ids_preserves_first_seen_order(self):
        report = "观点甲 [S2]。观点乙 [S1]。重复引用 [S2]。未知来源 [S99]。"

        self.assertEqual(
            extract_cited_source_ids(report),
            ["S2", "S1", "S99"],
        )

    def test_final_report_contains_only_whitelisted_links_and_references(self):
        registry, _, _ = self.make_registry()
        report = """# 报告

政策事实来自权威文件 [S1]，行业数据来自报告 [S2]。
模型擅自引用 [未知链接](https://evil.example/fake)，以及不存在的 [S99]。

## References

- [旧链接](https://stale.example/dead)
"""

        rendered = render_validated_references(report, registry)

        self.assertIn("[S1](https://example.com/policy)", rendered)
        self.assertIn("[S2](https://example.com/report)", rendered)
        self.assertIn("[政策文件](https://example.com/policy)", rendered)
        self.assertIn("[行业报告](https://example.com/report)", rendered)
        self.assertNotIn("https://evil.example/fake", rendered)
        self.assertNotIn("https://stale.example/dead", rendered)
        self.assertNotIn("S99", rendered)
        self.assertEqual(
            [record.source_id for record in registry.cited_records()],
            ["S1", "S2"],
        )


if __name__ == "__main__":
    unittest.main()
