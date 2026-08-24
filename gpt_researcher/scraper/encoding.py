"""Encoding helpers for scraper HTTP responses."""


_GENERIC_ENCODINGS = {
    "ascii",
    "iso-8859-1",
    "iso8859-1",
    "latin-1",
    "latin1",
}

_CHINESE_ENCODINGS = {
    "cp936",
    "gb2312",
    "gb_2312-80",
    "gbk",
    "gb18030",
}


def _normalize_encoding(encoding):
    if not encoding:
        return None

    normalized = encoding.strip().lower().replace("_", "-")
    if normalized in {item.replace("_", "-") for item in _CHINESE_ENCODINGS}:
        return "gb18030"
    return normalized


def resolve_response_encoding(response):
    """Choose a reliable encoding for a requests-style response."""
    declared = _normalize_encoding(getattr(response, "encoding", None))
    if declared and declared not in _GENERIC_ENCODINGS:
        return declared

    detected = _normalize_encoding(
        getattr(response, "apparent_encoding", None)
    )
    return detected or declared
