import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("gpt_researcher")
package.__path__ = [str(ROOT / "gpt_researcher")]
sys.modules.setdefault("gpt_researcher", package)

registry_module = importlib.import_module("gpt_researcher.sources.registry")
SourceRecord = registry_module.SourceRecord
SourceRegistry = registry_module.SourceRegistry


def usable_record(url: str, title: str = "来源") -> SourceRecord:
    return SourceRecord(
        source_id="",
        original_url=url,
        canonical_url=url,
        title=title,
        clean_content="甲" * 200 + "。乙。",
        http_status=200,
        content_type="text/html",
        content_chars=203,
        sentence_count=2,
        checked_at="2026-08-21T00:00:00+00:00",
        is_usable=True,
        failure_reason="ok",
    )


class SourceRegistryTests(unittest.TestCase):
    def test_separates_candidates_usable_and_cited_sources(self):
        registry = SourceRegistry()

        registry.record_candidate("https://Example.com/a?utm_source=test#part")
        stored = registry.add_usable(usable_record("https://example.com/a"))
        registry.mark_cited(stored.source_id)

        self.assertEqual(registry.candidate_urls, ["https://example.com/a"])
        self.assertEqual(registry.usable_urls(), ["https://example.com/a"])
        self.assertEqual(
            [item.source_id for item in registry.cited_records()],
            ["S1"],
        )

    def test_deduplicates_canonical_urls_and_keeps_stable_source_ids(self):
        registry = SourceRegistry()

        first = registry.add_usable(usable_record("https://example.com/a#part"))
        second = registry.add_usable(usable_record("https://example.com/a"))

        self.assertEqual(first.source_id, "S1")
        self.assertEqual(second.source_id, "S1")
        self.assertEqual(len(registry.usable_records()), 1)

    def test_rejects_unusable_records_from_usable_collection(self):
        registry = SourceRegistry()
        rejected = SourceRecord(
            source_id="",
            original_url="https://example.com/dead",
            canonical_url="https://example.com/dead",
            title="无效来源",
            clean_content="",
            http_status=404,
            content_type="text/html",
            content_chars=0,
            sentence_count=0,
            checked_at="2026-08-21T00:00:00+00:00",
            is_usable=False,
            failure_reason="http_404",
        )

        with self.assertRaises(ValueError):
            registry.add_usable(rejected)

        self.assertEqual(registry.usable_records(), [])


if __name__ == "__main__":
    unittest.main()
