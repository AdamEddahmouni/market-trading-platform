"""Normalize vendor JSON into canonical OF contracts without importing SDKs."""

from __future__ import annotations

from typing import Any

from ..contracts.envelope import validate_envelope
from ..contracts.identity import normalized_event_id
from ..order_flow.contracts import AggressorSide, AggressorSource, ClassifiedTrade, L1QuoteState
from ..order_flow.l1 import compute_l1_state
from ..providers.contracts import SymbolMapping
from ..providers.envelope import build_provider_metadata
from .timestamps import clocks_from_capture

PROVIDER_ID = "moomoo.opend.observational"
NORMALIZATION_VERSION = "market_data/moomoo/1.0.0"


def canonical_symbol(provider_symbol: str) -> SymbolMapping:
    text = str(provider_symbol).strip().upper()
    if "." in text:
        market, code = text.split(".", 1)
    else:
        market, code = "US", text
    venue = {
        "US": "US_EQUITY",
        "CC": "CRYPTO",
        "HK": "HK_EQUITY",
        "HK_FUTURE": "HK_FUTURE",
    }.get(market, market)
    return SymbolMapping(provider_symbol=text, instrument_id=code, venue_id=venue)


def classified_trade_from_ticker(payload: dict[str, Any], *, provider: str = PROVIDER_ID) -> ClassifiedTrade:
    direction = str(payload.get("ticker_direction") or payload.get("direction") or "").upper()
    if direction in {"BUY", "BID"}:
        side = AggressorSide.BUY
        source = AggressorSource.PROVIDER_NATIVE
        method = "provider.ticker_direction"
        confidence = 0.7
        signed = float(payload.get("volume") or 0)
    elif direction in {"SELL", "ASK"}:
        side = AggressorSide.SELL
        source = AggressorSource.PROVIDER_NATIVE
        method = "provider.ticker_direction"
        confidence = 0.7
        signed = -float(payload.get("volume") or 0)
    else:
        side = AggressorSide.UNKNOWN
        source = AggressorSource.UNKNOWN
        method = "unclassified"
        confidence = 0.0
        signed = 0.0
    sequence = payload.get("sequence")
    trade_id = str(sequence if sequence is not None else payload.get("time") or "unknown")
    return ClassifiedTrade(
        trade_id=trade_id,
        price=float(payload.get("price") or 0),
        quantity=float(payload.get("volume") or 0),
        aggressor_side=side,
        signed_volume=signed,
        aggressor_source=source,
        classification_method=method,
        classification_confidence=confidence,
        trade_timestamp=str(payload.get("time") or ""),
        quote_timestamp=None,
        provider=provider,
        venue=str(payload.get("venue") or ""),
    )


def l1_from_quote(payload: dict[str, Any]) -> L1QuoteState | None:
    bid = float(payload.get("bid_price") or payload.get("best_bid") or 0)
    ask = float(payload.get("ask_price") or payload.get("best_ask") or 0)
    bid_size = float(payload.get("bid_vol") or payload.get("bid_size") or 0)
    ask_size = float(payload.get("ask_vol") or payload.get("ask_size") or 0)
    return compute_l1_state(best_bid=bid, best_ask=ask, bid_size=bid_size, ask_size=ask_size)


