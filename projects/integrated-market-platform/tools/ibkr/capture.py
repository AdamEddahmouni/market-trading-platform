"""Conservative redaction and append-only JSONL evidence capture."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REDACTED = "<REDACTED>"
_SECRET_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "username",
    "totp",
    "apikey",
    "sessionid",
)
_TEXT_SECRET = re.compile(
    r"(?i)(\b(?:authorization|proxy[-_]?authorization|set[-_]?cookie|cookie|"
    r"password|passwd|access[-_]?token|refresh[-_]?token|token|totp(?:[-_]?secret)?|"
    r"username|api[-_]?key|client[-_]?secret)\b[\"']?\s*[:=]\s*[\"']?"
    r"(?:Bearer\s+)?)([^\"'\s&,;}]+)"
)


def _normalized_key(value: object) -> str:
    return "".join(character.lower() for character in str(value) if character.isalnum())


def _secret_key(value: object) -> bool:
    normalized = _normalized_key(value)
    return any(marker in normalized for marker in _SECRET_MARKERS)


def redact_text(text: str) -> str:
    """Redact common JSON, header, key/value, and query-string secret shapes."""

    return _TEXT_SECRET.sub(lambda match: f"{match.group(1)}{REDACTED}", str(text))


def redact(value: Any) -> Any:
    """Recursively redact secret-shaped keys and embedded textual credentials."""

    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _secret_key(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


class JsonlJournal:
    """Thread-safe, append-only UTF-8 JSONL writer with mandatory redaction."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: Mapping[str, object]) -> None:
        line = json.dumps(
            redact(dict(record)),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line + "\n")
                stream.flush()
                os.fsync(stream.fileno())


class ObservationCapture:
    """Serialize gateway responses without admitting them to research data."""

    def __init__(self, path: Path) -> None:
        self.journal = JsonlJournal(path)

    def record(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, object] | None,
        request_body: Mapping[str, object] | None,
        status: int,
        headers: Mapping[str, str],
        response_payload: object,
        provider: str = "IBKR_CLIENT_PORTAL_GATEWAY",
    ) -> None:
        self.journal.append(
            {
                "schema_version": "1.0",
                "classification": "CAPTURED_NOT_ADMITTED",
                "provider": provider,
                "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "request": {
                    "method": method,
                    "path": path,
                    "params": dict(params or {}),
                    "body": dict(request_body) if request_body is not None else None,
                },
                "response": {
                    "status": status,
                    "headers": dict(headers),
                    "payload": response_payload,
                },
            }
        )


__all__ = ["JsonlJournal", "ObservationCapture", "REDACTED", "redact", "redact_text"]
