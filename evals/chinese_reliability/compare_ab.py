"""Compare baseline and confirmed-outline Simple benchmark summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED_QUERY_COUNT = 5


def relative_change(
    baseline: float | None,
    enhanced: float | None,
) -> float | None:
    if baseline in (None, 0) or enhanced is None:
        return None
    return (enhanced - baseline) / baseline


def build_ab_comparison(baseline: dict, enhanced: dict) -> dict:
    counts = (baseline.get("total_queries"), enhanced.get("total_queries"))
    if counts != (EXPECTED_QUERY_COUNT, EXPECTED_QUERY_COUNT):
        raise ValueError("baseline and enhanced groups must each contain exactly 5 queries")

    return {
        "query_count": EXPECTED_QUERY_COUNT,
        "baseline": baseline,
        "enhanced": enhanced,
        "changes": {
            "success_rate_points": (
                enhanced["report_success_rate"] - baseline["report_success_rate"]
            ),
            "valid_citation_rate_relative": relative_change(
                baseline["valid_citation_rate"],
                enhanced["valid_citation_rate"],
            ),
            "average_duration_relative": relative_change(
                baseline["average_duration_seconds"],
                enhanced["average_duration_seconds"],
            ),
            "average_cost_relative": relative_change(
                baseline["average_cost"],
                enhanced["average_cost"],
            ),
            "outline_coverage_rate": enhanced["outline_coverage_rate"],
        },
    }


def _format_percent(value: float | None) -> str:
    return "-" if value is None else f"{value:+.1%}"


def _format_number(value: float | None, *, prefix: str = "") -> str:
    return "-" if value is None else f"{prefix}{value:.4f}"


def comparison_markdown(comparison: dict) -> str:
    baseline = comparison["baseline"]
    enhanced = comparison["enhanced"]
    changes = comparison["changes"]
    rows = [
        (
            "报告成功率",
            f"{baseline['report_success_rate']:.1%}",
            f"{enhanced['report_success_rate']:.1%}",
            f"{changes['success_rate_points']:+.1%}（百分点）",
        ),
        (
            "有效引用率",
            f"{baseline['valid_citation_rate']:.1%}",
            f"{enhanced['valid_citation_rate']:.1%}",
            _format_percent(changes["valid_citation_rate_relative"]),
        ),
        (
            "平均耗时（秒）",
            (
                "-"
                if baseline["average_duration_seconds"] is None
                else f"{baseline['average_duration_seconds']:.1f}"
            ),
            (
                "-"
                if enhanced["average_duration_seconds"] is None
                else f"{enhanced['average_duration_seconds']:.1f}"
            ),
            _format_percent(changes["average_duration_relative"]),
        ),
        (
            "平均成本",
            _format_number(baseline["average_cost"], prefix="$"),
            _format_number(enhanced["average_cost"], prefix="$"),
            _format_percent(changes["average_cost_relative"]),
        ),
        (
            "提纲覆盖率",
            "-",
            f"{enhanced['outline_coverage_rate']:.1%}",
            f"{changes['outline_coverage_rate']:.1%}",
        ),
    ]
    lines = [
        "# Simple 提纲 A/B 评测结果",
        "",
        "| 指标 | 基线组 | 提纲组 | 变化 |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(f"| {name} | {before} | {after} | {change} |" for name, before, after, change in rows)
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Simple A/B benchmark results")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--enhanced", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    enhanced = json.loads(args.enhanced.read_text(encoding="utf-8"))
    comparison = build_ab_comparison(baseline, enhanced)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "comparison.md").write_text(
        comparison_markdown(comparison),
        encoding="utf-8",
    )
    print(f"对比结果已保存：{args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
