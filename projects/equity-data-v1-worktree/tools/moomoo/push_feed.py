"""Moomoo OpenD push callback feed — quote-only, no trade context.

Runtime split:
- Push callbacks: QUOTE, TICKER, ORDER_BOOK (high cadence)
- Polling remains: capability probe, OpenD reachability, subscription sync, reconnect, diagnostics
Callbacks enqueue a minimal envelope and return. Normalization/admission run on the ingest thread.
"""

from __future__ import annotations

import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.bounded_queue import BoundedIngestQueue, drain_queue_worker
from market_platform_foundation.market_data.connectivity import opend_reachable
from market_platform_foundation.market_data.live_config import (
    ingest_queue_max_size,
    moomoo_host,
    moomoo_port,
    reconnect_backoff_seconds,
)
from market_platform_foundation.market_data.provider_time import (
    classify_first_push,
    event_time_ns_from_payload,
    is_provider_cached_push,
)
from market_platform_foundation.market_data.subscription_manager import LiveSubscriptionManager

KNOWN_INSTRUMENTS: dict[str, dict[str, str]] = {
    "AAPL": {"provider_symbol": "US.AAPL", "venue_id": "US_EQUITY"},
    "NVDA": {"provider_symbol": "US.NVDA", "venue_id": "US_EQUITY"},
    "MSFT": {"provider_symbol": "US.MSFT", "venue_id": "US_EQUITY"},
    "TSLA": {"provider_symbol": "US.TSLA", "venue_id": "US_EQUITY"},
    "SPY": {"provider_symbol": "US.SPY", "venue_id": "US_EQUITY"},
}

CAP_TO_SUBTYPE_NAME = {
    "US_EQUITY_L1": "QUOTE",
    "US_EQUITY_TICKS": "TICKER",
    "US_EQUITY_DEPTH": "ORDER_BOOK",
}


def payload_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if hasattr(data, "to_dict") and hasattr(data, "columns"):
        records = data.to_dict(orient="records")
        return [dict(row) for row in records]
    if isinstance(data, list):
        rows: list[dict[str, Any]] = []
        for item in data:
            if hasattr(item, "to_dict") and not hasattr(item, "columns"):
                rows.append(dict(item.to_dict()))
            elif isinstance(item, dict):
                rows.append(item)
        return rows
    if isinstance(data, dict):
        return [data]
    return []


def _percentile_ms(samples: list[int], p: float) -> int | None:
    if not samples:
        return None
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, int(len(ordered) * p))
    return ordered[idx] // 1_000_000


