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


def enrich_chain_contract_event(
    contract: dict[str, Any],
    *,
    provider_id: str,
    entitlement: str,
    instrument_id: str,
    event_time_ns: int,
    receive_time_ns: int,
    raw_source_reference: str,
    quality_flags: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Attach ADR-PROV-001 provider metadata to canonical chain contract dict."""
    symbol_mapping = SymbolMapping(
        instrument_id=instrument_id,
        provider_symbol=instrument_id,
        venue_id="US_EQUITY",
    )
    metadata = build_provider_metadata(
        provider_id=provider_id,
        entitlement=entitlement,
        event_time_ns=event_time_ns,
        receive_time_ns=receive_time_ns,
        symbol_mapping=symbol_mapping,
        raw_source_reference=raw_source_reference,
        quality_state="GOOD" if not quality_flags else "DEGRADED",
    )
    enriched = dict(contract)
    enriched["entitlement"] = entitlement
    enriched["provider_metadata"] = metadata
    enriched["event_time_ns"] = event_time_ns
    if quality_flags:
        existing = enriched.get("quality_flags", [])
        if isinstance(existing, list):
            enriched["quality_flags"] = sorted(set(existing) | set(quality_flags))
    return enriched


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


def build_large_transaction_envelope(
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
        "event_type": "LARGE_TRANSACTION_EVENT",
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


def print_to_large_transaction_event(
    *,
    event_time: str,
    print_size: float,
    price: float,
    side: str,
    reference_type: str,
    reference_value: float,
    size_ratio_value: float,
    threshold_ok: bool,
    threshold_reasons: list[str],
    direction_label: str,
    aggressor_provenance: str,
    source: str,
    source_revision_id: str = "1",
) -> dict[str, Any]:
    return {
        "aggressor_provenance": aggressor_provenance,
        "direction_label": direction_label,
        "epistemic_class": "DERIVED",
        "event_time": event_time,
        "family": "large_transactions",
        "price": price,
        "print_size": print_size,
        "reference_type": reference_type,
        "reference_value": reference_value,
        "research_only": True,
        "side": side,
        "size_ratio": size_ratio_value,
        "source": source,
        "source_revision_id": source_revision_id,
        "threshold_gate_ok": threshold_ok,
        "threshold_reasons": threshold_reasons,
    }


def build_order_book_envelope(
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
        "event_type": "ORDER_BOOK_EVENT",
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


def build_futures_envelope(
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
        "event_type": "FUTURES_DEPTH_EVENT",
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
            provider_metadata.get("symbol_mapping", {}).get("venue_id", "CME")
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


def snapshot_to_order_book_event(
    *,
    event_time: str,
    level_count: int,
    best_bid: float,
    best_ask: float,
    bid_size: float,
    ask_size: float,
    imbalance_ratio: float,
    ofi_value: float,
    direction_label: str,
    snapshot_provenance: str,
    source_revision_id: str = "1",
    book_pressure_side: str = "neutral",
    interpretation_policy: str = "momentum",
) -> dict[str, Any]:
    return {
        "ask_size": ask_size,
        "best_ask": best_ask,
        "best_bid": best_bid,
        "bid_size": bid_size,
        "book_pressure_side": book_pressure_side,
        "direction_label": direction_label,
        "epistemic_class": "DERIVED",
        "event_time": event_time,
        "family": "order_book",
        "imbalance_ratio": imbalance_ratio,
        "interpretation_policy": interpretation_policy,
        "level_count": level_count,
        "ofi_value": ofi_value,
        "research_only": True,
        "snapshot_provenance": snapshot_provenance,
        "source_revision_id": source_revision_id,
    }


def snapshot_to_futures_event(
    *,
    event_time: str,
    contract_month: str,
    exchange: str,
    session_state: str,
    level_count: int,
    best_bid: float,
    best_ask: float,
    bid_size: float,
    ask_size: float,
    imbalance_ratio: float,
    imbalance_signal: str,
    ofi_value: float,
    rth: bool,
    snapshot_provenance: str,
    source_revision_id: str = "1",
    book_pressure_side: str = "neutral",
    interpretation_policy: str = "contrarian_depth",
) -> dict[str, Any]:
    return {
        "ask_size": ask_size,
        "best_ask": best_ask,
        "best_bid": best_bid,
        "bid_size": bid_size,
        "book_pressure_side": book_pressure_side,
        "contract_month": contract_month,
        "data_kind": "depth_derived",
        "epistemic_class": "DERIVED",
        "event_time": event_time,
        "exchange": exchange,
        "family": "futures_positioning",
        "imbalance_ratio": imbalance_ratio,
        "imbalance_signal": imbalance_signal,
        "interpretation_policy": interpretation_policy,
        "lane": "futures_depth",
        "level_count": level_count,
        "ofi_value": ofi_value,
        "research_only": True,
        "rth": rth,
        "session_state": session_state,
        "snapshot_provenance": snapshot_provenance,
        "source_revision_id": source_revision_id,
        "whale_family_note": (
            "Legacy whale family id futures_positioning; payload is L2 depth not COT positioning."
        ),
    }


def build_catalyst_envelope(
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
        "event_type": "CATALYST_EVENT",
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


def catalyst_to_event(
    *,
    event_time: str,
    catalyst_type: str,
    headline: str,
    source: str,
    confidence: float,
    lean: str,
    direction_label: str,
    gate_ok: bool,
    gate_reasons: list[str],
    signal_source: str,
    source_revision_id: str = "1",
) -> dict[str, Any]:
    return {
        "catalyst_type": catalyst_type,
        "confidence": round(confidence, 4),
        "direction_label": direction_label,
        "epistemic_class": "INFERRED",
        "event_time": event_time,
        "family": "public_catalyst",
        "gate_ok": gate_ok,
        "gate_reasons": gate_reasons,
        "headline": headline,
        "lean": lean,
        "research_only": True,
        "signal_source": signal_source,
        "source": source,
        "source_revision_id": source_revision_id,
    }


def build_fund_etf_envelope(
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
        "event_type": "FUND_ETF_EVENT",
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


def event_to_fund_etf_event(
    *,
    event_time: str,
    event_type: str,
    etf_ticker: str,
    flow_direction: str,
    flow_proxy_ratio: float,
    reference_type: str,
    reference_value: float,
    correlation_20d: float,
    regime_label: str,
    direction_label: str,
    source: str,
    source_revision_id: str = "1",
) -> dict[str, Any]:
    return {
        "correlation_20d": correlation_20d,
        "direction_label": direction_label,
        "epistemic_class": "DERIVED",
        "etf_ticker": etf_ticker,
        "event_time": event_time,
        "event_type": event_type,
        "family": "fund_etf_cross_asset",
        "flow_direction": flow_direction,
        "flow_proxy_ratio": flow_proxy_ratio,
        "reference_type": reference_type,
        "reference_value": reference_value,
        "regime_label": regime_label,
        "research_only": True,
        "source": source,
        "source_revision_id": source_revision_id,
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
    "build_catalyst_envelope",
    "build_disclosure_envelope",
    "build_fund_etf_envelope",
    "build_futures_envelope",
    "catalyst_to_event",
    "enrich_chain_contract_event",
    "event_to_fund_etf_event",
    "build_large_transaction_envelope",
    "build_options_envelope",
    "build_order_book_envelope",
    "build_order_flow_envelope",
    "build_provider_metadata",
    "filing_to_disclosure_event",
    "print_to_large_transaction_event",
    "snapshot_to_futures_event",
    "snapshot_to_order_book_event",
]
