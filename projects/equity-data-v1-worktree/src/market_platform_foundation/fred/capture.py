"""Evidence capture envelopes for FRED requests — no credentials."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_fred_envelope(
    *,
    api_version: str,
    endpoint_family: str,
    series_id: str = "",
    release_id: int | None = None,
    retrieval_time: str,
    request_semantics: dict[str, Any],
    response_payload: dict[str, Any],
    record_count: int,
    page_count: int = 1,
    cursor_complete: bool = True,
    schema_version: str = "fred_capture.v1",
) -> dict[str, Any]:
    return {
        "source": "fred_alfred",
        "api_version": api_version,
        "endpoint_family": endpoint_family,
        "series_id": series_id,
        "release_id": release_id,
        "retrieval_time": retrieval_time,
        "request_semantics": request_semantics,
        "response_hash": hash_payload(response_payload),
        "record_count": record_count,
        "page_count": page_count,
        "cursor_complete": cursor_complete,
        "schema_version": schema_version,
    }


__all__ = ["build_fred_envelope", "hash_payload"]
