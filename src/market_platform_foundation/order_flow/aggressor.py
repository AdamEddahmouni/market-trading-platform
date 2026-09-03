"""Trade aggressor classification with explicit provenance."""

from __future__ import annotations

from ..donor_patterns.cvd_formulas import classify_aggressor
from .contracts import AggressorSide, AggressorSource, ClassifiedTrade

_NATIVE_QUALITY_SOURCES: dict[str, AggressorSource] = {
    "tick": AggressorSource.EXCHANGE_NATIVE,
    "mixed": AggressorSource.PROVIDER_NATIVE,
}

_INFERRED_QUALITY_SOURCES: dict[str, AggressorSource] = {
    "bvc": AggressorSource.BVC,
    "neutral": AggressorSource.UNKNOWN,
}


def provenance_from_quality_label(quality: str) -> AggressorSource:
    """Map fixture/provider quality labels to aggressor source — no silent upgrade."""
    normalized = str(quality).strip().lower()
    if normalized in _NATIVE_QUALITY_SOURCES:
        return _NATIVE_QUALITY_SOURCES[normalized]
    if normalized in _INFERRED_QUALITY_SOURCES:
        return _INFERRED_QUALITY_SOURCES[normalized]
    return AggressorSource.OTHER_INFERENCE


def _confidence_for_source(source: AggressorSource, *, delta: float) -> float:
    if source in {AggressorSource.EXCHANGE_NATIVE, AggressorSource.PROVIDER_NATIVE}:
        return 1.0 if delta != 0 else 0.5
    if source == AggressorSource.BVC:
        return 0.65
    if source == AggressorSource.LEE_READY:
        return 0.75
    if source == AggressorSource.TICK_RULE:
        return 0.55
    if source == AggressorSource.UNKNOWN:
        return 0.0
    return 0.4


def classify_trade(
    *,
    trade_id: str,
    price: float,
    quantity: float,
    bid: float | None = None,
    ask: float | None = None,
    prev_price: float | None = None,
    prev_dir: float = 0.0,
    trade_timestamp: str,
    quote_timestamp: str | None = None,
    provider: str = "",
    venue: str = "",
    aggressor_source: AggressorSource | None = None,
    use_midpoint: bool = False,
) -> ClassifiedTrade:
    """Classify a single trade using quote/tick rules when source not pre-specified."""
    signed = classify_aggressor(
        price,
        quantity,
        bid,
        ask,
        prev_price,
        prev_dir,
        use_midpoint=use_midpoint,
    )
    if signed > 0:
        side = AggressorSide.BUY
    elif signed < 0:
        side = AggressorSide.SELL
    else:
        side = AggressorSide.UNKNOWN

    if aggressor_source is None:
        if bid is not None and ask is not None and bid < ask:
            source = AggressorSource.QUOTE_MATCH if use_midpoint else AggressorSource.LEE_READY
            method = "midpoint" if use_midpoint else "lee_ready"
        elif prev_price is not None:
            source = AggressorSource.TICK_RULE
            method = "tick_rule"
        else:
            source = AggressorSource.UNKNOWN
            method = "unknown"
    else:
        source = aggressor_source
        method = source.value.lower()

    confidence = _confidence_for_source(source, delta=signed)
    return ClassifiedTrade(
        trade_id=trade_id,
        price=price,
        quantity=quantity,
        aggressor_side=side,
        signed_volume=signed,
        aggressor_source=source,
        classification_method=method,
        classification_confidence=confidence,
        trade_timestamp=trade_timestamp,
        quote_timestamp=quote_timestamp,
        provider=provider,
        venue=venue,
    )


def classify_bar_delta(
    *,
    bar_time: str,
    delta: float,
    volume: float,
    quality: str,
    source: str = "",
    venue: str = "US_EQUITY",
) -> ClassifiedTrade:
    """Normalize pre-aggregated bar delta with fixture quality semantics."""
    aggressor_source = provenance_from_quality_label(quality)
    if delta > 0:
        side = AggressorSide.BUY
    elif delta < 0:
        side = AggressorSide.SELL
    else:
        side = AggressorSide.UNKNOWN
    return ClassifiedTrade(
        trade_id=f"{bar_time}:bar",
        price=0.0,
        quantity=abs(volume) if volume else abs(delta),
        aggressor_side=side,
        signed_volume=delta,
        aggressor_source=aggressor_source,
        classification_method=f"bar_aggregate:{quality}",
        classification_confidence=_confidence_for_source(aggressor_source, delta=delta),
        trade_timestamp=bar_time,
        provider=source,
        venue=venue,
    )


__all__ = [
    "classify_bar_delta",
    "classify_trade",
    "provenance_from_quality_label",
]
