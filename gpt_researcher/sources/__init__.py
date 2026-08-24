"""Source admission and citation state for research reports."""

from .registry import SourceRecord, SourceRegistry
from .finalizer import (
    ReportSourceRepairResult,
    repair_report_sources,
    report_body_char_count,
)
from .validator import (
    FetchResponse,
    SourceValidationResult,
    SourceValidator,
    admit_scraped_source,
    admit_scraped_sources,
    normalize_url,
)

__all__ = [
    "SourceRecord",
    "SourceRegistry",
    "ReportSourceRepairResult",
    "repair_report_sources",
    "report_body_char_count",
    "FetchResponse",
    "SourceValidationResult",
    "SourceValidator",
    "admit_scraped_source",
    "admit_scraped_sources",
    "normalize_url",
]
