"""Typed outbound dispatch policy hooks for agent enrichment workers (Lane A extends)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

DEFAULT_OUTBOUND_TIMEOUT_SECONDS = 30.0
DEFAULT_OUTBOUND_MAX_RETRIES = 2

_ALLOWED_OUTBOUND_SCHEMES = frozenset({"https"})
_FORBIDDEN_OUTBOUND_HEADERS = frozenset(
    {
        "authorization",
        "x-api-key",
        "api-key",
        "cookie",
        "set-cookie",
    }
)


@dataclass(frozen=True, slots=True)
class OutboundDispatchPolicy:
    allowed_schemes: frozenset[str] = _ALLOWED_OUTBOUND_SCHEMES
    timeout_seconds: float = DEFAULT_OUTBOUND_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_OUTBOUND_MAX_RETRIES
    require_tls: bool = True


def load_outbound_dispatch_policy() -> OutboundDispatchPolicy:
    timeout = float(os.environ.get("IMP_INTELLIGENCE_OUTBOUND_TIMEOUT_SECONDS", DEFAULT_OUTBOUND_TIMEOUT_SECONDS))
    retries = int(os.environ.get("IMP_INTELLIGENCE_OUTBOUND_MAX_RETRIES", DEFAULT_OUTBOUND_MAX_RETRIES))
    if timeout <= 0:
        raise ValueError("INTELLIGENCE_OUTBOUND_TIMEOUT_INVALID")
    if retries < 0:
        raise ValueError("INTELLIGENCE_OUTBOUND_RETRIES_INVALID")
    return OutboundDispatchPolicy(timeout_seconds=timeout, max_retries=retries)


def validate_outbound_target_url(url: str, *, policy: OutboundDispatchPolicy | None = None) -> None:
    resolved = policy or load_outbound_dispatch_policy()
    parsed = urlparse(str(url).strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in resolved.allowed_schemes:
        raise ValueError("INTELLIGENCE_OUTBOUND_URL_SCHEME_FORBIDDEN")
    if resolved.require_tls and scheme != "https":
        raise ValueError("INTELLIGENCE_OUTBOUND_TLS_REQUIRED")


def validate_outbound_request_headers(headers: Mapping[str, str]) -> None:
    for key in headers:
        if str(key).lower() in _FORBIDDEN_OUTBOUND_HEADERS:
            raise ValueError("INTELLIGENCE_OUTBOUND_SECRET_HEADER_FORBIDDEN")


__all__ = [
    "DEFAULT_OUTBOUND_MAX_RETRIES",
    "DEFAULT_OUTBOUND_TIMEOUT_SECONDS",
    "OutboundDispatchPolicy",
    "load_outbound_dispatch_policy",
    "validate_outbound_request_headers",
    "validate_outbound_target_url",
]
