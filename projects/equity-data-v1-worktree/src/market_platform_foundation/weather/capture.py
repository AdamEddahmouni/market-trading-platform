"""Credential-safe immutable capture envelopes for weather source payloads."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

WEATHER_CAPTURE_SCHEMA = "weather.capture/1.0.0"
_SENSITIVE_TOKENS = (
    "api_key",
    "apikey",
    "access_token",
    "token",
    "password",
    "authorization",
    "cookie",
    "secret",
)
_SAFE_RESPONSE_HEADERS = {"cache-control", "content-type", "etag", "expires", "last-modified"}


def sanitize_weather_payload(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(token in normalized for token in _SENSITIVE_TOKENS):
                result[str(key)] = "REDACTED"
            else:
                result[str(key)] = sanitize_weather_payload(item)
        return result
    if isinstance(value, list):
        return [sanitize_weather_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_weather_payload(item) for item in value]
    if isinstance(value, str) and "://" in value and "?" in value:
        return sanitize_request_url(value)
    return value


def sanitize_request_url(url: str) -> str:
    parsed = urlsplit(url)
    safe_query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = key.lower().replace("-", "_")
        safe_query.append(
            (key, "REDACTED" if any(token in normalized for token in _SENSITIVE_TOKENS) else value)
        )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(safe_query), ""))


def hash_weather_payload(payload: Any) -> str:
    sanitized = sanitize_weather_payload(payload)
    canonical = json.dumps(
        sanitized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_weather_capture_envelope(
    *,
    source: str,
    endpoint_family: str,
    request_url: str,
    response_payload: dict[str, Any],
    retrieved_time: str,
    provider_first_observed_time: str,
    response_headers: Mapping[str, str] | None = None,
    parser_version: str = "weather.capture.v1",
) -> dict[str, Any]:
    sanitized_payload = sanitize_weather_payload(response_payload)
    safe_headers = {
        str(key).lower(): str(value)
        for key, value in (response_headers or {}).items()
        if str(key).lower() in _SAFE_RESPONSE_HEADERS
    }
    return {
        "schema": WEATHER_CAPTURE_SCHEMA,
        "source": source,
        "endpoint_family": endpoint_family,
        "request_url": sanitize_request_url(request_url),
        "request_identity_hash": hashlib.sha256(
            sanitize_request_url(request_url).encode("utf-8")
        ).hexdigest(),
        "response_hash": hash_weather_payload(sanitized_payload),
        "provider_first_observed_time": provider_first_observed_time,
        "retrieved_time": retrieved_time,
        "response_headers": safe_headers,
        "parser_version": parser_version,
        "sanitized_response": sanitized_payload,
    }


__all__ = [
    "WEATHER_CAPTURE_SCHEMA",
    "build_weather_capture_envelope",
    "hash_weather_payload",
    "sanitize_request_url",
    "sanitize_weather_payload",
]
