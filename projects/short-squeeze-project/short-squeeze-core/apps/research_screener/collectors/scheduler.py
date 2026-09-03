from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .base import EvidenceCollector
from .cache_log import log_collector_event
from .config import CollectorConfig
from .merge import extract_headlines
from .store import EvidenceStore

_BUCKET_WEIGHT = {
    "SHORT_PRESSURE_INPUTS_MISSING": 50,
    "FLOAT_OR_SHARE_BASIS_MISSING": 40,
    "CATALYST_INPUTS_MISSING": 30,
    "VOLUME_INPUTS_MISSING": 20,
    "PRICE_OR_QUOTE_INPUTS_MISSING": 10,
}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class CollectorScheduler:
    def __init__(
        self,
        *,
        config: CollectorConfig,
        store: EvidenceStore,
        collectors: list[EvidenceCollector],
        universe_fn: Callable[[], list[str]],
        gap_buckets_fn: Callable[[str], list[str]],
        on_headlines: Callable[[str, list[dict[str, Any]]], None] | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._collectors = collectors
        self._universe_fn = universe_fn
        self._gap_buckets_fn = gap_buckets_fn
        self._on_headlines = on_headlines
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._requests_this_minute = 0
        self._minute_start = time.time()
        self._last_tick_at: str | None = None
        self._last_symbols: list[str] = []
        self._last_target_bucket: str | None = None
        self._last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if not self._config.enabled or not self._collectors:
            return
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="collector-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self._config.enabled,
            "running": self.running,
            "tick_seconds": self._config.tick_seconds,
            "last_tick_at": self._last_tick_at,
            "symbols_last_tick": self._last_symbols,
            "top_gap_bucket": self._last_target_bucket,
            "last_error": self._last_error,
            "collectors": [
                {
                    "name": c.name,
                    "configured": c.configured,
                    "capabilities": c.capabilities,
                    "rate_limit_state": c.rate_limit_state,
                }
                for c in self._collectors
            ],
            "store": self._store.snapshot(),
        }

    def _rate_limit_ok(self) -> bool:
        now = time.time()
        if now - self._minute_start >= 60:
            self._minute_start = now
            self._requests_this_minute = 0
        if self._requests_this_minute >= self._config.max_requests_per_minute:
            return False
        self._requests_this_minute += 1
        return True

    def _prioritize(self, symbols: list[str]) -> list[str]:
        scored: list[tuple[float, str]] = []
        for symbol in symbols:
            buckets = self._gap_buckets_fn(symbol)
            score = sum(_BUCKET_WEIGHT.get(b, 1) for b in buckets)
            scored.append((score, symbol))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [symbol for _score, symbol in scored]

    def _tick(self) -> None:
        if not self._rate_limit_ok():
            return
        universe = [s.strip().upper() for s in self._universe_fn() if s.strip()]
        if not universe:
            return
        ordered = self._prioritize(universe)
        batch = ordered[: self._config.max_symbols_per_tick]
        self._last_symbols = batch
        if batch:
            top_buckets = self._gap_buckets_fn(batch[0])
            self._last_target_bucket = top_buckets[0] if top_buckets else None

        for collector in self._collectors:
            if not collector.configured:
                continue
            try:
                records = collector.poll(batch)
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"{collector.name}: {type(exc).__name__}: {exc}"
                continue
            if not records:
                continue
            added = self._store.merge(records)
            log_collector_event(
                {
                    "event": "collector_poll",
                    "collector": collector.name,
                    "symbols": batch,
                    "records_added": added,
                }
            )
            if self._on_headlines:
                by_symbol: dict[str, list[Any]] = {}
                for record in records:
                    by_symbol.setdefault(record.symbol, []).append(record)
                for symbol, sym_records in by_symbol.items():
                    headlines = extract_headlines(sym_records)
                    if headlines:
                        self._on_headlines(symbol, headlines)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
                self._last_tick_at = _now_iso()
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"{type(exc).__name__}: {exc}"
            self._stop.wait(self._config.tick_seconds)


__all__ = ["CollectorScheduler"]
