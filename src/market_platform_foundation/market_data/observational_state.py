"""Provider-neutral live market state for L1, trades, and order books."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..clock import monotonic_wall_ns
from .book_features import compute_book_features
from .normalization import classified_trade_from_ticker, levels_from_order_book, l1_from_quote
from .live_admission import ADMISSION_BLOCKED, ADMISSION_DISPLAY


@dataclass
class QuoteSnapshot:
    instrument_id: str
    bid_price: float | None
    ask_price: float | None
    bid_size: float | None
    ask_size: float | None
    last_price: float | None
    volume: float | None
    event_time_ns: int
    available_time_ns: int
    received_ns: int
    quality: str
    provider: str
    admission: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "admission": self.admission,
            "ask_price": self.ask_price,
            "ask_size": self.ask_size,
            "available_time_ns": self.available_time_ns,
            "bid_price": self.bid_price,
            "bid_size": self.bid_size,
            "event_time_ns": self.event_time_ns,
            "instrument_id": self.instrument_id,
            "last_price": self.last_price,
            "provider": self.provider,
            "quality": self.quality,
            "received_ns": self.received_ns,
            "volume": self.volume,
        }


@dataclass
class ObservationalStateStore:
    max_trades: int = 500
    quotes: dict[str, QuoteSnapshot] = field(default_factory=dict)
    trades: dict[str, deque[dict[str, Any]]] = field(default_factory=dict)
    books: dict[str, dict[str, Any]] = field(default_factory=dict)
    metrics: dict[str, int] = field(default_factory=lambda: {
        "events_received": 0,
        "events_admitted": 0,
        "events_dropped": 0,
        "duplicates": 0,
        "classified_trades": 0,
        "unknown_aggressor": 0,
        "provider_directed": 0,
        "inferred": 0,
        "quality_rejected": 0,
    })

    def apply_admitted(self, result: dict[str, Any]) -> bool:
        self.metrics["events_received"] += 1
        if result.get("admission", {}).get("display") == ADMISSION_BLOCKED:
            self.metrics["events_dropped"] += 1
            self.metrics["quality_rejected"] += 1
            if "DUPLICATE" in result.get("quality_flags", []) or any(
                row.get("state") == "DUPLICATE" for row in result.get("observations") or [] if isinstance(row, dict)
            ):
                self.metrics["duplicates"] += 1
            return False
        envelope = result.get("envelope")
        record = result.get("record") or {}
        if not envelope:
            self.metrics["events_dropped"] += 1
            return False

        instrument_id = str(envelope.get("instrument_id") or record.get("instrument_id") or "").upper()
        capability = str(record.get("capability") or envelope.get("event_type") or "")
        payload = record.get("raw_payload") or envelope.get("payload") or {}
        admission = str(result.get("admission", {}).get("display", ADMISSION_DISPLAY))
        quality = "PASS" if admission == ADMISSION_DISPLAY else "DEGRADED"
        provider = str(record.get("provider") or "moomoo")
        clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
        received_ns = int(clocks.get("received_time_ns") or envelope.get("live_received_time") or monotonic_wall_ns())
        event_time_ns = int(envelope.get("event_time") or received_ns)
        available_ns = int(envelope.get("available_time") or received_ns)

        if "L1" in capability or "SNAPSHOT" in capability:
            l1 = l1_from_quote(payload)
            last_price = _session_last_price(payload)
            bid = None if l1 is None else l1.best_bid
            ask = None if l1 is None else l1.best_ask
            if bid is None:
                bid = _optional_float(payload, "bid_price", "best_bid")
            if ask is None:
                ask = _optional_float(payload, "ask_price", "best_ask")
            self.quotes[instrument_id] = QuoteSnapshot(
                instrument_id=instrument_id,
                bid_price=bid,
                ask_price=ask,
                bid_size=_optional_float(payload, "bid_vol", "bid_size"),
                ask_size=_optional_float(payload, "ask_vol", "ask_size"),
                last_price=last_price,
                volume=_optional_float(payload, "volume", "after_volume"),
                event_time_ns=event_time_ns,
                available_time_ns=available_ns,
                received_ns=received_ns,
                quality=quality,
                provider=provider,
                admission=admission,
            )
        elif "TICK" in capability:
            trade = classified_trade_from_ticker(payload, provider=provider)
            tape = self.trades.setdefault(instrument_id, deque(maxlen=self.max_trades))
            tape.append(
                {
                    "admission": admission,
                    "aggressor_provenance": trade.aggressor_source.value,
                    "aggressor_side": trade.aggressor_side.value.upper(),
                    "available_time_ns": available_ns,
                    "event_time_ns": event_time_ns,
                    "price": trade.price,
                    "provider": provider,
                    "quality": quality,
                    "quantity": trade.quantity,
                    "trade_id": trade.trade_id,
                }
            )
            if trade.aggressor_side.value.upper() == "UNKNOWN":
                self.metrics["unknown_aggressor"] += 1
            else:
                self.metrics["classified_trades"] += 1
            provenance = trade.aggressor_source.value
            if provenance in {"PROVIDER_NATIVE", "EXCHANGE_NATIVE"}:
                self.metrics["provider_directed"] += 1
            elif provenance == "INFERRED":
                self.metrics["inferred"] += 1
        elif "DEPTH" in capability or "ORDER_BOOK" in capability:
            bids, asks = levels_from_order_book(payload)
            features = compute_book_features(bids, asks)
            self.books[instrument_id] = {
                "admission": admission,
                "asks": asks,
                "available_time_ns": available_ns,
                "bids": bids,
                "book_features": None if features is None else features.to_dict(),
                "event_time_ns": event_time_ns,
                "provider": provider,
                "quality": quality,
                "received_ns": received_ns,
                "requested_depth": len(bids) + len(asks),
                "returned_depth": max(len(bids), len(asks)),
                "update_semantics": "SNAPSHOT",
            }
            quote = self.quotes.get(instrument_id)
            if quote is not None and bids and asks:
                if quote.bid_price is None:
                    quote.bid_price = float(bids[0]["price"])
                    quote.bid_size = float(bids[0]["size"])
                if quote.ask_price is None:
                    quote.ask_price = float(asks[0]["price"])
                    quote.ask_size = float(asks[0]["size"])

        self.metrics["events_admitted"] += 1
        return True

    def quote_for(self, instrument_id: str) -> QuoteSnapshot | None:
        return self.quotes.get(instrument_id.upper())

    def trades_for(self, instrument_id: str) -> list[dict[str, Any]]:
        tape = self.trades.get(instrument_id.upper())
        return list(tape) if tape else []

    def book_for(self, instrument_id: str) -> dict[str, Any] | None:
        return self.books.get(instrument_id.upper())

    def freshness_ms(self, instrument_id: str, *, wall_now_ns: int | None = None) -> int | None:
        quote = self.quote_for(instrument_id)
        if quote is None:
            return None
        now = wall_now_ns if wall_now_ns is not None else monotonic_wall_ns()
        return max(0, (now - quote.received_ns) // 1_000_000)

    def metrics_report(self) -> dict[str, Any]:
        return dict(self.metrics)

    def clear_instrument(self, instrument_id: str) -> None:
        key = instrument_id.upper()
        self.quotes.pop(key, None)
        self.trades.pop(key, None)
        self.books.pop(key, None)


def _session_last_price(payload: dict[str, Any]) -> float | None:
    last = _optional_float(payload, "last_price", "last")
    after = _optional_float(payload, "after_price")
    overnight = _optional_float(payload, "overnight_price")
    pre = _optional_float(payload, "pre_price")
    data_time = str(payload.get("data_time") or "")
    if after is not None and data_time.startswith("16:00"):
        return after
    if overnight is not None and data_time.startswith("20:00"):
        return overnight
    if pre is not None and len(data_time) >= 2 and data_time[:2] < "09":
        return pre
    return last if last is not None else after or overnight or pre


def _optional_float(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None
