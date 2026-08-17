import unittest

from evals.chinese_reliability.outline_metrics import measure_outline_coverage


class OutlineCoverageTests(unittest.TestCase):
    def test_counts_matching_heading_with_substantial_chinese_body(self):
        sections = [
            {"title": "行业现状", "description": ""},
            {"title": "主要风险", "description": ""},
            {"title": "未来趋势", "description": ""},
        ]
        report = (
            "# 报告\n\n## 行业现状\n" + "中" * 120
            + "\n\n## 主要风险分析\n" + "中" * 130
            + "\n\n## 未来趋势\n" + "中" * 20
        )

        result = measure_outline_coverage(report, sections)

        self.assertEqual(result["outline_section_count"], 3)
        self.assertEqual(result["outline_covered_count"], 2)
        self.assertAlmostEqual(result["outline_coverage_rate"], 2 / 3)

    def test_punctuation_and_spaces_do_not_break_title_matching(self):
        result = measure_outline_coverage(
            "## 未来 趋势：三年展望\n" + "中" * 100,
            [{"title": "未来趋势", "description": ""}],
        )

        self.assertEqual(result["outline_covered_count"], 1)

    def test_empty_outline_returns_zero_metrics(self):
        self.assertEqual(
            measure_outline_coverage("# 报告\n正文", []),
            {
                "outline_section_count": 0,
                "outline_covered_count": 0,
                "outline_coverage_rate": 0.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
