"""IBKR adapter callback capture + offline replay (G6).

Capture is a safe facts-only journal: callback kind, provider reqId,
canonical instrument id, position, provider operation/side integers, price,
size, market maker, received/source timestamps, subscription generation, and
sanitized error metadata. No credentials, no account numbers, no secrets.

Replay feeds captured records back through the *adapter normalization path*
(``IbkrObservationalAdapter.on_*`` callbacks) without any live IB connection
(an offline replay subscription is registered without transport I/O), proving
``capture → adapter replay → DepthUpdate → IncrementalOrderBook`` yields the
same canonical final state/hash as direct fake callbacks.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

REDACTED = "<REDACTED>"
_SECRET_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "username",
    "account",
    "totp",
    "apikey",
    "sessionid",
)
_TEXT_SECRET = re.compile(
    r"(?i)(\b(?:authorization|proxy[-_]?authorization|set[-_]?cookie|cookie|"
    r"password|passwd|access[-_]?token|refresh[-_]?token|token|totp(?:[-_]?secret)?|"
    r"username|api[-_]?key|client[-_]?secret|account(?:[-_]?id)?)\b[\"' ]?\s*[:=]\s*[\"' ]?"
    r"(?:Bearer\s+)?)([^\"'\s&,;}]+)"
)


def _normalized_key(value: object) -> str:
    return "".join(character.lower() for character in str(value) if character.isalnum())


def _is_secret_key(value: object) -> bool:
    normalized = _normalized_key(value)
    return any(marker in normalized for marker in _SECRET_MARKERS)


def redact_text(text: str) -> str:
    return _TEXT_SECRET.sub(lambda match: f"{match.group(1)}{REDACTED}", str(text))


def redact(value: Any) -> Any:
    """Recursively redact secret-shaped keys and embedded credentials."""
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_secret_key(key) else redact(item)
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
    """Thread-safe, append-only, redacted JSONL writer."""

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


class CallbackCapture:
    """Facts-only callback journal for one adapter.

    Memory-only by default (``path=None``) so offline tests and the perf suite
    never touch disk per callback; pass a path to persist the JSONL journal.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.journal = None if path is None else JsonlJournal(path)
        self.records: list[dict[str, Any]] = []

    def record(self, payload: Mapping[str, Any]) -> None:
        entry = redact(dict(payload))
        entry["captured_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.records.append(entry)
        if self.journal is not None:
            self.journal.append(entry)

    def captured_records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.records)


def capture_depth_callback(
    *,
    callback: str,
    req_id: int,
    instrument_id: str,
    generation: int,
    position: int,
    operation: int,
    side: int,
    price: float | None,
    size: float | None,
    market_maker: str | None = None,
    is_smart_depth: bool | None = None,
    received_time_ns: int | None = None,
    source_time_ns: int | None = None,
) -> dict[str, Any]:
    """Build a safe depth-callback capture record."""
    return {
        "callback": callback,
        "callback_kind": "DEPTH",
        "generation": generation,
        "instrument_id": instrument_id,
        "is_smart_depth": is_smart_depth,
        "market_maker": market_maker,
        "operation": operation,
        "position": position,
        "price": price,
        "received_time_ns": received_time_ns,
        "req_id": req_id,
        "side": side,
        "size": size,
        "source_time_ns": source_time_ns,
    }


def capture_tick_callback(
    *,
    callback: str,
    req_id: int,
    instrument_id: str,
    generation: int,
    field: int,
    value: float | None,
    received_time_ns: int | None = None,
    source_time_ns: int | None = None,
) -> dict[str, Any]:
    """Build a safe L1 tick capture record (``tickPrice``/``tickSize``)."""
    return {
        "callback": callback,
        "callback_kind": "TICK",
        "field": field,
        "generation": generation,
        "instrument_id": instrument_id,
        "received_time_ns": received_time_ns,
        "req_id": req_id,
        "source_time_ns": source_time_ns,
        "value": value,
    }


def capture_trade_callback(
    *,
    callback: str,
    req_id: int,
    instrument_id: str,
    generation: int,
    price: float | None,
    size: float | None,
    exchange: str | None = None,
    special_conditions: str | None = None,
    tick_type: int | None = None,
    past_limit: bool | None = None,
    unreported: bool | None = None,
    received_time_ns: int | None = None,
    source_time_ns: int | None = None,
) -> dict[str, Any]:
    """Build a safe tick-by-tick trade capture record."""
    return {
        "callback": callback,
        "callback_kind": "TRADE",
        "exchange": exchange,
        "generation": generation,
        "instrument_id": instrument_id,
        "past_limit": past_limit,
        "price": price,
        "received_time_ns": received_time_ns,
        "req_id": req_id,
        "size": size,
        "source_time_ns": source_time_ns,
        "special_conditions": special_conditions,
        "tick_type": tick_type,
        "unreported": unreported,
    }


def capture_error_record(
    *,
    req_id: int | None,
    code: int | None,
    message: str,
    category: str,
    received_time_ns: int | None = None,
) -> dict[str, Any]:
    return {
        "callback": "error",
        "callback_kind": "ERROR",
        "category": category,
        "code": code,
        "message": redact_text(message)[:512],
        "received_time_ns": received_time_ns,
        "req_id": req_id,
    }


def capture_query_record(
    *,
    query_kind: str,
    instrument_id: str,
    request: Mapping[str, Any],
    response: Mapping[str, Any],
    received_time_ns: int | None = None,
) -> dict[str, Any]:
    """Build a safe read-only query capture record (G11)."""
    safe_request = redact(dict(request))
    safe_response = redact(dict(response))
    if "account" in safe_request or "accountId" in safe_request:
        safe_request = {key: REDACTED if "account" in key.lower() else value for key, value in safe_request.items()}
    return {
        "callback": "query",
        "callback_kind": "QUERY",
        "instrument_id": instrument_id,
        "query_kind": query_kind,
        "received_time_ns": received_time_ns,
        "request": safe_request,
        "response": safe_response,
    }


def replay_records(
    records: Iterable[Mapping[str, Any]],
    *,
    dispatch: Callable[[Mapping[str, Any]], Any],
) -> int:
    """Replay captured records through an adapter dispatch callable.

    ``dispatch`` receives each safe record (e.g. the adapter's
    ``on_captured_record`` handler) and must route it through the canonical
    normalization path. Returns the number of records dispatched.
    """
    count = 0
    for record in records:
        dispatch(dict(record))
        count += 1
    return count


__all__ = [
    "CallbackCapture",
    "REDACTED",
    "JsonlJournal",
    "capture_depth_callback",
    "capture_error_record",
    "capture_query_record",
    "capture_tick_callback",
    "capture_trade_callback",
    "redact",
    "redact_text",
    "replay_records",
]