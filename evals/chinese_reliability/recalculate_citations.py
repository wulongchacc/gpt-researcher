"""Recalculate citation metrics from saved reports without calling an LLM."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .metrics import build_run_metrics
from .run_benchmark import build_metadata, write_outputs
from .source_validator import (
    SourceValidationResult,
    SourceValidator,
    extract_report_citation_urls,
)


def _source_result(value: dict) -> SourceValidationResult:
    return SourceValidationResult(
        original_url=value["original_url"],
        normalized_url=value["normalized_url"],
        final_url=value.get("final_url"),
        status=value["status"],
        http_status=value.get("http_status"),
        content_length=int(value.get("content_length", 0)),
        reason=value["reason"],
    )


async def recalculate_run(
    run: dict,
    report: str,
    *,
    validator: SourceValidator | None = None,
) -> dict:
    """Return one saved run with final-report citation metrics recalculated."""
    validator = validator or SourceValidator()
    candidate_values = run.get("candidate_source_results") or run.get(
        "source_results", []
    )
    candidate_results = [_source_result(value) for value in candidate_values]
    known_results = {result.normalized_url: result for result in candidate_results}
    known_results.update(
        {
            result.final_url: result
            for result in candidate_results
            if result.final_url
        }
    )

    citation_urls = extract_report_citation_urls(report)
    missing_urls = [url for url in citation_urls if url not in known_results]
    for result in await validator.validate_many(missing_urls):
        known_results[result.normalized_url] = result
        if result.final_url:
            known_results[result.final_url] = result
    citation_results = [known_results[url] for url in citation_urls]

    is_deep = run.get("report_type") == "deep"
    metrics = build_run_metrics(
        report=report,
        source_results=citation_results,
        duration_seconds=float(run.get("duration_seconds", 0.0)),
        cost=run.get("cost"),
        error=run.get("error"),
        min_report_chars=1500 if is_deep else 400,
        min_valid_sources=5 if is_deep else 2,
    )
    return {
        **run,
        "report": report,
        "source_results": [asdict(result) for result in citation_results],
        "candidate_source_results": [
            asdict(result) for result in candidate_results
        ],
        "candidate_source_count": len(candidate_results),
        "reachable_candidate_source_count": sum(
            result.status == "valid" for result in candidate_results
        ),
        **metrics,
    }


def _load_runs(input_dir: Path) -> list[dict]:
    runs_path = input_dir / "runs.jsonl"
    return [
        json.loads(line)
        for line in runs_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def recalculate_directory(input_dir: Path, output_dir: Path) -> list[dict]:
    if input_dir.resolve() == output_dir.resolve():
        raise ValueError("output directory must differ from input directory")

    validator = SourceValidator()
    recalculated_runs = []
    for run in _load_runs(input_dir):
        report_path = input_dir / "reports" / f"{run['id']}.md"
        report = report_path.read_text(encoding="utf-8")
        recalculated_runs.append(
            await recalculate_run(run, report, validator=validator)
        )

    metadata = build_metadata("citation-recalculation")
    metadata.update(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "citation_scope": "final_report_markdown_links",
            "source_directory": str(input_dir),
        }
    )
    write_outputs(output_dir, recalculated_runs, metadata)
    return recalculated_runs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recalculate saved report citation metrics without LLM calls"
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    asyncio.run(recalculate_directory(args.input_dir, args.output_dir))
    print(f"重新统计结果已保存：{args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
