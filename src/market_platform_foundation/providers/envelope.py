"""Provider event envelope builder aligned with canonical contracts."""

from __future__ import annotations

from typing import Any

from ..contracts.envelope import validate_envelope
from ..donor_patterns.edgar_whale import normalize_edgar_filing
from .contracts import SymbolMapping

PROVIDER_EVENT_SCHEMA = "1.0.0"
PROVIDER_NORMALIZATION_VERSION = "providers/envelope/1.0.0"


def build_provider_metadata(
    *,
    provider_id: str,
    entitlement: str,
    event_time_ns: int,
    receive_time_ns: int,
    symbol_mapping: SymbolMapping,
    quality_state: str = "GOOD",
    raw_source_reference: str,
) -> dict[str, Any]:
    return {
        "entitlement": entitlement,
        "event_time_ns": event_time_ns,
        "latency_quality": {"quality_state": quality_state},
        "provider_id": provider_id,
        "raw_source_reference": raw_source_reference,
        "receive_time_ns": receive_time_ns,
        "symbol_mapping": {
            "instrument_id": symbol_mapping.instrument_id,
            "provider_symbol": symbol_mapping.provider_symbol,
            "venue_id": symbol_mapping.venue_id,
        },
    }


def build_disclosure_envelope(
    *,
    normalized_event_id: str,
    source_record_id: str,
    instrument_id: str,
    event_time_ns: int,
    available_time_ns: int,
    ingest_run_id: str,
    provider_metadata: dict[str, Any],
    disclosure_event: dict[str, Any],
) -> dict[str, Any]:
    envelope = {
        "available_time": available_time_ns,
        "channel_id": str(
            provider_metadata.get("symbol_mapping", {}).get("provider_symbol", instrument_id)
        ),
        "disclosure_event": disclosure_event,
        "event_time": event_time_ns,
        "event_type": "DISCLOSURE_EVENT",
        "historical_ingested_time": available_time_ns,
        "ingest_run_id": ingest_run_id,
        "instrument_id": instrument_id,
        "live_received_time": None,
        "normalization_version": PROVIDER_NORMALIZATION_VERSION,
        "normalized_event_id": normalized_event_id,
        "operation": "UPSERT",
        "provider_metadata": provider_metadata,
        "publisher_id": str(provider_metadata.get("provider_id", "unknown")),
        "quality_observation_refs": [],
        "raw_reference": str(provider_metadata.get("raw_source_reference", "")),
        "schema_version": PROVIDER_EVENT_SCHEMA,
        "source_instance_id": str(provider_metadata.get("provider_id", "unknown")),
        "source_publish_time": event_time_ns,
        "source_record_id": source_record_id,
        "source_revision_id": disclosure_event.get("source_revision_id", "1"),
        "source_sequence": None,
        "supersedes_event_id": None,
        "venue_id": str(
            provider_metadata.get("symbol_mapping", {}).get("venue_id", "US_EQUITY")
        ),
    }
    timestamp_states = {
        "event_time": "REQUIRED",
        "source_publish_time": "REQUIRED",
        "live_received_time": "FORBIDDEN",
        "historical_ingested_time": "REQUIRED",
        "available_time": "REQUIRED",
    }
    reasons = validate_envelope(
        envelope,
        timestamp_states=timestamp_states,
        acquisition_mode="historical",
    )
    if reasons:
        raise ValueError(f"PROVIDER_ENVELOPE_INVALID:{','.join(reasons)}")
    return envelope


def build_order_flow_envelope(
    *,
    normalized_event_id: str,
    source_record_id: str,
    instrument_id: str,
    event_time_ns: int,
    available_time_ns: int,
    ingest_run_id: str,
    provider_metadata: dict[str, Any],
    whale_event: dict[str, Any],
) -> dict[str, Any]:
    envelope = {
        "available_time": available_time_ns,
        "channel_id": str(
            provider_metadata.get("symbol_mapping", {}).get("provider_symbol", instrument_id)
        ),
        "event_time": event_time_ns,
        "event_type": "ORDER_FLOW_EVENT",
        "historical_ingested_time": available_time_ns,
        "ingest_run_id": ingest_run_id,
        "instrument_id": instrument_id,
        "live_received_time": None,
        "normalization_version": PROVIDER_NORMALIZATION_VERSION,
        "normalized_event_id": normalized_event_id,
        "operation": "UPSERT",
        "provider_metadata": provider_metadata,
        "publisher_id": str(provider_metadata.get("provider_id", "unknown")),
        "quality_observation_refs": [],
        "raw_reference": str(provider_metadata.get("raw_source_reference", "")),
        "schema_version": PROVIDER_EVENT_SCHEMA,
        "source_instance_id": str(provider_metadata.get("provider_id", "unknown")),
        "source_publish_time": event_time_ns,
        "source_record_id": source_record_id,
        "source_revision_id": whale_event.get("source_revision_id", "1"),
        "source_sequence": None,
        "supersedes_event_id": None,
        "venue_id": str(
            provider_metadata.get("symbol_mapping", {}).get("venue_id", "US_EQUITY")
        ),
        "whale_event": whale_event,
    }
    timestamp_states = {
        "event_time": "REQUIRED",
        "source_publish_time": "REQUIRED",
        "live_received_time": "FORBIDDEN",
        "historical_ingested_time": "REQUIRED",
        "available_time": "REQUIRED",
    }
    reasons = validate_envelope(
        envelope,
        timestamp_states=timestamp_states,
        acquisition_mode="historical",
    )
    if reasons:
        raise ValueError(f"PROVIDER_ENVELOPE_INVALID:{','.join(reasons)}")
    return envelope


