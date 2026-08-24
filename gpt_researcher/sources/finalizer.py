"""Repair report links using completed online validation results."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .registry import SourceRegistry
from .validator import SourceValidationResult, normalize_url


_REFERENCE_SECTION_PATTERN = re.compile(
    r"(?ims)^##\s+(?:references|参考文献)\s*$.*\Z"
)
_MARKDOWN_LINK_PATTERN = re.compile(
    r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)", re.IGNORECASE
)
_BARE_URL_PATTERN = re.compile(r"(?<!\]\()https?://[^\s)>]+", re.IGNORECASE)
_SOURCE_LABEL_PATTERN = re.compile(r"^S\d+$", re.IGNORECASE)
_SOURCE_ID_PATTERN = re.compile(r"\[(S\d+)\]", re.IGNORECASE)


@dataclass(frozen=True)
class ReportSourceRepairResult:
    report: str
    valid_citation_count: int
    removed_link_count: int
    redirected_link_count: int
    repair_rounds: int = 1


def report_body_char_count(report_markdown: str) -> int:
    """Count visible non-whitespace characters outside the references section."""
    report_body = _REFERENCE_SECTION_PATTERN.sub("", report_markdown or "")
    report_body = _MARKDOWN_LINK_PATTERN.sub(lambda match: match.group(1), report_body)
    report_body = _BARE_URL_PATTERN.sub("", report_body)
    report_body = re.sub(r"[#>*_`~\[\]()-]", "", report_body)
    return len(re.sub(r"\s+", "", report_body))


def repair_report_sources(
    report_markdown: str,
    registry: SourceRegistry,
    validation_results: Iterable[SourceValidationResult],
) -> ReportSourceRepairResult:
    """Remove failed links and rebuild references from validated sources once."""
    records_by_id = {record.source_id: record for record in registry.usable_records()}
    records_by_url = {record.canonical_url: record for record in registry.usable_records()}
    validation_by_url = {}
    for result in validation_results:
        try:
            validation_by_url[normalize_url(result.original_url)] = result
        except (TypeError, ValueError):
            continue

    report_body = _REFERENCE_SECTION_PATTERN.sub("", report_markdown or "").rstrip()
    cited_ids = []
    final_urls_by_id = {}
    removed_urls = set()
    redirected_ids = set()

    def repair_link(match: re.Match) -> str:
        label, raw_url = match.groups()
        try:
            canonical_url = normalize_url(raw_url)
        except (TypeError, ValueError):
            removed_urls.add(raw_url)
            return "" if _SOURCE_LABEL_PATTERN.fullmatch(label) else label

        record = records_by_url.get(canonical_url)
        result = validation_by_url.get(canonical_url)
        if record is None or result is None or not result.is_valid:
            removed_urls.add(canonical_url)
            return "" if _SOURCE_LABEL_PATTERN.fullmatch(label) else label

        try:
            final_url = normalize_url(result.final_url or canonical_url)
        except (TypeError, ValueError):
            removed_urls.add(canonical_url)
            return "" if _SOURCE_LABEL_PATTERN.fullmatch(label) else label

        if _SOURCE_LABEL_PATTERN.fullmatch(label):
            source_id = label.upper()
            if source_id != record.source_id:
                removed_urls.add(canonical_url)
                return ""
            if source_id not in cited_ids:
                cited_ids.append(source_id)
            final_urls_by_id[source_id] = final_url
            if final_url != canonical_url:
                redirected_ids.add(source_id)
            return f"[{source_id}]({final_url})"

        return f"[{label}]({final_url})"

    report_body = _MARKDOWN_LINK_PATTERN.sub(repair_link, report_body)

    def repair_bare_url(match: re.Match) -> str:
        raw_url = match.group(0)
        try:
            canonical_url = normalize_url(raw_url)
        except (TypeError, ValueError):
            removed_urls.add(raw_url)
            return ""

        record = records_by_url.get(canonical_url)
        result = validation_by_url.get(canonical_url)
        if record is None or result is None or not result.is_valid:
            removed_urls.add(canonical_url)
            return ""
        return normalize_url(result.final_url or canonical_url)

    report_body = _BARE_URL_PATTERN.sub(repair_bare_url, report_body)

    renumbered_ids = {
        source_id: f"S{index}"
        for index, source_id in enumerate(cited_ids, start=1)
    }

    def renumber_source_id(match: re.Match) -> str:
        source_id = match.group(1).upper()
        replacement = renumbered_ids.get(source_id)
        return f"[{replacement}]" if replacement else ""

    report_body = _SOURCE_ID_PATTERN.sub(renumber_source_id, report_body).rstrip()

    if cited_ids:
        references = ["", "", "## References", ""]
        for source_id in cited_ids:
            record = records_by_id[source_id]
            title = record.title.strip() or renumbered_ids[source_id]
            references.append(
                f"- [{title}]({final_urls_by_id[source_id]}) "
                f"[{renumbered_ids[source_id]}]"
            )
        report_body += "\n".join(references) + "\n"

    return ReportSourceRepairResult(
        report=report_body,
        valid_citation_count=len(cited_ids),
        removed_link_count=len(removed_urls),
        redirected_link_count=len(redirected_ids),
    )
