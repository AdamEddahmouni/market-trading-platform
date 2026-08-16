"""Stdlib HTTP client for short-squeeze integration API (read-only)."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:8787"
DEFAULT_TIMEOUT = 5.0


def fetch_json(path: str, *, base_url: str = DEFAULT_BASE_URL, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise ConnectionError(f"donor squeeze fetch failed: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"donor squeeze response must be object: {path}")
    return payload


def fetch_manifest(*, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    envelope = fetch_json("/api/v1/integration/manifest", base_url=base_url)
    data = envelope.get("data", envelope)
    if not isinstance(data, dict):
        raise ValueError("integration manifest data must be object")
    return data


def fetch_frozen_candidates(*, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    envelope = fetch_json("/api/frozen/candidates", base_url=base_url)
    if "rows" in envelope:
        return envelope
    data = envelope.get("data", envelope)
    if not isinstance(data, dict):
        raise ValueError("frozen candidates data must be object")
    return data


def fetch_frozen_candidate_detail(
    symbol: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    encoded = symbol.strip().upper()
    if not encoded:
        raise ValueError("symbol is required")
    envelope = fetch_json(f"/api/frozen/candidate/{encoded}", base_url=base_url)
    data = envelope.get("data", envelope)
    if not isinstance(data, dict):
        raise ValueError("frozen candidate detail data must be object")
    return data


def is_available(*, base_url: str = DEFAULT_BASE_URL) -> bool:
    try:
        envelope = fetch_json("/health", base_url=base_url)
        return envelope.get("status") == "OK"
    except ConnectionError:
        return False
