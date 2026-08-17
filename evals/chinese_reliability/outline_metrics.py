"""Measure how completely a report follows a confirmed outline."""

from __future__ import annotations

import re
import unicodedata


HEADING_PATTERN = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
CHINESE_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def normalize_heading(value: str) -> str:
    return "".join(
        character.casefold()
        for character in value
        if not character.isspace()
        and not unicodedata.category(character).startswith("P")
    )


def extract_heading_blocks(report: str) -> list[tuple[str, str]]:
    matches = list(HEADING_PATTERN.finditer(report))
    return [
        (
            normalize_heading(match.group(1)),
            report[
                match.end() : matches[index + 1].start()
                if index + 1 < len(matches)
                else len(report)
            ],
        )
        for index, match in enumerate(matches)
    ]


def chinese_char_count(value: str) -> int:
    return len(CHINESE_PATTERN.findall(value))


def measure_outline_coverage(report: str, sections: list[dict]) -> dict:
    heading_blocks = extract_heading_blocks(report)
    covered = 0
    for section in sections:
        expected = normalize_heading(str(section.get("title") or ""))
        matched = any(
            expected
            and (heading == expected or expected in heading)
            and chinese_char_count(body) >= 100
            for heading, body in heading_blocks
        )
        covered += int(matched)

    total = len(sections)
    return {
        "outline_section_count": total,
        "outline_covered_count": covered,
        "outline_coverage_rate": covered / total if total else 0.0,
    }
