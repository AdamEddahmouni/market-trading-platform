"""IBKR tick-by-tick trade print normalization and classification (G9).

Maps provider tick-by-tick facts into canonical :class:`ClassifiedTrade`
semantics without fabricating exchange-native aggressor side. IB
``tickByTickAllLast`` supplies price, size, exchange, special conditions,
and ``TickAttribLast`` flags — not a verified aggressor side — so
classification uses the IMP hierarchy:

1. INFERRED via contemporaneous canonical L1 (same provider, not stale).
2. UNKNOWN when quote context is missing, stale, cross-provider, or invalid.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ...order_flow.aggressor import classify_trade
from ...order_flow.contracts import AggressorSide, AggressorSource, ClassifiedTrade
from .contracts import EntitlementState, TradePrintFacts


class TradeClassificationKind(StrEnum):
    NATIVE = "NATIVE"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class QuoteContext:
    bid: float | None
    ask: float | None
    provider: str
    received_ns: int | None
    quality: str
    entitlement: EntitlementState | None = None


def replay_dedup_key(
    *,
    req_id: int,
    source_time_ns: int | None,
    price: float,
    size: float,
    exchange: str | None,
) -> str:
    """Local replay/idempotency key — NOT a provider event id.

    IB tick-by-tick does not expose a stable provider event identifier; this
    composite is used only for bounded dedup within capture/replay sessions.
    """
    return f"ibkr:tbt:{req_id}:{source_time_ns}:{price}:{size}:{exchange or ''}"


def facts_from_tick_by_tick_all_last(
    *,
    instrument_id: str,
    subscription_id: str,
    req_id: int,
    generation: int,
    price: float,
    size: float,
    source_time_ns: int | None,
    received_time_ns: int,
    exchange: str | None = None,
    special_conditions: str | None = None,
    tick_type: int | None = None,
    past_limit: bool | None = None,
    unreported: bool | None = None,
) -> TradePrintFacts:
    return TradePrintFacts(
        instrument_id=instrument_id,
        subscription_id=subscription_id,
        req_id=req_id,
        generation=generation,
        price=price,
        size=size,
        source_time_ns=source_time_ns,
        received_time_ns=received_time_ns,
        exchange=exchange,
        special_conditions=special_conditions,
        tick_type=tick_type,
        past_limit=past_limit,
        unreported=unreported,
        provider_event_id=None,
        schema_version="ibkr_observational/trade_print/1.0.0",
    )


def _quote_is_eligible(
    quote: QuoteContext | None,
    *,
    trade_provider: str,
    received_time_ns: int,
    stale_after_ms: int = 5000,
) -> tuple[bool, str | None]:
    if quote is None:
        return False, "MISSING_QUOTE_CONTEXT"
    if quote.provider and quote.provider.upper() != trade_provider.upper():
        return False, "PROVIDER_MISMATCH"
    if quote.quality in {"STALE", "DELAYED", "INVALID"}:
        return False, f"QUOTE_{quote.quality}"
    if quote.entitlement in {
        EntitlementState.NOT_ENTITLED,
        EntitlementState.ERROR,
    }:
        return False, "QUOTE_NOT_ENTITLED"
    if quote.received_ns is not None and stale_after_ms > 0:
        age_ms = (received_time_ns - quote.received_ns) / 1_000_000
        if age_ms > stale_after_ms:
            return False, "QUOTE_STALE"
    if quote.bid is None or quote.ask is None or quote.bid >= quote.ask:
        return False, "QUOTE_INCOMPLETE"
    return True, None


def classify_trade_print(
    facts: TradePrintFacts,
    *,
    quote: QuoteContext | None = None,
    prev_price: float | None = None,
    prev_dir: float = 0.0,
    stale_after_ms: int = 5000,
    provider: str = "IBKR",
) -> tuple[ClassifiedTrade, TradeClassificationKind, str | None]:
    """Classify one IBKR trade print into canonical CVD semantics."""
    eligible, quote_reason = _quote_is_eligible(
        quote,
        trade_provider=provider,
        received_time_ns=facts.received_time_ns,
        stale_after_ms=stale_after_ms,
    )
    trade_id = replay_dedup_key(
        req_id=facts.req_id,
        source_time_ns=facts.source_time_ns,
        price=facts.price,
        size=facts.size,
        exchange=facts.exchange,
    )
    trade_timestamp = (
        str(facts.source_time_ns) if facts.source_time_ns is not None else ""
    )
    quote_timestamp = (
        str(quote.received_ns)
        if quote is not None and quote.received_ns is not None
        else None
    )

    if eligible and quote is not None:
        classified = classify_trade(
            trade_id=trade_id,
            price=facts.price,
            quantity=facts.size,
            bid=quote.bid,
            ask=quote.ask,
            prev_price=prev_price,
            prev_dir=prev_dir,
            trade_timestamp=trade_timestamp,
            quote_timestamp=quote_timestamp,
            provider=provider,
            venue=facts.exchange or "",
            aggressor_source=AggressorSource.LEE_READY,
        )
        if classified.aggressor_side is AggressorSide.UNKNOWN:
            return classified, TradeClassificationKind.UNKNOWN, quote_reason
        return classified, TradeClassificationKind.INFERRED, None

    classified = ClassifiedTrade(
        trade_id=trade_id,
        price=facts.price,
        quantity=facts.size,
        aggressor_side=AggressorSide.UNKNOWN,
        signed_volume=0.0,
        aggressor_source=AggressorSource.UNKNOWN,
        classification_method="ibkr.tbt.insufficient_context/1",
        classification_confidence=0.0,
        trade_timestamp=trade_timestamp,
        quote_timestamp=quote_timestamp,
        provider=provider,
        venue=facts.exchange or "",
    )
    return classified, TradeClassificationKind.UNKNOWN, quote_reason or "MISSING_QUOTE_CONTEXT"


def facts_to_dict(facts: TradePrintFacts) -> dict[str, Any]:
    return facts.as_dict()


__all__ = [
    "QuoteContext",
    "TradeClassificationKind",
    "classify_trade_print",
    "facts_from_tick_by_tick_all_last",
    "facts_to_dict",
    "replay_dedup_key",
]