def build_options_envelope(
    *,
    normalized_event_id: str,
    source_record_id: str,
    instrument_id: str,
    event_time_ns: int,
    available_time_ns: int,
    ingest_run_id: str,
    provider_metadata: dict[str, Any],
    whale_event: dict[str, Any],
) -> dict[str, Any]:
    envelope = {
        "available_time": available_time_ns,
        "channel_id": str(
            provider_metadata.get("symbol_mapping", {}).get("provider_symbol", instrument_id)
        ),
        "event_time": event_time_ns,
        "event_type": "OPTIONS_EVENT",
        "historical_ingested_time": available_time_ns,
        "ingest_run_id": ingest_run_id,
        "instrument_id": instrument_id,
        "live_received_time": None,
        "normalization_version": PROVIDER_NORMALIZATION_VERSION,
        "normalized_event_id": normalized_event_id,
        "operation": "UPSERT",
        "provider_metadata": provider_metadata,
        "publisher_id": str(provider_metadata.get("provider_id", "unknown")),
        "quality_observation_refs": [],
        "raw_reference": str(provider_metadata.get("raw_source_reference", "")),
        "schema_version": PROVIDER_EVENT_SCHEMA,
        "source_instance_id": str(provider_metadata.get("provider_id", "unknown")),
        "source_publish_time": event_time_ns,
        "source_record_id": source_record_id,
        "source_revision_id": whale_event.get("source_revision_id", "1"),
        "source_sequence": None,
        "supersedes_event_id": None,
        "venue_id": str(
            provider_metadata.get("symbol_mapping", {}).get("venue_id", "US_EQUITY")
        ),
        "whale_event": whale_event,
    }
    timestamp_states = {
        "event_time": "REQUIRED",
        "source_publish_time": "REQUIRED",
        "live_received_time": "FORBIDDEN",
        "historical_ingested_time": "REQUIRED",
        "available_time": "REQUIRED",
    }
    reasons = validate_envelope(
        envelope,
        timestamp_states=timestamp_states,
        acquisition_mode="historical",
    )
    if reasons:
        raise ValueError(f"PROVIDER_ENVELOPE_INVALID:{','.join(reasons)}")
    return envelope


def activity_to_options_event(
    *,
    event_time: str,
    strike: float,
    expiry: str,
    option_type: str,
    volume: int,
    open_interest: int,
    volume_oi_ratio: float,
    iv_rank: float,
    bid: float,
    ask: float,
    liquidity_ok: bool,
    liquidity_reasons: list[str],
    confirmation_score: float,
    direction_label: str,
    volume_ratio: float,
    skew_signal: float,
    source: str,
    source_revision_id: str = "1",
) -> dict[str, Any]:
    return {
        "ask": ask,
        "bid": bid,
        "confirmation_score": round(confirmation_score, 2),
        "direction_label": direction_label,
        "epistemic_class": "DERIVED",
        "event_time": event_time,
        "expiry": expiry,
        "family": "options",
        "iv_rank": iv_rank,
        "liquidity_ok": liquidity_ok,
        "liquidity_reasons": liquidity_reasons,
        "open_interest": open_interest,
        "option_type": option_type,
        "research_only": True,
        "skew_signal": skew_signal,
        "source": source,
        "source_revision_id": source_revision_id,
        "strike": strike,
        "volume": volume,
        "volume_oi_ratio": volume_oi_ratio,
        "volume_ratio": volume_ratio,
    }


def bar_to_order_flow_event(
    *,
    bar_time: str,
    delta: float,
    cumulative_delta: float,
    volume: float,
    quality: str,
    source: str,
    aggressor_provenance: str,
    source_revision_id: str = "1",
) -> dict[str, Any]:
    return {
        "aggressor_provenance": aggressor_provenance,
        "bar_time": bar_time,
        "cumulative_delta": cumulative_delta,
        "delta": delta,
        "epistemic_class": "DERIVED",
        "family": "order_flow",
        "quality": quality,
        "research_only": True,
        "source": source,
        "source_revision_id": source_revision_id,
        "volume": volume,
    }


def filing_to_disclosure_event(
    *,
    form_type: str,
    filer: str,
    issuer: str,
    accepted_at: str,
    source_url: str,
    accession_number: str,
    is_amendment: bool = False,
    transaction_code: str | None = None,
    source_revision_id: str = "1",
) -> dict[str, Any]:
    normalized = normalize_edgar_filing(
        form_type=form_type,
        filer=filer,
        issuer=issuer,
        accepted_at=accepted_at,
        source_url=source_url,
        is_amendment=is_amendment,
        transaction_code=transaction_code,
    )
    return {
        **normalized,
        "accession_number": accession_number,
        "family": "regulatory_disclosure",
        "form_type": form_type,
        "source_revision_id": source_revision_id,
    }


__all__ = [
    "PROVIDER_EVENT_SCHEMA",
    "PROVIDER_NORMALIZATION_VERSION",
    "activity_to_options_event",
    "bar_to_order_flow_event",
    "build_disclosure_envelope",
    "build_options_envelope",
    "build_order_flow_envelope",
    "build_provider_metadata",
    "filing_to_disclosure_event",
]
