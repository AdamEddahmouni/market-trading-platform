"""Stdlib HTTP client for FuturesX read-only bridge (port 8788)."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:8788"
DEFAULT_TIMEOUT = 5.0


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


def is_available(*, base_url: str = DEFAULT_BASE_URL) -> bool:
    try:
        payload = fetch_json("/health", base_url=base_url)
    except ConnectionError:
        return False
    return payload.get("status") == "OK"


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
