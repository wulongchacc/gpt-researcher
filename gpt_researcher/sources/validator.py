"""Validate scraped source content before it enters research context."""

from __future__ import annotations

import html
import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .registry import SourceRecord, SourceRegistry


_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "spm"}
_ERROR_PAGE_PATTERNS = (
    re.compile(r"(?:page\s+not\s+found|not\s+found)", re.IGNORECASE),
    re.compile(r"(?:页面不存在|找不到页面|错误页面)"),
    re.compile(r"(?:^|\s)404(?:\s|$)"),
)
_LOGIN_PAGE_PATTERNS = (
    re.compile(r"(?:请|需要|先).{0,8}登录"),
    re.compile(r"sign\s*in|log\s*in", re.IGNORECASE),
)
_CAPTCHA_PAGE_PATTERNS = (
    re.compile(r"验证码|人机验证"),
    re.compile(r"captcha", re.IGNORECASE),
)


@dataclass(frozen=True)
class FetchResponse:
    """Minimal HTTP response returned by an online source fetcher."""

    status_code: int
    final_url: str


@dataclass(frozen=True)
class SourceValidationResult:
    """Online availability result for one report source."""

    original_url: str
    final_url: str
    status_code: Optional[int]
    is_valid: bool
    status: str
    failure_reason: str
    attempts: int


AsyncFetcher = Callable[[str, float], Awaitable[FetchResponse]]


def _fetch_url(url: str, timeout: float) -> FetchResponse:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
            "Range": "bytes=0-1023",
            "User-Agent": "Mozilla/5.0 (compatible; GPTResearcherSourceValidator/1.0)",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return FetchResponse(
                status_code=int(response.getcode()),
                final_url=response.geturl(),
            )
    except HTTPError as exc:
        return FetchResponse(status_code=int(exc.code), final_url=exc.geturl())


async def _default_fetcher(url: str, timeout: float) -> FetchResponse:
    return await asyncio.to_thread(_fetch_url, url, timeout)


