"""Finviz secret redaction — URLs, exceptions, logs."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .config import REDACT_KEYS

REDACTED = "<REDACTED>"
_AUTH_QUERY_RE = re.compile(r"([?&]auth=)[^&\s\"']+", re.IGNORECASE)
_SENSITIVE_QUERY_RE = re.compile(
    r"([?&](?:auth|token|api_token|password|passwd|session|sessionid)=)[^&\s\"']+",
    re.IGNORECASE,
)
_SENSITIVE_HEADER_RE = re.compile(
    r"(?i)(authorization|cookie|set-cookie|x-api-key)\s*[:=]\s*\S+",
)
_SENSITIVE_KV_RE = re.compile(
    r"(?i)\b(password|passwd|api_token|sessionid)\s*=\s*\S+",
)


def sanitize_url(url: str, *, secret: str | None = None) -> str:
    if not url:
        return url
    cleaned = _SENSITIVE_QUERY_RE.sub(rf"\1{REDACTED}", url)
    cleaned = _AUTH_QUERY_RE.sub(rf"\1{REDACTED}", cleaned)
    if secret:
        cleaned = cleaned.replace(secret, REDACTED)
    try:
        parsed = urlparse(cleaned)
        if parsed.query:
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            redacted_pairs = [
                (key, REDACTED if _is_sensitive_key(key) else value)
                for key, value in pairs
            ]
            cleaned = urlunparse(
                parsed._replace(query=urlencode(redacted_pairs)),
            )
    except (ValueError, TypeError):
        pass
    return cleaned


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in REDACT_KEYS:
        return True
    return lowered.endswith("_key") or lowered.endswith("_token")


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if _is_sensitive_key(str(key)):
                cleaned[key] = "REDACTED"
            else:
                cleaned[key] = redact_payload(value)
        return cleaned
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_text(payload)
    return payload


def sanitize_text(text: str, *, secret: str | None = None) -> str:
    if not text:
        return text
    cleaned = _SENSITIVE_QUERY_RE.sub(rf"\1{REDACTED}", text)
    cleaned = _AUTH_QUERY_RE.sub(rf"\1{REDACTED}", cleaned)
    cleaned = _SENSITIVE_HEADER_RE.sub(
        lambda match: f"{match.group(1)} {REDACTED}",
        cleaned,
    )
    cleaned = _SENSITIVE_KV_RE.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        cleaned,
    )
    if secret:
        cleaned = cleaned.replace(secret, REDACTED)
    return cleaned


def redact_text(text: str, secret: str | None) -> str:
    return sanitize_text(text, secret=secret)


class FinvizHTTPError(Exception):
    """HTTP error with sanitized URL — never embeds raw auth values."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        secret: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = sanitize_url(url or "", secret=secret)
        super().__init__(sanitize_text(message, secret=secret))

    def __repr__(self) -> str:
        return (
            f"FinvizHTTPError(status_code={self.status_code!r}, "
            f"url={self.url!r}, message={str(self)!r})"
        )
