"""Structured source records shared by retrieval and report generation."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    original_url: str
    canonical_url: str
    title: str
    clean_content: str
    http_status: int | None
    content_type: str | None
    content_chars: int
    sentence_count: int
    checked_at: str
    is_usable: bool
    failure_reason: str


class SourceRegistry:
    """Keep candidate, usable, and cited source state separate."""

    def __init__(self) -> None:
        self._candidate_urls: list[str] = []
        self._candidate_seen: set[str] = set()
        self._usable_by_url: dict[str, SourceRecord] = {}
        self._cited_ids: list[str] = []

    @property
    def candidate_urls(self) -> list[str]:
        return list(self._candidate_urls)

    def record_candidate(self, url: str) -> str:
        from .validator import normalize_url

        canonical_url = normalize_url(url)
        if canonical_url not in self._candidate_seen:
            self._candidate_seen.add(canonical_url)
            self._candidate_urls.append(canonical_url)
        return canonical_url

    def add_usable(self, record: SourceRecord) -> SourceRecord:
        from .validator import normalize_url

        if not record.is_usable:
            raise ValueError("Only usable source records can enter the registry")

        canonical_url = normalize_url(record.canonical_url or record.original_url)
        existing = self._usable_by_url.get(canonical_url)
        if existing is not None:
            return existing

        stored = replace(
            record,
            source_id=f"S{len(self._usable_by_url) + 1}",
            canonical_url=canonical_url,
        )
        self._usable_by_url[canonical_url] = stored
        return stored

    def mark_cited(self, source_id: str) -> None:
        if not any(record.source_id == source_id for record in self._usable_by_url.values()):
            raise KeyError(f"Unknown source ID: {source_id}")
        if source_id not in self._cited_ids:
            self._cited_ids.append(source_id)

    def usable_records(self) -> list[SourceRecord]:
        return list(self._usable_by_url.values())

    def cited_records(self) -> list[SourceRecord]:
        records_by_id = {
            record.source_id: record for record in self._usable_by_url.values()
        }
        return [records_by_id[source_id] for source_id in self._cited_ids]

    def usable_urls(self) -> list[str]:
        return list(self._usable_by_url)