@dataclass
class MoomooPushFeed:
    subscriptions: LiveSubscriptionManager
    on_record: Callable[[dict[str, Any]], None]
    on_connected: Callable[[], None] | None = None
    on_disconnected: Callable[[str], None] | None = None
    on_reconnecting: Callable[[], None] | None = None
    on_overflow: Callable[[], None] | None = None
    provider_generation: int = 0
    queue: BoundedIngestQueue[dict[str, Any]] = field(
        default_factory=lambda: BoundedIngestQueue(max_size=ingest_queue_max_size())
    )
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _connection_thread: threading.Thread | None = field(default=None, repr=False)
    _processor_thread: threading.Thread | None = field(default=None, repr=False)
    _subscribed_subtypes: set[tuple[str, str]] = field(default_factory=set, repr=False)
    _lag_samples: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list), repr=False)
    _processing_lag_ns: list[int] = field(default_factory=list, repr=False)
    _first_push_seen: set[str] = field(default_factory=set, repr=False)
    _duplicate_callbacks: int = 0
    _sequence_anomalies: int = 0
    _last_sequence: dict[str, int] = field(default_factory=dict, repr=False)
    _handler_errors: int = 0
    last_error: str | None = None
    trade_api_counters: dict[str, int] = field(
        default_factory=lambda: {
            "broker_cancels": 0,
            "broker_modifications": 0,
            "broker_orders_submitted": 0,
            "trade_contexts_created": 0,
            "trade_unlock_calls": 0,
        }
    )

    def start(self) -> None:
        if self._connection_thread and self._connection_thread.is_alive():
            return
        self._stop_event.clear()
        self._processor_thread = threading.Thread(
            target=drain_queue_worker,
            kwargs={
                "queue": self.queue,
                "stop_event": self._stop_event,
                "handler": self._process_envelope,
            },
            name="moomoo-ingest-processor",
            daemon=True,
        )
        self._processor_thread.start()
        self._connection_thread = threading.Thread(target=self._connection_loop, name="moomoo-push-feed", daemon=True)
        self._connection_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def metrics(self) -> dict[str, Any]:
        quote_lag = list(self._lag_samples.get("US_EQUITY_L1") or [])
        trade_lag = list(self._lag_samples.get("US_EQUITY_TICKS") or [])
        book_lag = list(self._lag_samples.get("US_EQUITY_DEPTH") or [])
        processing = list(self._processing_lag_ns)
        return {
            **self.queue.metrics(),
            "callback_lag_ms_max": _percentile_ms(quote_lag + trade_lag + book_lag, 1.0),
            "callback_lag_ms_p50": _percentile_ms(quote_lag + trade_lag + book_lag, 0.5),
            "callback_lag_ms_p95": _percentile_ms(quote_lag + trade_lag + book_lag, 0.95),
            "duplicate_callbacks": self._duplicate_callbacks,
            "processing_lag_ms_p50": _percentile_ms(processing, 0.5),
            "processing_lag_ms_p95": _percentile_ms(processing, 0.95),
            "provider_generation": self.provider_generation,
            "quote_lag_ms_p50": _percentile_ms(quote_lag, 0.5),
            "quote_lag_ms_p95": _percentile_ms(quote_lag, 0.95),
            "quote_lag_ms_max": _percentile_ms(quote_lag, 1.0),
            "quote_lag_samples": len(quote_lag),
            "sequence_anomalies": self._sequence_anomalies,
            "trade_lag_ms_p50": _percentile_ms(trade_lag, 0.5),
            "trade_lag_ms_p95": _percentile_ms(trade_lag, 0.95),
            "trade_lag_ms_max": _percentile_ms(trade_lag, 1.0),
            "trade_lag_samples": len(trade_lag),
            "book_lag_ms_p50": _percentile_ms(book_lag, 0.5),
            "book_lag_ms_p95": _percentile_ms(book_lag, 0.95),
            "book_lag_ms_max": _percentile_ms(book_lag, 1.0),
            "book_lag_samples": len(book_lag),
            "handler_errors": self._handler_errors,
            "trade_api_counters": dict(self.trade_api_counters),
        }

    def _connection_loop(self) -> None:
        attempt = 0
        while not self._stop_event.is_set():
            if not opend_reachable():
                self.last_error = f"OpenD not reachable at {moomoo_host()}:{moomoo_port()}"
                if self.on_disconnected:
                    self.on_disconnected(self.last_error)
                time.sleep(reconnect_backoff_seconds(attempt))
                attempt += 1
                continue
            if self.on_reconnecting and attempt > 0:
                self.on_reconnecting()
            try:
                self._run_session()
                attempt = 0
            except Exception as exc:
                self.last_error = str(exc)
                if self.on_disconnected:
                    self.on_disconnected(self.last_error)
                time.sleep(reconnect_backoff_seconds(attempt))
                attempt += 1

    def _run_session(self) -> None:
        import moomoo as ft

        self.provider_generation += 1
        self._subscribed_subtypes.clear()
        self._first_push_seen.clear()
        self._last_sequence.clear()
        quote_ctx = ft.OpenQuoteContext(host=moomoo_host(), port=moomoo_port())
        generation = self.provider_generation
        seen_ids: set[str] = set()
        self_outer = self

        class QuoteHandler(ft.StockQuoteHandlerBase):
            def on_recv_rsp(self, rsp_pb):  # type: ignore[no-untyped-def]
                ret, data = super().on_recv_rsp(rsp_pb)
                if ret != ft.RET_OK:
                    return ret, data
                for payload in payload_rows(data):
                    self_outer._enqueue_from_payload(
                        capability="US_EQUITY_L1",
                        payload=payload,
                        generation=generation,
                    )
                return ret, data

        class TickerHandler(ft.TickerHandlerBase):
            def on_recv_rsp(self, rsp_pb):  # type: ignore[no-untyped-def]
                ret, data = super().on_recv_rsp(rsp_pb)
                if ret != ft.RET_OK:
                    return ret, data
                for payload in payload_rows(data):
                    instrument = str(payload.get("code") or "").split(".")[-1]
                    seq = payload.get("sequence")
                    identity = f"{instrument}:{seq}"
                    if seq is not None and identity in seen_ids:
                        self_outer._duplicate_callbacks += 1
                    if seq is not None:
                        try:
                            current = int(seq)
                            prior = self_outer._last_sequence.get(instrument)
                            if prior is not None and 1 < current - prior < 10_000:
                                self_outer._sequence_anomalies += 1
                            self_outer._last_sequence[instrument] = current
                        except (TypeError, ValueError):
                            pass
                        seen_ids.add(identity)
                    self_outer._enqueue_from_payload(
                        capability="US_EQUITY_TICKS",
                        payload=payload,
                        generation=generation,
                        sequence=seq,
                    )
                return ret, data

        class BookHandler(ft.OrderBookHandlerBase):
            def on_recv_rsp(self, rsp_pb):  # type: ignore[no-untyped-def]
                ret, data = super().on_recv_rsp(rsp_pb)
                if ret != ft.RET_OK:
                    return ret, data
                payload = data if isinstance(data, dict) else {}
                self_outer._enqueue_from_payload(
                    capability="US_EQUITY_DEPTH",
                    payload=payload,
                    generation=generation,
                )
                return ret, data

        quote_ctx.set_handler(QuoteHandler())
        quote_ctx.set_handler(TickerHandler())
        quote_ctx.set_handler(BookHandler())
        if self.on_connected:
            self.on_connected()
        try:
            while not self._stop_event.is_set():
                if not opend_reachable():
                    raise RuntimeError("OPEND_UNREACHABLE")
                self._sync_subscriptions(quote_ctx, ft)
                time.sleep(0.5)
        finally:
            quote_ctx.close()

    def _sync_subscriptions(self, quote_ctx: Any, ft: Any) -> None:
        subtype_map = {
            "QUOTE": ft.SubType.QUOTE,
            "TICKER": ft.SubType.TICKER,
            "ORDER_BOOK": ft.SubType.ORDER_BOOK,
        }
        desired: set[tuple[str, str]] = set()
        for row in self.subscriptions.active_subscriptions():
            instrument = row["instrument_id"]
            cap = row["capability"]
            code = KNOWN_INSTRUMENTS.get(instrument, {}).get("provider_symbol") or f"US.{instrument}"
            subtype_name = CAP_TO_SUBTYPE_NAME.get(cap)
            if subtype_name:
                desired.add((code, subtype_name))
        for code, subtype_name in desired - self._subscribed_subtypes:
            ret, _msg = quote_ctx.subscribe(
                [code],
                [subtype_map[subtype_name]],
                is_first_push=True,
                subscribe_push=True,
                session=ft.Session.ALL,
            )
            if ret == ft.RET_OK:
                self._subscribed_subtypes.add((code, subtype_name))
        quote_codes = sorted({code for code, subtype in self._subscribed_subtypes if subtype == "QUOTE"})
        if quote_codes:
            ret_q, quote_data = quote_ctx.get_stock_quote(quote_codes)
            if ret_q == ft.RET_OK:
                for payload in payload_rows(quote_data):
                    self._enqueue_from_payload(
                        capability="US_EQUITY_L1",
                        payload=payload,
                        generation=self.provider_generation,
                    )
        for code, subtype_name in self._subscribed_subtypes - desired:
            quote_ctx.unsubscribe([code], [subtype_map[subtype_name]])
            self._subscribed_subtypes.discard((code, subtype_name))

    def _enqueue_from_payload(
        self,
        *,
        capability: str,
        payload: dict[str, Any],
        generation: int,
        sequence: Any | None = None,
    ) -> None:
        code = str(payload.get("code") or "")
        instrument = code.split(".")[-1] if code else ""
        received = time.time_ns()
        event_ns = event_time_ns_from_payload(payload, received_ns=received)
        channel = f"{generation}:{instrument}:{capability}"
        is_first = channel not in self._first_push_seen
        if is_first:
            self._first_push_seen.add(channel)
        first_kind = classify_first_push(is_first=is_first, event_ns=event_ns, received_ns=received)
        if is_provider_cached_push(payload):
            first_kind = "CACHED"
        lag = max(0, received - event_ns)
        bucket = self._lag_samples[capability]
        bucket.append(lag)
        if len(bucket) > 500:
            del bucket[:-500]
        record = {
            "capability": capability,
            "clocks": {
                "event_time_ns": event_ns,
                "provider_time_ns": event_ns,
                "received_time_ns": received,
                "ingested_time_ns": received,
            },
            "first_push_class": first_kind,
            "instrument_id": instrument.upper(),
            "is_cached": first_kind == "CACHED",
            "is_first_push": is_first,
            "provider": "moomoo",
            "provider_generation": generation,
            "provider_symbol": code,
            "raw_payload": payload,
            "sequence": sequence if sequence is not None else received,
        }
        if not self.queue.enqueue(record) and self.on_overflow:
            self.on_overflow()

    def _process_envelope(self, record: dict[str, Any]) -> None:
        clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
        ingested = int(clocks.get("ingested_time_ns") or time.time_ns())
        self._processing_lag_ns.append(max(0, time.time_ns() - ingested))
        if len(self._processing_lag_ns) > 500:
            self._processing_lag_ns = self._processing_lag_ns[-500:]
        try:
            self.on_record(record)
        except Exception:
            self._handler_errors += 1
