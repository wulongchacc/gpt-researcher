"""Generate and persist reviewable outlines for the Simple A/B benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .run_benchmark import DEFAULT_OUTPUT_ROOT, DEFAULT_QUERIES_PATH, load_cases


DEFAULT_OUTLINES_PATH = DEFAULT_OUTPUT_ROOT / "simple-outlines.json"


async def generate_outline_record(
    case: dict,
    planner,
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> dict:
    if case.get("report_type") != "research_report":
        raise ValueError("outline preparation only supports Simple cases")

    total_cost = 0.0

    def add_cost(cost: float) -> None:
        nonlocal total_cost
        total_cost += float(cost)

    started = clock()
    sections = await planner.generate(
        task=case["question"],
        language="Chinese (Simplified)",
        cost_callback=add_cost,
    )
    duration = clock() - started
    return {
        "id": case["id"],
        "question": case["question"],
        "sections": [asdict(section) for section in sections],
        "outline_duration_seconds": round(duration, 3),
        "outline_cost": total_cost,
    }


def build_simple_planner():
    from gpt_researcher.config import Config
    from gpt_researcher.config.model_profiles import resolve_model_profile
    from gpt_researcher.skills.outline import OutlinePlanner

    config = Config()
    _, overrides = resolve_model_profile("research_report", "simple")
    config.apply_runtime_overrides(overrides)
    return OutlinePlanner(config)


async def prepare_simple_outlines(
    cases: list[dict],
    output_path: Path,
    *,
    planner=None,
) -> list[dict]:
    planner = planner or build_simple_planner()
    records: list[dict] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] 生成提纲：{case['id']}", flush=True)
        record = await generate_outline_record(case, planner)
        records.append(record)
        output_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"  {len(record['sections'])} 节；"
            f"耗时 {record['outline_duration_seconds']:.1f}s；"
            f"成本 ${record['outline_cost']:.6f}",
            flush=True,
        )
    return records


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Simple benchmark outlines")
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTLINES_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = [
        case
        for case in load_cases(args.queries)
        if case["report_type"] == "research_report"
    ]
    if len(cases) != 5:
        raise ValueError("outline preparation requires exactly 5 Simple cases")
    asyncio.run(prepare_simple_outlines(cases, args.output))
    print(f"提纲已保存，请人工确认后再运行实验：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
