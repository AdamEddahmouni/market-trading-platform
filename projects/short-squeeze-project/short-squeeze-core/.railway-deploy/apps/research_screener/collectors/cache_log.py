from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _cache_dir() -> Path:
    from ..paths import repository_root

    return repository_root() / "data" / "collector_cache"


_log_lock = threading.Lock()
_enabled = os.environ.get("COLLECTOR_CACHE_ENABLED", "true").lower() not in (
    "false",
    "0",
    "no",
    "off",
)


def log_collector_event(event: dict[str, Any]) -> None:
    if not _enabled:
        return
    payload = {"logged_at": _now_iso(), **event}
    path = _cache_dir() / f"events_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.jsonl"
    with _log_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


__all__ = ["log_collector_event"]
