import json
import unittest
from pathlib import Path
from unittest.mock import patch

from evals.chinese_reliability.run_benchmark import (
    build_output_documents,
    load_cases,
    load_outline_records,
    run_single_case,
    validate_outline_records_for_cases,
)
from evals.chinese_reliability.source_validator import SourceValidationResult


class FakeResearcher:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def conduct_research(self):
        return ["context"]

    async def write_report(self):
        return "中" * 900

    def get_source_urls(self):
        return ["https://a.example", "https://b.example", "https://c.example"]

    def get_costs(self):
        return 0.03


class FakeValidator:
    async def validate_many(self, urls):
        return [
            SourceValidationResult(
                original_url=url,
                normalized_url=url,
                final_url=url,
                status="valid",
                http_status=200,
                content_length=500,
                reason="ok",
            )
            for url in urls
        ]


class ReliabilityRunnerTests(unittest.IsolatedAsyncioTestCase):
    def test_load_cases_uses_stable_order_and_limit(self):
        path = (
            Path(__file__).parents[1]
            / "evals"
            / "chinese_reliability"
            / "queries.json"
        )

        cases = load_cases(path, limit=1)

        self.assertEqual([case["id"] for case in cases], ["simple-01"])

    def test_load_cases_selects_one_simple_and_one_deep_by_id(self):
        path = (
            Path(__file__).parents[1]
            / "evals"
            / "chinese_reliability"
            / "queries.json"
        )

        cases = load_cases(path, ids=["simple-01", "deep-01"])

        self.assertEqual([case["id"] for case in cases], ["simple-01", "deep-01"])

    async def test_run_single_case_collects_report_sources_and_metrics(self):
        case = {
            "id": "q1",
            "question": "测试问题",
            "report_type": "research_report",
        }

        result = await run_single_case(
            case,
            researcher_factory=FakeResearcher,
            validator=FakeValidator(),
        )

        self.assertEqual(result["id"], "q1")
        self.assertEqual(result["report_type"], "research_report")
        self.assertTrue(result["report_success"])
        self.assertEqual(result["valid_citation_count"], 3)
        self.assertAlmostEqual(result["cost"], 0.03)

    async def test_enhanced_case_uses_confirmed_outline_and_includes_outline_cost(self):
        captured = {}

        def researcher_factory(**kwargs):
            captured.update(kwargs)
            return FakeResearcher(**kwargs)

        outline_record = {
            "id": "q1",
            "question": "测试问题",
            "sections": [
                {"id": "section-1", "title": "背景", "description": "研究背景"},
                {"id": "section-2", "title": "现状", "description": "研究现状"},
                {"id": "section-3", "title": "趋势", "description": "研究趋势"},
            ],
            "outline_duration_seconds": 2.5,
            "outline_cost": 0.01,
        }

        result = await run_single_case(
            {"id": "q1", "question": "测试问题", "report_type": "research_report"},
            mode="enhanced",
            outline_record=outline_record,
            researcher_factory=researcher_factory,
            validator=FakeValidator(),
        )

        self.assertEqual(captured["outline"], outline_record["sections"])
        self.assertEqual(captured["model_profile"], "simple")
        self.assertGreaterEqual(result["duration_seconds"], 2.5)
        self.assertAlmostEqual(result["cost"], 0.04)
        self.assertEqual(result["outline_section_count"], 3)

    def test_load_outline_records_validates_question_and_section_count(self):
        records = [
            {
                "id": "simple-01",
                "question": "测试问题",
                "sections": [
                    {"id": "section-1", "title": "背景", "description": ""},
                    {"id": "section-2", "title": "现状", "description": ""},
                    {"id": "section-3", "title": "趋势", "description": ""},
                ],
                "outline_duration_seconds": 1.0,
                "outline_cost": 0.01,
            }
        ]
        with patch.object(
            Path,
            "read_text",
            return_value=json.dumps(records, ensure_ascii=False),
        ):
            loaded = load_outline_records(Path("outlines.json"))

        self.assertEqual(loaded["simple-01"]["question"], "测试问题")

        records[0]["sections"] = records[0]["sections"][:2]
        with patch.object(
            Path,
            "read_text",
            return_value=json.dumps(records, ensure_ascii=False),
        ):
            with self.assertRaisesRegex(ValueError, "3 to 5"):
                load_outline_records(Path("outlines.json"))

    def test_enhanced_mode_requires_matching_outline_for_every_case(self):
        cases = [
            {
                "id": f"simple-{index:02d}",
                "question": f"问题{index}",
                "report_type": "research_report",
            }
            for index in range(1, 6)
        ]
        records = {
            case["id"]: {
                "id": case["id"],
                "question": case["question"],
                "sections": [{}, {}, {}],
            }
            for case in cases
        }

        validated = validate_outline_records_for_cases(cases, "enhanced", records)

        self.assertEqual(set(validated), {case["id"] for case in cases})

        records.pop("simple-05")
        with self.assertRaisesRegex(ValueError, "simple-05"):
            validate_outline_records_for_cases(cases, "enhanced", records)

    def test_enhanced_mode_rejects_deep_cases(self):
        with self.assertRaisesRegex(ValueError, "Simple"):
            validate_outline_records_for_cases(
                [{"id": "deep-01", "question": "问题", "report_type": "deep"}],
                "enhanced",
                {"deep-01": {"id": "deep-01", "question": "问题"}},
            )

    def test_build_output_documents_creates_machine_and_human_readable_content(self):
        runs = [
            {
                "id": "q1",
                "question": "测试问题",
                "report_type": "research_report",
                "report": "报告",
                "error": None,
                "duration_seconds": 1.0,
                "cost": 0.01,
                "citation_count": 3,
                "valid_citation_count": 3,
                "valid_citation_rate": 1.0,
                "report_success": True,
                "source_results": [],
            }
        ]

        documents = build_output_documents(
            runs,
            metadata={"mode": "baseline", "git_commit": "abc", "timestamp": "now"},
        )

        self.assertEqual(documents[Path("reports/q1.md")], "报告")
        self.assertIn(Path("runs.jsonl"), documents)
        self.assertIn(Path("summary.json"), documents)
        self.assertIn(Path("summary.md"), documents)
        summary = json.loads(documents[Path("summary.json")])
        self.assertEqual(summary["summaries"]["research_report"]["total_queries"], 1)
        self.assertIn("提纲覆盖率", documents[Path("summary.md")])


if __name__ == "__main__":
    unittest.main()
