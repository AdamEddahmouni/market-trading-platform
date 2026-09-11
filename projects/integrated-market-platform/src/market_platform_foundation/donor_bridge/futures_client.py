"""Stdlib HTTP client for FuturesX read-only bridge (port 8788)."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:8788"
DEFAULT_TIMEOUT = 5.0
AVAILABILITY_PROBE_TIMEOUT = 0.5
_AVAILABILITY_PROBE_CACHE_TTL_SECONDS = 2.0
_availability_probe_cache: dict[str, tuple[bool, float]] = {}


def fetch_json(path: str, *, base_url: str = DEFAULT_BASE_URL, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise ConnectionError(f"donor futures fetch failed: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"donor futures response must be object: {path}")
    return payload


def clear_availability_probe_cache() -> None:
    """Reset cached donor availability probes (test-only hook)."""

    _availability_probe_cache.clear()


def is_available(*, base_url: str = DEFAULT_BASE_URL) -> bool:
    normalized = base_url.rstrip("/")
    now = time.monotonic()
    cached = _availability_probe_cache.get(normalized)
    if cached is not None and now < cached[1]:
        return cached[0]
    try:
        payload = fetch_json(
            "/health",
            base_url=normalized,
            timeout=AVAILABILITY_PROBE_TIMEOUT,
        )
        available = payload.get("status") == "OK"
    except ConnectionError:
        available = False
    _availability_probe_cache[normalized] = (
        available,
        now + _AVAILABILITY_PROBE_CACHE_TTL_SECONDS,
    )
    return available


def fetch_health(*, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    return fetch_json("/health", base_url=base_url)


def fetch_session(*, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    return fetch_json("/api/session", base_url=base_url)


def fetch_depth_latest(*, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    return fetch_json("/api/depth/latest", base_url=base_url)


__all__ = [
    "DEFAULT_BASE_URL",
    "fetch_depth_latest",
    "fetch_health",
    "fetch_session",
    "is_available",
]
