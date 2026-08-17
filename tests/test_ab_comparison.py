import unittest

from evals.chinese_reliability.compare_ab import (
    build_ab_comparison,
    comparison_markdown,
    relative_change,
)


class AbComparisonTests(unittest.TestCase):
    def setUp(self):
        self.baseline = {
            "total_queries": 5,
            "report_success_rate": 0.6,
            "valid_citation_rate": 0.75,
            "average_duration_seconds": 120.0,
            "average_cost": 0.08,
            "outline_coverage_rate": 0.0,
        }
        self.enhanced = {
            "total_queries": 5,
            "report_success_rate": 0.8,
            "valid_citation_rate": 0.825,
            "average_duration_seconds": 150.0,
            "average_cost": 0.1,
            "outline_coverage_rate": 0.9,
        }

    def test_builds_success_points_and_relative_changes(self):
        comparison = build_ab_comparison(self.baseline, self.enhanced)

        changes = comparison["changes"]
        self.assertAlmostEqual(changes["success_rate_points"], 0.2)
        self.assertAlmostEqual(changes["valid_citation_rate_relative"], 0.1)
        self.assertAlmostEqual(changes["average_duration_relative"], 0.25)
        self.assertAlmostEqual(changes["average_cost_relative"], 0.25)
        self.assertAlmostEqual(changes["outline_coverage_rate"], 0.9)

    def test_zero_baseline_returns_none_for_relative_change(self):
        self.assertIsNone(relative_change(0.0, 0.5))
        self.assertIsNone(relative_change(None, 0.5))

    def test_rejects_groups_with_different_or_unexpected_query_counts(self):
        with self.assertRaisesRegex(ValueError, "exactly 5"):
            build_ab_comparison(
                {**self.baseline, "total_queries": 4},
                self.enhanced,
            )

    def test_markdown_handles_missing_duration_and_cost(self):
        comparison = build_ab_comparison(
            {
                **self.baseline,
                "average_duration_seconds": None,
                "average_cost": None,
            },
            {
                **self.enhanced,
                "average_duration_seconds": None,
                "average_cost": None,
            },
        )

        markdown = comparison_markdown(comparison)

        self.assertIn("| 平均耗时（秒） | - | - | - |", markdown)
        self.assertIn("| 平均成本 | - | - | - |", markdown)


if __name__ == "__main__":
    unittest.main()
