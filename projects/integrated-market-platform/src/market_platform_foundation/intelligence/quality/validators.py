"""Domain validators adapted to canonical quality findings (BUILD 04)."""

from __future__ import annotations

from typing import Any

from ...market_data.quality import assess_book, assess_quote
from ..contracts.event import EventV1
from .models import (
    FindingSeverity,
    IntelligenceCapability,
    QualityFinding,
    QualityFindingCode,
    capability_for_event_type,
)


def _severity_for_flag(flag: str) -> FindingSeverity:
    if flag in {QualityFindingCode.CROSSED_BOOK.value, QualityFindingCode.INVALID_QUOTE.value}:
        return FindingSeverity.ERROR
    if flag in {"LOCKED_BOOK", "SPREAD_ABNORMAL", "DEPTH_PARTIAL"}:
        return FindingSeverity.WARNING
    return FindingSeverity.WARNING


def _finding_for_flag(
    flag: str,
    *,
    event: EventV1,
    capability: IntelligenceCapability | None,
) -> QualityFinding:
    code = flag
    if flag == "LOCKED_BOOK":
        code = QualityFindingCode.LOCKED_BOOK.value
    elif flag in {"DEPTH_PARTIAL", "MICROSTRUCTURE_CAPABILITY_UNAVAILABLE"}:
        code = QualityFindingCode.PARTIAL_DATA.value
    return QualityFinding(
        code=code,
        severity=_severity_for_flag(flag),
        message=f"{flag} detected for event {event.event_id}",
        provider_id=event.source.provider_id,
        capability=capability,
        instrument_id=event.instrument_id,
        observed_at_ns=event.available_time_ns,
        event_id=event.event_id,
        evidence={"flag": flag},
    )


def _payload_for_quote_validator(payload: dict[str, Any]) -> dict[str, Any]:
    """Adapt normalized intelligence payloads to the platform quote validator shape."""
    adapted = dict(payload)
    if "bid" in payload and "bid_price" not in payload:
        adapted["bid_price"] = payload["bid"]
    if "ask" in payload and "ask_price" not in payload:
        adapted["ask_price"] = payload["ask"]
    if "bid_size" in payload and "bid_vol" not in payload:
        adapted["bid_vol"] = payload["bid_size"]
    if "ask_size" in payload and "ask_vol" not in payload:
        adapted["ask_vol"] = payload["ask_size"]
    return adapted


def validate_quote_event(event: EventV1) -> tuple[QualityFinding, ...]:
    """Reuse platform quote validator; expose results as canonical findings."""
    capability = capability_for_event_type(event.event_type)
    flags = assess_quote(_payload_for_quote_validator(event.payload))
    return tuple(_finding_for_flag(flag, event=event, capability=capability) for flag in flags)


def validate_depth_event(event: EventV1) -> tuple[QualityFinding, ...]:
    capability = capability_for_event_type(event.event_type)
    flags = assess_book(event.payload)
    return tuple(_finding_for_flag(flag, event=event, capability=capability) for flag in flags)


def validate_event_structure(event: EventV1) -> tuple[QualityFinding, ...]:
    """Run capability-appropriate structural validators on a normalized event."""
    event_type = str(event.event_type).upper()
    if event_type in {"QUOTE", "L1"}:
        return validate_quote_event(event)
    if event_type in {"DEPTH", "ORDER_BOOK"}:
        return validate_depth_event(event)
    return ()


def assess_freshness_finding(
    event: EventV1,
    *,
    decision_time_ns: int,
    max_age_ns: int,
    stale_code: str,
) -> QualityFinding | None:
    age_ns = decision_time_ns - event.available_time_ns
    if age_ns <= max_age_ns:
        return None
    capability = capability_for_event_type(event.event_type)
    return QualityFinding(
        code=stale_code,
        severity=FindingSeverity.WARNING,
        message=(
            f"{stale_code}: event {event.event_id} age {age_ns}ns exceeds "
            f"requirement {max_age_ns}ns"
        ),
        provider_id=event.source.provider_id,
        capability=capability,
        instrument_id=event.instrument_id,
        observed_at_ns=event.available_time_ns,
        event_id=event.event_id,
        evidence={"age_ns": age_ns, "max_age_ns": max_age_ns},
    )


def assess_borrow_freshness(
    event: EventV1,
    *,
    decision_time_ns: int,
    max_age_ns: int,
) -> QualityFinding | None:
    if str(event.event_type).upper() != "BORROW":
        return None
    return assess_freshness_finding(
        event,
        decision_time_ns=decision_time_ns,
        max_age_ns=max_age_ns,
        stale_code=QualityFindingCode.BORROW_STALE.value,
    )


def assess_short_interest_freshness(
    event: EventV1,
    *,
    decision_time_ns: int,
    max_age_ns: int,
) -> QualityFinding | None:
    if str(event.event_type).upper() != "SHORT_INTEREST":
        return None
    return assess_freshness_finding(
        event,
        decision_time_ns=decision_time_ns,
        max_age_ns=max_age_ns,
        stale_code=QualityFindingCode.SHORT_INTEREST_STALE.value,
    )


def quote_mid_price(payload: dict[str, Any]) -> float | None:
    adapted = _payload_for_quote_validator(payload)
    bid = adapted.get("bid_price") or adapted.get("best_bid")
    ask = adapted.get("ask_price") or adapted.get("best_ask")
    try:
        bid_f = float(bid) if bid is not None else 0.0
        ask_f = float(ask) if ask is not None else 0.0
    except (TypeError, ValueError):
        return None
    if bid_f > 0 and ask_f > 0:
        return (bid_f + ask_f) / 2.0
    last = payload.get("last_price") or payload.get("last")
    try:
        return float(last) if last not in (None, 0, 0.0) else None
    except (TypeError, ValueError):
        return None


__all__ = [
    "assess_borrow_freshness",
    "assess_freshness_finding",
    "assess_short_interest_freshness",
    "quote_mid_price",
    "validate_depth_event",
    "validate_event_structure",
    "validate_quote_event",
]
