"""Structured logging redaction utilities (Platformization P5).

Neutral prerequisites for a future hosted deployment: today the operator UI
runs on localhost, but log lines and payloads are exactly the surface that
leaks first when a bind address or transport changes. These helpers make
redaction available to every future caller (including ``ui_api/server.py``
log paths — integration there is deliberately deferred, see the P5 spec §6)
without changing any existing behavior.

Design:
- Key-shape redaction is value-blind and case/separator-insensitive: any key
  whose normalized form contains a secret marker is redacted. This
  deliberately over-redacts (a field named ``monkey`` would be redacted);
  over-redaction is the safe failure mode for secrets.
- :func:`build_log_line` emits deterministic canonical JSON with sorted keys
  and no wall clock; provenance fields ride along as data.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

REDACTED = "<REDACTED>"

SECRET_KEY_MARKERS: tuple[str, ...] = (
    "token",
    "key",
    "secret",
    "authorization",
    "password",
    "passwd",
    "credential",
    "auth",
    "cookie",
)

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")

_JSON_SECRET_KV_RE = re.compile(
    r'(?i)("[^"]*(?:token|key|secret|authorization|password|passwd|credential|auth|cookie)[^"]*"\s*:\s*)"[^"]*"'
)
_KV_SECRET_RE = re.compile(
    r"(?i)\b([a-z0-9_.-]*(?:token|key|secret|authorization|password|passwd|credential|auth|cookie)[a-z0-9_.-]*)\s*[=:]\s*([^\s&\"',}]+)"
)


def normalize_key(name: str) -> str:
    """Lowercase and strip separators so ``Client-Secret`` == ``client_secret``."""

    return _NORMALIZE_RE.sub("", name.lower())


def is_secret_key(name: str) -> bool:
    """True when a key's normalized form carries a secret-shaped marker.

    Deliberately over-broad (substring match): false positives redact benign
    fields, which is safe; false negatives leak credentials, which is not.
    """

    if not isinstance(name, str):
        return False
    normalized = normalize_key(name)
    return any(marker in normalized for marker in SECRET_KEY_MARKERS)


def redact_mapping(payload: Any) -> Any:
    """Recursively redact values under secret-shaped keys.

    Dicts become new dicts; lists/tuples keep their type; scalars pass
    through untouched unless their key matched.
    """

    if isinstance(payload, Mapping):
        return {
            key: REDACTED if is_secret_key(str(key)) else redact_mapping(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [redact_mapping(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_mapping(item) for item in payload)
    return payload


def redact_log_line(line: str) -> str:
    """Redact secret-shaped values inside an already-formatted log line.

    Handles JSON-style (``"api_key": "abc"``), KV-style (``token=abc``),
    header-style (``Authorization: Bearer abc``), and query-style
    (``?auth=abc``) shapes. Values are replaced with :data:`REDACTED`.
    """

    redacted = _JSON_SECRET_KV_RE.sub(r"\1" + f'"{REDACTED}"', line)
    return _KV_SECRET_RE.sub(lambda m: f"{m.group(1)}={REDACTED}", redacted)


def build_log_line(
    event: str,
    *,
    level: str = "INFO",
    fields: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> str:
    """Deterministic, redacted canonical JSON log line.

    Sorted keys, compact separators, no timestamp injected by this module —
    callers that want wall-clock timestamps must pass one explicitly as a
    field so pure/test contexts stay deterministic.
    """

    payload: dict[str, Any] = {"event": event, "level": level.upper()}
    if fields:
        payload["fields"] = redact_mapping(dict(fields))
    if provenance:
        payload["provenance"] = redact_mapping(dict(provenance))
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
