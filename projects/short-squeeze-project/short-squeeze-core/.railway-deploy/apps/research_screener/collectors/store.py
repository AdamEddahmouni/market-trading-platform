from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any

from .models import CollectorRecord


class EvidenceStore:
    """Thread-safe in-memory index of collector records per symbol."""

    def __init__(self, *, default_ttl_s: int = 3600) -> None:
        self._lock = threading.RLock()
        self._by_symbol: dict[str, list[CollectorRecord]] = {}
        self._ttl_by_source: dict[str, int] = {}
        self._default_ttl_s = max(1, int(default_ttl_s))
        self._seen_keys: dict[str, float] = {}

    def set_source_ttl(self, source_id: str, ttl_s: int) -> None:
        with self._lock:
            self._ttl_by_source[source_id] = max(1, int(ttl_s))

    def merge(self, records: list[CollectorRecord]) -> int:
        if not records:
            return 0
        added = 0
        now = time.time()
        with self._lock:
            for record in records:
                key = record.dedupe_key or (
                    f"{record.source_id}:{record.symbol}:"
                    f"{record.received_at}:{hash(tuple(sorted(record.payload.items())))}"
                )
                if key in self._seen_keys and (now - self._seen_keys[key]) < 30:
                    continue
                self._seen_keys[key] = now
                bucket = self._by_symbol.setdefault(record.symbol.upper(), [])
                bucket.append(record)
                added += 1
            self._prune_locked(now)
        return added

    def get(self, symbol: str) -> list[CollectorRecord]:
        symbol = symbol.strip().upper()
        now = time.time()
        with self._lock:
            self._prune_locked(now)
            return list(self._by_symbol.get(symbol, []))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            symbols = sorted(self._by_symbol)
            return {
                "symbol_count": len(symbols),
                "record_count": sum(len(v) for v in self._by_symbol.values()),
                "symbols": symbols,
            }

    def symbol_detail(self, symbol: str) -> dict[str, Any]:
        records = self.get(symbol)
        return {
            "symbol": symbol.strip().upper(),
            "records": [
                {
                    "source_id": r.source_id,
                    "received_at": r.received_at,
                    "field_hints": r.field_hints,
                    "payload": r.payload,
                }
                for r in records
            ],
        }

    def _record_age_seconds(self, record: CollectorRecord, now: float) -> float:
        try:
            received = record.received_at.replace("Z", "+00:00")
            ts = datetime.fromisoformat(received).timestamp()
            return max(0.0, now - ts)
        except (ValueError, TypeError, OSError):
            return float(self._default_ttl_s) + 1.0

    def _prune_locked(self, now: float) -> None:
        for symbol, records in list(self._by_symbol.items()):
            kept: list[CollectorRecord] = []
            for record in records:
                ttl = self._ttl_by_source.get(record.source_id, self._default_ttl_s)
                if self._record_age_seconds(record, now) <= ttl:
                    kept.append(record)
            if kept:
                self._by_symbol[symbol] = kept
            else:
                self._by_symbol.pop(symbol, None)


__all__ = ["EvidenceStore"]
