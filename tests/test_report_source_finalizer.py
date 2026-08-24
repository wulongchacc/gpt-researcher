from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("gpt_researcher")
package.__path__ = [str(ROOT / "gpt_researcher")]
sys.modules.setdefault("gpt_researcher", package)

finalizer_module = importlib.import_module("gpt_researcher.sources.finalizer")
registry_module = importlib.import_module("gpt_researcher.sources.registry")
validator_module = importlib.import_module("gpt_researcher.sources.validator")

repair_report_sources = finalizer_module.repair_report_sources
SourceRecord = registry_module.SourceRecord
SourceRegistry = registry_module.SourceRegistry
SourceValidationResult = validator_module.SourceValidationResult


def usable_record(url: str, title: str) -> SourceRecord:
    content = "第一句可靠事实。第二句可靠事实。" + ("资料" * 100)
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
        checked_at="2026-08-24T00:00:00+00:00",
        is_usable=True,
        failure_reason="ok",
    )


def validation(
    url: str,
    *,
    valid: bool,
    final_url: str | None = None,
    status_code: int = 200,
) -> SourceValidationResult:
    return SourceValidationResult(
        original_url=url,
        final_url=final_url or url,
        status_code=status_code,
        is_valid=valid,
        status="valid" if valid else "invalid",
        failure_reason="ok" if valid else f"http_{status_code}",
        attempts=1,
    )


class ReportSourceFinalizerTests(unittest.TestCase):
    def make_registry(self):
        registry = SourceRegistry()
        first = registry.add_usable(
            usable_record("https://example.com/dead", "失效来源")
        )
        second = registry.add_usable(
            usable_record("https://example.com/stable", "稳定来源")
        )
        third = registry.add_usable(
            usable_record("https://example.com/redirect", "重定向来源")
        )
        return registry, first, second, third

    def test_removes_dead_citation_updates_redirect_and_renumbers_sources(self):
        registry, first, second, third = self.make_registry()
        report = f"""# 报告

失效结论 [{first.source_id}]({first.canonical_url})。
稳定结论 [{second.source_id}]({second.canonical_url})。
重定向结论 [{third.source_id}]({third.canonical_url})。

## References

- [失效来源]({first.canonical_url}) [{first.source_id}]
- [稳定来源]({second.canonical_url}) [{second.source_id}]
- [重定向来源]({third.canonical_url}) [{third.source_id}]
"""

        result = repair_report_sources(
            report,
            registry,
            [
                validation(first.canonical_url, valid=False, status_code=404),
                validation(second.canonical_url, valid=True),
                validation(
                    third.canonical_url,
                    valid=True,
                    final_url="https://example.com/final",
                ),
            ],
        )

        self.assertNotIn(first.canonical_url, result.report)
        self.assertNotIn("失效来源", result.report)
        self.assertIn("[S1](https://example.com/stable)", result.report)
        self.assertIn("[S2](https://example.com/final)", result.report)
        self.assertIn("[稳定来源](https://example.com/stable) [S1]", result.report)
        self.assertIn("[重定向来源](https://example.com/final) [S2]", result.report)
        self.assertEqual(result.valid_citation_count, 2)
        self.assertEqual(result.removed_link_count, 1)
        self.assertEqual(result.redirected_link_count, 1)

    def test_removes_unvalidated_external_links_but_keeps_readable_label(self):
        registry, _, second, _ = self.make_registry()
        report = (
            f"可靠结论 [{second.source_id}]({second.canonical_url})，"
            "未知来源 [相关网页](https://unknown.example/page)。"
        )

        result = repair_report_sources(
            report,
            registry,
            [validation(second.canonical_url, valid=True)],
        )

        self.assertIn("相关网页", result.report)
        self.assertNotIn("unknown.example", result.report)
        self.assertEqual(result.removed_link_count, 1)

    def test_omits_reference_section_when_no_valid_citation_remains(self):
        registry, first, _, _ = self.make_registry()
        report = f"结论 [{first.source_id}]({first.canonical_url})。"

        result = repair_report_sources(
            report,
            registry,
            [validation(first.canonical_url, valid=False, status_code=410)],
        )

        self.assertNotIn("http", result.report)
        self.assertNotIn("## References", result.report)
        self.assertEqual(result.valid_citation_count, 0)


if __name__ == "__main__":
    unittest.main()
