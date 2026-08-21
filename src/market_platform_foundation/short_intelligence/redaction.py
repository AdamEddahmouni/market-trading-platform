"""Never persist or log FINRA tokens, Basic/Bearer headers, or client secrets."""

from __future__ import annotations

from typing import Any

from ..credential_audit import SECRET_SCAN_RULES, scan_redacted_bytes

REDACT_KEYS = {
    "access_token",
    "client_secret",
    "client_id",
    "authorization",
    "finra_client_id",
    "finra_client_secret",
    "resultlink",
    "result_link",
}


def redact_mapping(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in REDACT_KEYS:
                cleaned[key] = "REDACTED"
            else:
                cleaned[key] = redact_mapping(value)
        return cleaned
    if isinstance(payload, list):
        return [redact_mapping(item) for item in payload]
    if isinstance(payload, str) and payload.lower().startswith(("bearer ", "basic ")):
        return "REDACTED"
    return payload


def evidence_contains_secrets(payload: bytes) -> bool:
    return bool(scan_redacted_bytes(payload, "PATH-EVIDENCE", "WORKTREE", SECRET_SCAN_RULES))