class SourceValidator:
    """Validate source URLs with bounded concurrency and retries."""

    def __init__(
        self,
        *,
        fetcher: Optional[AsyncFetcher] = None,
        timeout: float = 8.0,
        max_retries: int = 2,
        concurrency: int = 5,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if concurrency <= 0:
            raise ValueError("concurrency must be positive")

        self.fetcher = fetcher or _default_fetcher
        self.timeout = float(timeout)
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(concurrency)

    async def validate_many(self, urls: Iterable[str]) -> list[SourceValidationResult]:
        return await asyncio.gather(*(self._validate_one(url) for url in urls))

    async def _validate_one(self, original_url: str) -> SourceValidationResult:
        try:
            request_url = normalize_url(original_url)
        except (TypeError, ValueError):
            return SourceValidationResult(
                original_url=str(original_url),
                final_url="",
                status_code=None,
                is_valid=False,
                status="invalid",
                failure_reason="invalid_url",
                attempts=0,
            )

        for attempt in range(1, self.max_retries + 2):
            try:
                async with self._semaphore:
                    response = await asyncio.wait_for(
                        self.fetcher(request_url, self.timeout),
                        timeout=self.timeout,
                    )
            except asyncio.TimeoutError:
                if attempt <= self.max_retries:
                    continue
                return self._failure_result(
                    original_url, request_url, "timeout", "timeout", attempt
                )
            except (OSError, URLError):
                if attempt <= self.max_retries:
                    continue
                return self._failure_result(
                    original_url,
                    request_url,
                    "network_error",
                    "network_error",
                    attempt,
                )

            try:
                final_url = normalize_url(response.final_url or request_url)
            except (TypeError, ValueError):
                return SourceValidationResult(
                    original_url=original_url,
                    final_url="",
                    status_code=response.status_code,
                    is_valid=False,
                    status="invalid",
                    failure_reason="invalid_final_url",
                    attempts=attempt,
                )

            status_code = int(response.status_code)
            if 200 <= status_code < 300:
                return SourceValidationResult(
                    original_url=original_url,
                    final_url=final_url,
                    status_code=status_code,
                    is_valid=True,
                    status="valid",
                    failure_reason="ok",
                    attempts=attempt,
                )

            status = "blocked" if status_code in {403, 429} else "invalid"
            return SourceValidationResult(
                original_url=original_url,
                final_url=final_url,
                status_code=status_code,
                is_valid=False,
                status=status,
                failure_reason=f"http_{status_code}",
                attempts=attempt,
            )

        raise RuntimeError("unreachable validation state")

    @staticmethod
    def _failure_result(
        original_url: str,
        final_url: str,
        status: str,
        failure_reason: str,
        attempts: int,
    ) -> SourceValidationResult:
        return SourceValidationResult(
            original_url=original_url,
            final_url=final_url,
            status_code=None,
            is_valid=False,
            status=status,
            failure_reason=failure_reason,
            attempts=attempts,
        )


def _is_tracking_key(key: str) -> bool:
    lowered = key.lower()
    return lowered.startswith("utm_") or lowered in _TRACKING_QUERY_KEYS


def normalize_url(url: str) -> str:
    """Return a canonical absolute HTTP(S) URL."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")

    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only absolute HTTP(S) URLs are supported")

    host = parsed.hostname.lower()
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    path = parsed.path or ""
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not _is_tracking_key(key)
        )
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def _clean_content(value: Any) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if not isinstance(value, str):
        return ""

    text = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", value, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _sentence_count(content: str) -> int:
    return len(re.findall(r"[。！？.!?]+", content))


def _page_failure_reason(content: str) -> str | None:
    for pattern in _CAPTCHA_PAGE_PATTERNS:
        if pattern.search(content):
            return "captcha_page"
    for pattern in _LOGIN_PAGE_PATTERNS:
        if pattern.search(content):
            return "login_page"
    for pattern in _ERROR_PAGE_PATTERNS:
        if pattern.search(content):
            return "error_page"
    return None


def admit_scraped_source(
    source: Mapping[str, Any],
    *,
    min_content_chars: int = 200,
    min_sentences: int = 2,
) -> SourceRecord:
    """Classify one scraper result using content-quality thresholds."""
    original_url = str(source.get("url") or source.get("href") or "")
    try:
        canonical_url = normalize_url(original_url)
        failure_reason = "ok"
    except (TypeError, ValueError):
        canonical_url = ""
        failure_reason = "invalid_url"

    content = _clean_content(
        source.get("raw_content") or source.get("content") or source.get("body")
    )
    sentence_count = _sentence_count(content)

    if failure_reason == "ok":
        page_reason = _page_failure_reason(content)
        if page_reason:
            failure_reason = page_reason
        elif not content:
            failure_reason = "missing_content"
        elif len(content) < min_content_chars:
            failure_reason = "content_too_short"
        elif sentence_count < min_sentences:
            failure_reason = "too_few_sentences"

    return SourceRecord(
        source_id="",
        original_url=original_url,
        canonical_url=canonical_url,
        title=str(source.get("title") or ""),
        clean_content=content,
        http_status=source.get("status_code") or source.get("http_status"),
        content_type=source.get("content_type"),
        content_chars=len(content),
        sentence_count=sentence_count,
        checked_at=datetime.now(timezone.utc).isoformat(),
        is_usable=failure_reason == "ok",
        failure_reason=failure_reason,
    )


def admit_scraped_sources(
    sources: Iterable[Mapping[str, Any]],
    registry: SourceRegistry,
    *,
    min_content_chars: int = 200,
    min_sentences: int = 2,
) -> list[dict[str, Any]]:
    """Return scraper dictionaries that pass admission and register them."""
    admitted: list[dict[str, Any]] = []
    for source in sources:
        record = admit_scraped_source(
            source,
            min_content_chars=min_content_chars,
            min_sentences=min_sentences,
        )
        if record.canonical_url:
            registry.record_candidate(record.canonical_url)
        if not record.is_usable:
            continue

        stored = registry.add_usable(record)
        admitted_source = dict(source)
        admitted_source.update(
            {
                "url": stored.canonical_url,
                "raw_content": stored.clean_content,
                "source_id": stored.source_id,
            }
        )
        admitted.append(admitted_source)
    return admitted
