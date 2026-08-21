"""Credential redaction for FRED V1 query-string and V2 Bearer auth."""

from __future__ import annotations

import re
from typing import Any

_REDACT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("api_key", re.compile(r"(?i)(api_key=)[^&\s\"']+")),
    ("FRED_API_KEY", re.compile(r"(?i)(FRED_API_KEY\s*[:=]\s*)\S+")),
    (
        "Authorization",
        re.compile(r"(?i)(Authorization\s*[:=]\s*(?:Bearer|Basic)\s+)\S+"),
    ),
)


def redact_text(value: str) -> str:
    sanitized = value
    for _, pattern in _REDACT_PATTERNS:
        sanitized = pattern.sub(r"\1REDACTED", sanitized)
    return sanitized


def sanitize_v1_request_semantics(*, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    safe = {key: value for key, value in params.items() if key != "api_key"}
    safe["endpoint"] = endpoint
    return safe


def sanitize_error(exc: BaseException) -> str:
    return redact_text(str(exc))


__all__ = ["redact_text", "sanitize_error", "sanitize_v1_request_semantics"]
