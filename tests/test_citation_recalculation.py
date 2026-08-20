import unittest

from evals.chinese_reliability.recalculate_citations import recalculate_run
from evals.chinese_reliability.source_validator import SourceValidationResult


def source_result(url: str, status: str = "valid") -> dict:
    return {
        "original_url": url,
        "normalized_url": url,
        "final_url": url,
        "status": status,
        "http_status": 200 if status == "valid" else 404,
        "content_length": 500 if status == "valid" else 0,
        "reason": "ok" if status == "valid" else "http_404",
    }


class FakeValidator:
    async def validate_many(self, urls):
        return [
            SourceValidationResult(**source_result(url))
            for url in urls
        ]


class CitationRecalculationTests(unittest.IsolatedAsyncioTestCase):
    async def test_recalculate_run_preserves_candidates_and_scores_report_links(self):
        old_run = {
            "id": "simple-01",
            "question": "测试问题",
            "report_type": "research_report",
            "duration_seconds": 12.0,
            "cost": 0.1,
            "error": None,
            "source_results": [
                source_result("https://a.example"),
                source_result("https://b.example"),
                source_result("https://unused.example", "invalid"),
            ],
        }
        report = (
            "中" * 500
            + "\n[来源A](https://a.example)"
            + "\n[来源B](https://b.example)"
        )

        recalculated = await recalculate_run(
            old_run,
            report,
            validator=FakeValidator(),
        )

        self.assertEqual(recalculated["citation_count"], 2)
        self.assertEqual(recalculated["valid_citation_count"], 2)
        self.assertEqual(recalculated["candidate_source_count"], 3)
        self.assertEqual(recalculated["reachable_candidate_source_count"], 2)
        self.assertEqual(len(recalculated["candidate_source_results"]), 3)
        self.assertTrue(recalculated["report_success"])


if __name__ == "__main__":
    unittest.main()
