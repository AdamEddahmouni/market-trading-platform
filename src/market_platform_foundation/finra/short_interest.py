"""Normalize Consolidated Short Interest rows. Inventory snapshot, not flow."""

from __future__ import annotations

from typing import Any

from ..canonical import sha256_bytes, canonical_bytes
from ..short_intelligence.clocks import clocks_short_interest
from ..short_intelligence.contracts import ObservationFamily, ShortInterestObservation
from ..short_intelligence.identity import SymbolMap
from .publication_calendar import cycle_for_settlement


def _int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return None


def _float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flag(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def normalize_short_interest_row(
    row: dict[str, Any],
    *,
    symbol_map: SymbolMap,
    observed_time: str,
    retrieved_time: str,
    finra_request_id: str = "",
    record_version: int = 1,
) -> ShortInterestObservation:
    symbol = str(row.get("symbolCode") or "").strip().upper()
    settlement = str(row.get("settlementDate") or "")[:10]
    cycle = cycle_for_settlement(settlement)
    publication = cycle.publication_date if cycle else ""
    provider_available = cycle.provider_available_time if cycle else ""
    quality: list[str] = []
    if cycle is None:
        quality.append("PUBLICATION_CALENDAR_UNKNOWN")
        quality.append("PIT_UNCERTAIN")
    resolved = symbol_map.resolve(symbol, as_of=settlement or observed_time)
    if "IDENTITY_UNRESOLVED" in resolved.quality_flags:
        quality.append("IDENTITY_UNRESOLVED")
    revision = _flag(row.get("revisionFlag"))
    if revision and revision.upper() not in {"N", "NULL", "NONE"}:
        quality.append("REVISED")
    clocks = clocks_short_interest(
        settlement_date=settlement,
        publication_date=publication or settlement,
        observed_time=observed_time,
        retrieved_time=retrieved_time,
        provider_available_time=provider_available,
    )
    if cycle is None:
        clocks = dict(clocks)
        clocks["available_time"] = ""
        clocks["provider_available_time"] = ""
        clocks["official_publication_date"] = ""
    current = _int(row.get("currentShortPositionQuantity"))
    previous = _int(row.get("previousShortPositionQuantity"))
    delta = _int(row.get("changePreviousNumber"))
    if delta is None and current is not None and previous is not None:
        delta = current - previous
    return ShortInterestObservation(
        observation_family=ObservationFamily.SHORT_INTEREST,
        instrument_id=resolved.instrument_id,
        provider_symbol=symbol,
        settlement_date=settlement,
        publication_date=publication,
        current_short_position_quantity=current,
        previous_short_position_quantity=previous,
        short_position_delta=delta,
        short_position_pct_change=_float(row.get("changePercent")),
        average_daily_volume_quantity=_int(row.get("averageDailyVolumeQuantity")),
        days_to_cover_provider=_float(row.get("daysToCoverQuantity")),
        market_class_code=str(row.get("marketClassCode") or ""),
        stock_split_flag=_flag(row.get("stockSplitFlag")),
        revision_flag=revision,
        issue_name=str(row.get("issueName") or ""),
        provider="finra.query",
        source_dataset="otcMarket/consolidatedShortInterest",
        record_version=record_version,
        clocks=clocks,
        quality_flags=tuple(dict.fromkeys(quality)),
        raw_payload_hash=sha256_bytes(canonical_bytes(row)),
        finra_request_id=finra_request_id,
    )
