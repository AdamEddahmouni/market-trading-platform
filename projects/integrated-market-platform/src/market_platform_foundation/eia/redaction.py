"""Credential redaction for EIA API v2 query-string api_key parameter."""

from __future__ import annotations

import copy
import re
from typing import Any

_REDACT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("api_key", re.compile(r"(?i)(api_key=)[^&\s\"']+")),
    ("EIA_API_KEY", re.compile(r"(?i)(EIA_API_KEY\s*[:=]\s*)\S+")),
)


def redact_text(value: str) -> str:
    sanitized = value
    for _, pattern in _REDACT_PATTERNS:
        sanitized = pattern.sub(r"\1REDACTED", sanitized)
    return sanitized


def _redact_request_block(request: dict[str, Any]) -> None:
    params = request.get("params")
    if isinstance(params, dict) and "api_key" in params:
        params["api_key"] = "REDACTED"


def sanitize_request_params(params: dict[str, Any]) -> dict[str, Any]:
    safe = {key: value for key, value in params.items() if key != "api_key"}
    return safe


def sanitize_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip echoed api_key from EIA request metadata before logging/hashing."""
    sanitized = copy.deepcopy(payload)

    top_request = sanitized.get("request")
    if isinstance(top_request, dict):
        _redact_request_block(top_request)

    response = sanitized.get("response")
    if isinstance(response, dict):
        nested_request = response.get("request")
        if isinstance(nested_request, dict):
            _redact_request_block(nested_request)

    return sanitized


def sanitize_error(exc: BaseException) -> str:
    return redact_text(str(exc))


__all__ = [
    "redact_text",
    "sanitize_error",
    "sanitize_request_params",
    "sanitize_response_payload",
]
