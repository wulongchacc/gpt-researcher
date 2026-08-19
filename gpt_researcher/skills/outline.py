"""Structured outline generation for deep research."""

import json
from dataclasses import dataclass
from typing import Any

from ..utils.llm import create_chat_completion


MIN_OUTLINE_SECTIONS = 3
MAX_OUTLINE_SECTIONS = 5


class OutlineParseError(ValueError):
    """Raised when a model response cannot produce a valid outline."""


@dataclass(frozen=True)
class OutlineSection:
    id: str
    title: str
    description: str


def _remove_markdown_fence(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _load_sections(raw: str) -> list[Any]:
    try:
        payload = json.loads(_remove_markdown_fence(raw))
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutlineParseError("The outline response is not valid JSON") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("sections"), list):
        raise OutlineParseError("The outline response must contain a sections list")
    return payload["sections"]


def parse_outline_response(raw: str) -> list[OutlineSection]:
    """Parse a model response into three to five unique sections."""
    sections: list[OutlineSection] = []
    seen_titles: set[str] = set()

    for item in _load_sections(raw):
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        if not title:
            raise OutlineParseError("Every outline section must have a title")

        normalized_title = title.casefold()
        if normalized_title in seen_titles:
            continue

        description = str(item.get("description") or "").strip()
        seen_titles.add(normalized_title)
        sections.append(
            OutlineSection(
                id=f"section-{len(sections) + 1}",
                title=title,
                description=description,
            )
        )
        if len(sections) == MAX_OUTLINE_SECTIONS:
            break

    if len(sections) < MIN_OUTLINE_SECTIONS:
        raise OutlineParseError(
            f"An outline must contain at least {MIN_OUTLINE_SECTIONS} unique sections"
        )
    return sections


class OutlinePlanner:
    """Generate a structured outline with the request's strategic model."""

    def __init__(self, config, section_count: int | None = None):
        self.config = config
        self.section_count = section_count

    async def generate(
        self,
        task: str,
        language: str = "English",
        cost_callback=None,
    ) -> list[OutlineSection]:
        normalized_task = task.strip()
        if not normalized_task:
            raise ValueError("The research task cannot be empty")

        normalized_language = language.strip() or "English"
        section_requirement = (
            f"Return exactly {self.section_count} non-overlapping sections."
            if self.section_count
            else "Return 3 to 5 non-overlapping sections."
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert research planner. Return valid JSON only, "
                    "without markdown, commentary, or additional keys."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Create a research outline for this task: {normalized_task}\n"
                    f"Write the outline in: {normalized_language}\n"
                    f"{section_requirement} Each section must be "
                    "researchable from public information and describe the questions "
                    "it should answer. Use exactly this schema:\n"
                    '{"sections": [{"title": "<title>", '
                    '"description": "<research scope and questions>"}]}'
                ),
            },
        ]

        raw = await create_chat_completion(
            messages=messages,
            llm_provider=self.config.strategic_llm_provider,
            model=self.config.strategic_llm_model,
            reasoning_effort=getattr(self.config, "reasoning_effort", None),
            max_tokens=getattr(self.config, "strategic_token_limit", 2000),
            llm_kwargs=getattr(self.config, "llm_kwargs", {}),
            temperature=0.2,
            cost_callback=cost_callback,
        )
        sections = parse_outline_response(raw)
        if self.section_count:
            return sections[: self.section_count]
        return sections
