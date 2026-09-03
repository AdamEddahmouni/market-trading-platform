"""Sanitized EIA evidence capture envelopes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .redaction import sanitize_response_payload


def capture_envelope(
    *,
    route: str,
    params: dict[str, Any],
    response: dict[str, Any],
    parser_version: str = "eia.capture.v1",
) -> dict[str, Any]:
    sanitized = sanitize_response_payload(response)
    canonical = json.dumps(sanitized, sort_keys=True, separators=(",", ":"))
    return {
        "source": "eia",
        "route": route,
        "params": {key: value for key, value in params.items() if key != "api_key"},
        "response_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "record_count": len(sanitized.get("response", {}).get("data", []) or []),
        "parser_version": parser_version,
        "sanitized_response": sanitized,
    }


__all__ = ["capture_envelope"]
