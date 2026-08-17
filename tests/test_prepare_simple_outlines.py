import unittest
from dataclasses import dataclass

from evals.chinese_reliability.prepare_simple_outlines import generate_outline_record


@dataclass(frozen=True)
class FakeSection:
    id: str
    title: str
    description: str


class FakePlanner:
    async def generate(self, task, language, cost_callback):
        cost_callback(0.01)
        cost_callback(0.02)
        return [
            FakeSection(id="section-1", title="背景", description="研究背景"),
            FakeSection(id="section-2", title="现状", description="研究现状"),
            FakeSection(id="section-3", title="趋势", description="研究趋势"),
        ]


class PrepareSimpleOutlinesTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_outline_record_tracks_sections_duration_and_cost(self):
        times = iter((10.0, 12.5))

        record = await generate_outline_record(
            {
                "id": "simple-01",
                "question": "测试问题",
                "report_type": "research_report",
            },
            FakePlanner(),
            clock=lambda: next(times),
        )

        self.assertEqual(record["id"], "simple-01")
        self.assertEqual(record["question"], "测试问题")
        self.assertEqual(len(record["sections"]), 3)
        self.assertEqual(record["sections"][0]["title"], "背景")
        self.assertAlmostEqual(record["outline_duration_seconds"], 2.5)
        self.assertAlmostEqual(record["outline_cost"], 0.03)

    async def test_rejects_non_simple_case_before_calling_planner(self):
        with self.assertRaisesRegex(ValueError, "Simple"):
            await generate_outline_record(
                {
                    "id": "deep-01",
                    "question": "测试问题",
                    "report_type": "deep",
                },
                FakePlanner(),
            )


if __name__ == "__main__":
    unittest.main()
