"""Moomoo/OpenD capture record normalization (BUILD 03)."""

from __future__ import annotations

import copy
from typing import Any

from ....market_data.normalization import (
    PROVIDER_ID as MOOMOO_PROVIDER_ID,
    canonical_symbol,
    classified_trade_from_ticker,
    levels_from_order_book,
    l1_from_quote,
)
from ....market_data.timestamps import clocks_from_capture
from ...contracts.common import QualityState, SourceReference
from ..errors import NormalizationDiagnostic, NormalizationErrorCode
from ..event_builder import build_event_v1
from ..identity import derive_event_id_from_provider, hash_raw_payload
from ..models import (
    AvailabilityBasis,
    AvailabilityConfidence,
    IngestionMode,
    NormalizationContext,
    NormalizationResult,
    ProviderProvenance,
)
from ..numeric import normalize_optional_float, sanitize_payload
from ..timestamps import derive_available_time_ns

ADAPTER_ID = "moomoo.capture"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/moomoo/1"

_CAPABILITY_TO_EVENT_TYPE = {
    "QUOTE": "QUOTE",
    "TICKER": "TRADE",
    "ORDER_BOOK": "BOOK",
    "MARKET_DATA_EVENT": "MARKET_DATA_EVENT",
}


def _map_capability(raw: dict[str, Any]) -> str | None:
    capability = str(raw.get("capability") or "MARKET_DATA_EVENT").upper()
    return _CAPABILITY_TO_EVENT_TYPE.get(capability)


def _quote_payload(raw: dict[str, Any]) -> dict[str, Any]:
    l1 = l1_from_quote(raw.get("raw_payload") or raw)
    payload: dict[str, Any] = {}
    if l1 is not None:
        payload["bid"] = l1.best_bid
        payload["ask"] = l1.best_ask
        payload["bid_size"] = l1.bid_size
        payload["ask_size"] = l1.ask_size
        payload["midpoint"] = l1.mid
        payload["spread"] = l1.spread
    for key in ("bid_price", "ask_price", "bid_vol", "ask_vol", "last_price", "volume"):
        val, _ = normalize_optional_float((raw.get("raw_payload") or raw).get(key), field_name=key)
        if val is not None and key not in payload:
            payload[key.replace("_price", "").replace("_vol", "_size")] = val
    return sanitize_payload(payload)


def _trade_payload(raw: dict[str, Any]) -> dict[str, Any]:
    trade = classified_trade_from_ticker(raw.get("raw_payload") or raw)
    return sanitize_payload(
        {
            "price": trade.price,
            "quantity": trade.quantity,
            "aggressor_side": trade.aggressor_side.value,
            "signed_volume": trade.signed_volume,
            "trade_id": trade.trade_id,
        }
    )


def _book_payload(raw: dict[str, Any]) -> dict[str, Any]:
    bids, asks = levels_from_order_book(raw.get("raw_payload") or raw)
    return sanitize_payload({"bids": bids, "asks": asks})


def normalize_moomoo_capture(
    record: dict[str, Any],
    *,
    context: NormalizationContext,
) -> NormalizationResult:
    """Normalize a Moomoo/OpenD capture record to EventV1."""
    raw = copy.deepcopy(record)
    capability = _map_capability(raw)
    if capability is None:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                    message=f"Unsupported Moomoo capability: {raw.get('capability')}",
                ),
            ),
        )

    provider_symbol = str(raw.get("provider_symbol") or raw.get("instrument_id") or "")
    if not provider_symbol:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.INVALID_INSTRUMENT,
                    message="provider_symbol is required",
                    field="provider_symbol",
                ),
            ),
        )

    mapping = canonical_symbol(provider_symbol)
    clocks = clocks_from_capture(raw)
    event_time_ns = clocks.event_time_ns or clocks.provider_time_ns or context.received_time_ns
    provider_time_ns = clocks.provider_time_ns
    sequence = raw.get("sequence")
    source_record_id = str(sequence if sequence is not None else event_time_ns)

    effective_context = context
    if context.ingestion_mode in {IngestionMode.REPLAY, IngestionMode.FIXTURE}:
        effective_context = NormalizationContext(
            received_time_ns=context.received_time_ns,
            ingestion_mode=IngestionMode.HISTORICAL_RECONSTRUCTED,
            adapter_version=context.adapter_version,
            raw_payload_ref=context.raw_payload_ref,
            historical_available_time_ns=clocks.received_time_ns or context.received_time_ns,
            availability_basis=AvailabilityBasis.RECONSTRUCTED_FROM_SOURCE,
            availability_confidence=AvailabilityConfidence.DERIVED,
        )

    try:
        available_time_ns, availability = derive_available_time_ns(
            context=effective_context,
            event_time_ns=event_time_ns,
            provider_time_ns=provider_time_ns,
        )
    except ValueError:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNDETERMINABLE_AVAILABILITY,
                    message="Could not derive available_time_ns",
                ),
            ),
        )

    if capability == "QUOTE":
        payload = _quote_payload(raw)
    elif capability == "TRADE":
        payload = _trade_payload(raw)
    elif capability == "BOOK":
        payload = _book_payload(raw)
    else:
        payload = sanitize_payload(dict(raw.get("raw_payload") or {}))

    event_id = derive_event_id_from_provider(
        provider_id=str(raw.get("provider") or MOOMOO_PROVIDER_ID),
        venue_id=mapping.venue_id,
        source_record_id=source_record_id,
        event_family=capability,
        channel_id=mapping.provider_symbol,
        publisher_id=str(raw.get("provider") or MOOMOO_PROVIDER_ID),
    )

    provenance = ProviderProvenance(
        provider_id=str(raw.get("provider") or MOOMOO_PROVIDER_ID),
        source_record_type="moomoo_capture",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_symbol=mapping.provider_symbol,
        provider_native_record_id=source_record_id,
        provider_event_type=str(raw.get("capability") or capability),
        raw_payload_ref=context.raw_payload_ref,
        raw_payload_hash=hash_raw_payload(raw),
        availability=availability,
        ingestion_mode=context.ingestion_mode,
    )

    source = SourceReference(
        provider_id=provenance.provider_id,
        source_type=capability,
        source_record_id=source_record_id,
        raw_reference=context.raw_payload_ref,
    )

    event = build_event_v1(
        event_id=event_id,
        event_type=capability,
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload,
        source=source,
        provenance=provenance,
        instrument_id=mapping.instrument_id,
        provider_time_ns=provider_time_ns,
        received_time_ns=context.received_time_ns,
        quality_state=QualityState.GOOD if not raw.get("quality_flags") else QualityState.DEGRADED,
        quality_flags=tuple(str(f) for f in (raw.get("quality_flags") or ())),
    )
    return NormalizationResult(event=event, provenance=provenance)


SUPPORTED_RECORD_TYPES = frozenset({"QUOTE", "TICKER", "ORDER_BOOK", "moomoo_capture"})


__all__ = ["SUPPORTED_RECORD_TYPES", "normalize_moomoo_capture"]