def levels_from_order_book(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bids = _normalize_side(payload.get("Bid") or payload.get("bids") or [])
    asks = _normalize_side(payload.get("Ask") or payload.get("asks") or [])
    bids.sort(key=lambda row: float(row["price"]), reverse=True)
    asks.sort(key=lambda row: float(row["price"]))
    return bids, asks


def live_envelope_from_capture(record: dict[str, Any]) -> dict[str, Any]:
    clocks = clocks_from_capture(record)
    received = clocks.received_time_ns or 0
    event_time = clocks.event_time_ns or clocks.provider_time_ns or received
    mapping = canonical_symbol(str(record.get("provider_symbol") or record.get("instrument_id") or ""))
    metadata = build_provider_metadata(
        provider_id=str(record.get("provider") or PROVIDER_ID),
        entitlement="OBSERVATIONAL_READ_ONLY",
        event_time_ns=event_time,
        receive_time_ns=received,
        symbol_mapping=mapping,
        raw_source_reference=str(record.get("schema_version") or ""),
        quality_state="GOOD" if not record.get("quality_flags") else "DEGRADED",
    )
    event_id = normalized_event_id(
        provider_id=str(record.get("provider") or PROVIDER_ID),
        venue_id=mapping.venue_id,
        publisher_id=str(record.get("provider") or PROVIDER_ID),
        channel_id=mapping.provider_symbol,
        source_instance_id=str(record.get("provider") or PROVIDER_ID),
        source_record_id=str(record.get("sequence") or event_time),
        source_revision_id="1",
        event_family=str(record.get("capability") or "MARKET_DATA_EVENT"),
        subrecord_discriminator="live",
    )
    envelope = {
        "available_time": received,
        "channel_id": mapping.provider_symbol,
        "event_time": event_time,
        "event_type": str(record.get("capability") or "MARKET_DATA_EVENT"),
        "historical_ingested_time": None,
        "ingest_run_id": str(record.get("ingest_run_id") or "live-observational"),
        "instrument_id": mapping.instrument_id,
        "live_received_time": received,
        "normalization_version": NORMALIZATION_VERSION,
        "normalized_event_id": event_id,
        "operation": "UPSERT",
        "provider_metadata": metadata,
        "publisher_id": str(record.get("provider") or PROVIDER_ID),
        "quality_observation_refs": list(record.get("quality_flags") or []),
        "raw_reference": str(record.get("schema_version") or ""),
        "schema_version": "1.0.0",
        "source_instance_id": str(record.get("provider") or PROVIDER_ID),
        "source_publish_time": clocks.provider_time_ns or event_time,
        "source_record_id": str(record.get("sequence") or event_id),
        "source_revision_id": "1",
        "source_sequence": record.get("sequence"),
        "supersedes_event_id": None,
        "venue_id": mapping.venue_id,
        "payload": record.get("raw_payload") or {},
    }
    reasons = validate_envelope(
        envelope,
        timestamp_states={
            "event_time": "REQUIRED",
            "source_publish_time": "REQUIRED",
            "live_received_time": "REQUIRED",
            "historical_ingested_time": "FORBIDDEN",
            "available_time": "REQUIRED",
        },
        acquisition_mode="live",
    )
    if reasons:
        raise ValueError(f"LIVE_ENVELOPE_INVALID:{','.join(reasons)}")
    return envelope


def replay_envelope_from_capture(record: dict[str, Any]) -> dict[str, Any]:
    """Historical-mode envelope for deterministic replay of captured observations.

    Knowledge time is received_time (what a live consumer could have known).
    This is not dataset admission.
    """
    clocks = clocks_from_capture(record)
    received = clocks.received_time_ns or 0
    ingested = clocks.ingested_time_ns or received
    event_time = clocks.event_time_ns or clocks.provider_time_ns or received
    mapping = canonical_symbol(str(record.get("provider_symbol") or record.get("instrument_id") or ""))
    metadata = build_provider_metadata(
        provider_id=str(record.get("provider") or PROVIDER_ID),
        entitlement="CAPTURED_REPLAY_NOT_ADMITTED",
        event_time_ns=event_time,
        receive_time_ns=received,
        symbol_mapping=mapping,
        raw_source_reference=str(record.get("schema_version") or ""),
    )
    event_id = normalized_event_id(
        provider_id=str(record.get("provider") or PROVIDER_ID),
        venue_id=mapping.venue_id,
        publisher_id=str(record.get("provider") or PROVIDER_ID),
        channel_id=mapping.provider_symbol,
        source_instance_id=str(record.get("provider") or PROVIDER_ID),
        source_record_id=str(record.get("sequence") or event_time),
        source_revision_id="1",
        event_family=str(record.get("capability") or "MARKET_DATA_EVENT"),
        subrecord_discriminator="replay",
    )
    envelope = {
        "available_time": received,
        "channel_id": mapping.provider_symbol,
        "event_time": event_time,
        "event_type": str(record.get("capability") or "MARKET_DATA_EVENT"),
        "historical_ingested_time": ingested,
        "ingest_run_id": str(record.get("ingest_run_id") or "captured-replay"),
        "instrument_id": mapping.instrument_id,
        "live_received_time": None,
        "normalization_version": NORMALIZATION_VERSION,
        "normalized_event_id": event_id,
        "operation": "UPSERT",
        "provider_metadata": metadata,
        "publisher_id": str(record.get("provider") or PROVIDER_ID),
        "quality_observation_refs": list(record.get("quality_flags") or []),
        "raw_reference": str(record.get("schema_version") or ""),
        "schema_version": "1.0.0",
        "source_instance_id": str(record.get("provider") or PROVIDER_ID),
        "source_publish_time": clocks.provider_time_ns or event_time,
        "source_record_id": str(record.get("sequence") or event_id),
        "source_revision_id": "1",
        "source_sequence": record.get("sequence"),
        "supersedes_event_id": None,
        "venue_id": mapping.venue_id,
        "payload": record.get("raw_payload") or {},
    }
    reasons = validate_envelope(
        envelope,
        timestamp_states={
            "event_time": "REQUIRED",
            "source_publish_time": "REQUIRED",
            "live_received_time": "FORBIDDEN",
            "historical_ingested_time": "REQUIRED",
            "available_time": "REQUIRED",
        },
        acquisition_mode="historical",
    )
    if reasons:
        raise ValueError(f"REPLAY_ENVELOPE_INVALID:{','.join(reasons)}")
    return envelope


def _normalize_side(raw: object) -> list[dict[str, Any]]:
    levels: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return levels
    for item in raw:
        if isinstance(item, dict):
            price = item.get("price")
            size = item.get("size") if item.get("size") is not None else item.get("volume")
            order_count = item.get("order_count") if item.get("order_count") is not None else item.get("num")
            details = item.get("order_details") or item.get("orders") or {}
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            price, size = item[0], item[1]
            order_count = item[2] if len(item) >= 3 else None
            details = item[3] if len(item) >= 4 else {}
        else:
            continue
        try:
            price_f = float(price)
            size_f = float(size or 0)
        except (TypeError, ValueError):
            continue
        levels.append(
            {
                "order_count": None if order_count is None else int(order_count),
                "order_details": details if isinstance(details, dict) else {},
                "price": price_f,
                "size": size_f,
            }
        )
    return levels
