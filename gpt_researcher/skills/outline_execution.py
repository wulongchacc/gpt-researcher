"""Helpers for applying a user-confirmed outline during research."""

from __future__ import annotations

from typing import Any


SIMPLE_OUTLINE_SECTION_COUNT = 3


def _normalized_sections(outline: list[dict[str, Any]] | None) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for section in outline or []:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        if not title:
            continue
        description = str(section.get("description") or "").strip()
        sections.append((title, description))
    return sections


def outline_to_research_questions(
    outline: list[dict[str, Any]] | None,
) -> list[str]:
    """Convert confirmed sections into ordered deep-research directions."""
    return [
        f"{title}：{description}" if description else title
        for title, description in _normalized_sections(outline)
    ]


def build_simple_outline_search_queries(
    outline: list[dict[str, Any]] | None,
    original_query: str,
) -> list[str]:
    """Build bounded Simple-mode searches from a confirmed outline."""
    candidates = outline_to_research_questions(outline)[
        :SIMPLE_OUTLINE_SECTION_COUNT
    ]
    normalized_original = " ".join(str(original_query or "").split())
    if normalized_original:
        candidates.append(normalized_original)

    queries: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = " ".join(candidate.split())
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            queries.append(normalized)
    return queries


def format_outline_report_instruction(
    outline: list[dict[str, Any]] | None,
) -> str:
    """Build a writing constraint that preserves the confirmed section order."""
    sections = outline_to_research_questions(outline)
    if not sections:
        return ""

    numbered_sections = "\n".join(
        f"{index}. {section}" for index, section in enumerate(sections, start=1)
    )
    return (
        "The following report outline was confirmed by the user. Use every item "
        "as a major section and preserve this exact order. Do not rename, merge, "
        "or omit these sections. Subsections may be added when useful.\n"
        f"{numbered_sections}"
    )
