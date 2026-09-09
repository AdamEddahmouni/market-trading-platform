"""Provider-neutral live market state for L1, trades, and order books."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..clock import monotonic_wall_ns
from ..order_flow.order_book.engine import IncrementalOrderBook
from ..order_flow.order_book.freshness import FreshnessPolicy, evaluate_book_freshness
from ..order_flow.order_book.projection import project_book_snapshot
from .book_features import compute_book_features
from .depth_admission import DepthAdmissionContext, DepthAdmissibilityResult, evaluate_depth_admissibility
from .live_config import depth_freshness_policy
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
    last_size: float | None = None
    volume: float | None = None
    event_time_ns: int = 0
    available_time_ns: int = 0
    received_ns: int = 0
    quality: str = "PASS"
    provider: str = ""
    admission: str = ADMISSION_DISPLAY

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
            "last_size": self.last_size,
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
    #: Canonical provider-neutral incremental book engines (G5 / ARCH-003).
    #: The engine is the authoritative book state; ``books`` holds the
    #: compatibility snapshot projection consumed by existing projections.
    canonical_books: dict[str, IncrementalOrderBook] = field(default_factory=dict)
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
            # Canonical engine is authoritative for book state. Full-book
            # provider pushes enter via the explicit snapshot ingestion
            # compatibility mode (replace_from_snapshot), never a blind
            # in-place mutation; incremental providers (IBKR in G6) feed
            # DepthUpdate events through apply_depth_update into the same
            # engine.
            engine = self.canonical_books.get(instrument_id)
            if engine is None:
                engine = IncrementalOrderBook(instrument_id)
                self.canonical_books[instrument_id] = engine
            engine.replace_from_snapshot(
                bids=bids,
                asks=asks,
                provider=provider,
                source_time_ns=event_time_ns,
                received_time_ns=received_ns,
            )
            self._refresh_book_projection(
                engine,
                instrument_id=instrument_id,
                provider=provider,
                event_time_ns=event_time_ns,
                available_ns=available_ns,
                received_ns=received_ns,
                admission=admission,
                quality=quality,
                update_semantics="SNAPSHOT",
            )
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

    def _refresh_book_projection(
        self,
        engine: IncrementalOrderBook,
        *,
        instrument_id: str,
        provider: str,
        event_time_ns: int,
        available_ns: int,
        received_ns: int,
        admission: str,
        quality: str,
        update_semantics: str,
    ) -> None:
        """Refresh the legacy snapshot projection from canonical engine state.

        Shared by the snapshot-ingestion path (``apply_admitted``) and the
        incremental provider path (``apply_depth_update``) so the two never
        drift: the engine stays authoritative and ``books`` is always a
        deterministic projection of it.
        """
        bids, asks = engine.to_snapshot_rows()
        features = compute_book_features(bids, asks)
        canonical = project_book_snapshot(engine, include_rows=False)
        self.books[instrument_id] = {
            "admission": admission,
            "asks": asks,
            "available_time_ns": available_ns,
            "bids": bids,
            "book_features": None if features is None else features.to_dict(),
            "book_state_valid": canonical["book_state_valid"],
            "book_status": canonical["book_status"],
            "book_status_reason": canonical["book_status_reason"],
            "event_time_ns": event_time_ns,
            "generation": canonical["generation"],
            "model_version": canonical["model_version"],
            "provider": provider,
            "quality": quality,
            "received_ns": received_ns,
            "requested_depth": len(bids) + len(asks),
            "returned_depth": max(len(bids), len(asks)),
            "sequence_status": canonical["sequence_state"],
            "update_semantics": update_semantics,
        }
        if engine.last_source_time_ns is not None:
            self.books[instrument_id]["last_source_time_ns"] = engine.last_source_time_ns
        if engine.last_received_time_ns is not None:
            self.books[instrument_id]["last_received_time_ns"] = engine.last_received_time_ns

    def quote_for(self, instrument_id: str) -> QuoteSnapshot | None:
        return self.quotes.get(instrument_id.upper())

    def trades_for(self, instrument_id: str) -> list[dict[str, Any]]:
        tape = self.trades.get(instrument_id.upper())
        return list(tape) if tape else []

    def book_for(self, instrument_id: str) -> dict[str, Any] | None:
        return self.books.get(instrument_id.upper())

    def depth_admissibility_for(
        self,
        instrument_id: str,
        *,
        as_of_time_ns: int,
        provider_id: str = "",
        context: DepthAdmissionContext | None = None,
        policy: FreshnessPolicy | None = None,
    ) -> DepthAdmissibilityResult:
        """Evaluate canonical depth admissibility for one instrument."""
        engine = self.book_engine_for(instrument_id)
        return evaluate_depth_admissibility(
            engine,
            as_of_time_ns=as_of_time_ns,
            policy=policy or depth_freshness_policy(provider_id),
            context=context,
        )

    def book_freshness_for(
        self,
        instrument_id: str,
        *,
        as_of_time_ns: int,
        policy: FreshnessPolicy | None = None,
        provider_id: str = "",
    ) -> str:
        engine = self.book_engine_for(instrument_id)
        if engine is None:
            return "UNAVAILABLE"
        evaluation = evaluate_book_freshness(
            engine,
            as_of_time_ns=as_of_time_ns,
            policy=policy or depth_freshness_policy(provider_id),
        )
        return evaluation.status.value

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
        self.canonical_books.pop(key, None)

    def book_engine_for(self, instrument_id: str) -> IncrementalOrderBook | None:
        return self.canonical_books.get(instrument_id.upper())

    # ------------------------------------------------------------------ G6
    # Canonical provider-adapter entry points. The IBKR observational adapter
    # (and any future incremental provider) calls these directly with canonical
    # facts; this store remains the ONLY canonical book store and the only
    # quote state store.

    def apply_quote_update(
        self,
        *,
        instrument_id: str,
        bid_price: float | None = None,
        ask_price: float | None = None,
        bid_size: float | None = None,
        ask_size: float | None = None,
        last_price: float | None = None,
        last_size: float | None = None,
        event_time_ns: int | None = None,
        available_time_ns: int | None = None,
        received_ns: int | None = None,
        quality: str = "PASS",
        provider: str = "IBKR",
        admission: str = ADMISSION_DISPLAY,
    ) -> QuoteSnapshot:
        """Canonical L1 quote entry point (provider adapters).

        Unknown facts stay ``None`` — this method never fabricates a side or a
        size, and the adapter is responsible for only publishing facts it
        actually observed (delayed data is labeled via ``quality``, never
        presented as real-time).
        """
        key = str(instrument_id or "").upper()
        if not key:
            raise ValueError("instrument_id must be a non-empty string")
        now_ns = received_ns if received_ns is not None else monotonic_wall_ns()
        self.quotes[key] = QuoteSnapshot(
            instrument_id=key,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            last_price=last_price,
            last_size=last_size,
            volume=None,
            event_time_ns=event_time_ns if event_time_ns is not None else now_ns,
            available_time_ns=available_time_ns if available_time_ns is not None else now_ns,
            received_ns=now_ns,
            quality=quality,
            provider=provider,
            admission=admission,
        )
        self.metrics["events_received"] += 1
        self.metrics["events_admitted"] += 1
        return self.quotes[key]

    def apply_depth_update(
        self,
        update: Any,
        *,
        quality: str = "PASS",
        admission: str = ADMISSION_DISPLAY,
    ) -> Any:
        """Canonical incremental depth entry point (G6 adapter path).

        Applies one :class:`DepthUpdate` to the canonical engine, then
        refreshes the legacy snapshot projection. Returns the engine's
        :class:`ApplyResult` — callers must never infer success.
        """
        from ..order_flow.order_book.contracts import (
            ApplyOutcome,
            DepthUpdate,
        )

        if not isinstance(update, DepthUpdate):
            raise TypeError(f"expected DepthUpdate, got {type(update).__name__}")
        self.metrics["events_received"] += 1
        instrument_id = update.instrument_id.upper()
        engine = self.canonical_books.get(instrument_id)
        if engine is None:
            engine = IncrementalOrderBook(update.instrument_id)
            self.canonical_books[instrument_id] = engine
        result = engine.apply(update)
        if result.outcome in {
            ApplyOutcome.APPLIED,
            ApplyOutcome.NOOP,
            ApplyOutcome.INVALIDATED,
            ApplyOutcome.RESET_APPLIED,
        }:
            event_time_ns = (
                update.source_time_ns
                if update.source_time_ns is not None
                else (engine.last_source_time_ns or 0)
            )
            received_ns = (
                update.received_time_ns
                if update.received_time_ns is not None
                else (engine.last_received_time_ns or 0)
            )
            self._refresh_book_projection(
                engine,
                instrument_id=instrument_id,
                provider=str(update.source or "IBKR"),
                event_time_ns=event_time_ns,
                available_ns=received_ns,
                received_ns=received_ns,
                admission=admission,
                quality=quality,
                update_semantics="INCREMENTAL",
            )
        if result.outcome in {ApplyOutcome.APPLIED, ApplyOutcome.RESET_APPLIED}:
            self.metrics["events_admitted"] += 1
        return result

    def apply_classified_trade(
        self,
        trade: Any,
        *,
        instrument_id: str,
        event_time_ns: int | None = None,
        available_time_ns: int | None = None,
        received_ns: int | None = None,
        quality: str = "PASS",
        provider: str = "IBKR",
        admission: str = ADMISSION_DISPLAY,
        dedupe: bool = True,
    ) -> bool:
        """Canonical classified trade entry point (G9 IBKR adapter path)."""
        from ..order_flow.contracts import ClassifiedTrade

        if not isinstance(trade, ClassifiedTrade):
            raise TypeError(f"expected ClassifiedTrade, got {type(trade).__name__}")
        key = str(instrument_id or "").upper()
        if not key:
            raise ValueError("instrument_id must be a non-empty string")
        now_ns = received_ns if received_ns is not None else monotonic_wall_ns()
        tape = self.trades.setdefault(key, deque(maxlen=self.max_trades))
        if dedupe and any(row.get("trade_id") == trade.trade_id for row in tape):
            self.metrics["duplicates"] += 1
            return False
        event_ns = event_time_ns if event_time_ns is not None else now_ns
        available_ns = available_time_ns if available_time_ns is not None else now_ns
        tape.append(
            {
                "admission": admission,
                "aggressor_provenance": trade.aggressor_source.value,
                "aggressor_side": trade.aggressor_side.value.upper(),
                "available_time_ns": available_ns,
                "classification_confidence": trade.classification_confidence,
                "classification_method": trade.classification_method,
                "event_time_ns": event_ns,
                "price": trade.price,
                "provider": provider,
                "quality": quality,
                "quantity": trade.quantity,
                "signed_volume": trade.signed_volume,
                "trade_id": trade.trade_id,
            }
        )
        self.metrics["events_received"] += 1
        self.metrics["events_admitted"] += 1
        if trade.aggressor_side.value.upper() == "UNKNOWN":
            self.metrics["unknown_aggressor"] += 1
        else:
            self.metrics["classified_trades"] += 1
        provenance = trade.aggressor_source.value
        if provenance in {"PROVIDER_NATIVE", "EXCHANGE_NATIVE"}:
            self.metrics["provider_directed"] += 1
        elif provenance in {"LEE_READY", "QUOTE_MATCH", "TICK_RULE", "BVC", "OTHER_INFERENCE"}:
            self.metrics["inferred"] += 1
        return True


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
