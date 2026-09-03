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
    venue_id: str = "US_EQUITY",
) -> dict[str, Any]:
    """Attach ADR-PROV-001 provider metadata to canonical chain contract dict."""
    symbol_mapping = SymbolMapping(
        instrument_id=instrument_id,
        provider_symbol=instrument_id,
        venue_id=venue_id,
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
    ofi_method: str | None = None,
    ofi_version: str | None = None,
    book_state_valid: bool | None = None,
    liquidity_method: str | None = None,
    liquidity_version: str | None = None,
    net_depth_delta: float | None = None,
    depth_withdrawal: float | None = None,
    depth_replenishment: float | None = None,
    fragility_score: float | None = None,
    resiliency_score: float | None = None,
    total_depth: float | None = None,
    spread_delta: float | None = None,
    impact_method: str | None = None,
    impact_version: str | None = None,
    absorption_score: float | None = None,
    exhaustion_score: float | None = None,
    price_efficiency: float | None = None,
    mid_delta: float | None = None,
    aggression_signed_volume: float | None = None,
    impact_regime: str | None = None,
    impact_quality_flags: list[str] | None = None,
    opposing_replenishment: bool | None = None,
    forecast_method: str | None = None,
    forecast_version: str | None = None,
    forecast_horizon_seconds: int | None = None,
    expected_mid_delta: float | None = None,
    direction_bias: str | None = None,
    continuation_probability: float | None = None,
    reversal_probability: float | None = None,
    volatility_proxy: float | None = None,
    composite_bias: float | None = None,
    model_confidence: float | None = None,
    forecast_quality_flags: list[str] | None = None,
    execution_method: str | None = None,
    execution_version: str | None = None,
    book_model_version: str | None = None,
    queue_model_version: str | None = None,
    aggressive_fill_probability: float | None = None,
    passive_fill_probability: float | None = None,
    expected_slippage_spread_fraction: float | None = None,
    expected_slippage_absolute: float | None = None,
    adverse_selection_risk: float | None = None,
    touch_depth_bid: float | None = None,
    touch_depth_ask: float | None = None,
    displayed_depth_consumed_fraction: float | None = None,
    execution_quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
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
    if ofi_method is not None:
        event["ofi_method"] = ofi_method
    if ofi_version is not None:
        event["ofi_version"] = ofi_version
    if book_state_valid is not None:
        event["book_state_valid"] = book_state_valid
    if liquidity_method is not None:
        event["liquidity_method"] = liquidity_method
    if liquidity_version is not None:
        event["liquidity_version"] = liquidity_version
    if net_depth_delta is not None:
        event["net_depth_delta"] = net_depth_delta
    if depth_withdrawal is not None:
        event["depth_withdrawal"] = depth_withdrawal
    if depth_replenishment is not None:
        event["depth_replenishment"] = depth_replenishment
    if fragility_score is not None:
        event["fragility_score"] = fragility_score
    if resiliency_score is not None:
        event["resiliency_score"] = resiliency_score
    if total_depth is not None:
        event["total_depth"] = total_depth
    if spread_delta is not None:
        event["spread_delta"] = spread_delta
    if impact_method is not None:
        event["impact_method"] = impact_method
    if impact_version is not None:
        event["impact_version"] = impact_version
    if absorption_score is not None:
        event["absorption_score"] = absorption_score
    if exhaustion_score is not None:
        event["exhaustion_score"] = exhaustion_score
    if price_efficiency is not None:
        event["price_efficiency"] = price_efficiency
    if mid_delta is not None:
        event["mid_delta"] = mid_delta
    if aggression_signed_volume is not None:
        event["aggression_signed_volume"] = aggression_signed_volume
    if impact_regime is not None:
        event["impact_regime"] = impact_regime
    if impact_quality_flags is not None:
        event["impact_quality_flags"] = impact_quality_flags
    if opposing_replenishment is not None:
        event["opposing_replenishment"] = opposing_replenishment
    if forecast_method is not None:
        event["forecast_method"] = forecast_method
    if forecast_version is not None:
        event["forecast_version"] = forecast_version
    if forecast_horizon_seconds is not None:
        event["forecast_horizon_seconds"] = forecast_horizon_seconds
    if expected_mid_delta is not None:
        event["expected_mid_delta"] = expected_mid_delta
    if direction_bias is not None:
        event["direction_bias"] = direction_bias
    if continuation_probability is not None:
        event["continuation_probability"] = continuation_probability
    if reversal_probability is not None:
        event["reversal_probability"] = reversal_probability
    if volatility_proxy is not None:
        event["volatility_proxy"] = volatility_proxy
    if composite_bias is not None:
        event["composite_bias"] = composite_bias
    if model_confidence is not None:
        event["model_confidence"] = model_confidence
    if forecast_quality_flags is not None:
        event["forecast_quality_flags"] = forecast_quality_flags
    if execution_method is not None:
        event["execution_method"] = execution_method
    if execution_version is not None:
        event["execution_version"] = execution_version
    if book_model_version is not None:
        event["book_model_version"] = book_model_version
    if queue_model_version is not None:
        event["queue_model_version"] = queue_model_version
    if aggressive_fill_probability is not None:
        event["aggressive_fill_probability"] = aggressive_fill_probability
    if passive_fill_probability is not None:
        event["passive_fill_probability"] = passive_fill_probability
    if expected_slippage_spread_fraction is not None:
        event["expected_slippage_spread_fraction"] = expected_slippage_spread_fraction
    if expected_slippage_absolute is not None:
        event["expected_slippage_absolute"] = expected_slippage_absolute
    if adverse_selection_risk is not None:
        event["adverse_selection_risk"] = adverse_selection_risk
    if touch_depth_bid is not None:
        event["touch_depth_bid"] = touch_depth_bid
    if touch_depth_ask is not None:
        event["touch_depth_ask"] = touch_depth_ask
    if displayed_depth_consumed_fraction is not None:
        event["displayed_depth_consumed_fraction"] = displayed_depth_consumed_fraction
    if execution_quality_flags is not None:
        event["execution_quality_flags"] = execution_quality_flags
    return event


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
    ofi_method: str | None = None,
    ofi_version: str | None = None,
    book_state_valid: bool | None = None,
    liquidity_method: str | None = None,
    liquidity_version: str | None = None,
    net_depth_delta: float | None = None,
    depth_withdrawal: float | None = None,
    depth_replenishment: float | None = None,
    fragility_score: float | None = None,
    resiliency_score: float | None = None,
    total_depth: float | None = None,
    spread_delta: float | None = None,
    impact_method: str | None = None,
    impact_version: str | None = None,
    absorption_score: float | None = None,
    exhaustion_score: float | None = None,
    price_efficiency: float | None = None,
    mid_delta: float | None = None,
    aggression_signed_volume: float | None = None,
    impact_regime: str | None = None,
    impact_quality_flags: list[str] | None = None,
    opposing_replenishment: bool | None = None,
    forecast_method: str | None = None,
    forecast_version: str | None = None,
    forecast_horizon_seconds: int | None = None,
    expected_mid_delta: float | None = None,
    direction_bias: str | None = None,
    continuation_probability: float | None = None,
    reversal_probability: float | None = None,
    volatility_proxy: float | None = None,
    composite_bias: float | None = None,
    model_confidence: float | None = None,
    forecast_quality_flags: list[str] | None = None,
    execution_method: str | None = None,
    execution_version: str | None = None,
    book_model_version: str | None = None,
    queue_model_version: str | None = None,
    aggressive_fill_probability: float | None = None,
    passive_fill_probability: float | None = None,
    expected_slippage_spread_fraction: float | None = None,
    expected_slippage_absolute: float | None = None,
    adverse_selection_risk: float | None = None,
    touch_depth_bid: float | None = None,
    touch_depth_ask: float | None = None,
    displayed_depth_consumed_fraction: float | None = None,
    execution_quality_flags: list[str] | None = None,
    queue_method: str | None = None,
    queue_version: str | None = None,
    queue_imbalance_mbo: float | None = None,
    mbo_capability_available: bool | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "ask_size": ask_size,
        "best_ask": best_ask,
        "best_bid": best_bid,
        "bid_size": bid_size,
        "book_pressure_side": book_pressure_side,
        "canonical_family": "futures_depth",
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
    if ofi_method is not None:
        event["ofi_method"] = ofi_method
    if ofi_version is not None:
        event["ofi_version"] = ofi_version
    if book_state_valid is not None:
        event["book_state_valid"] = book_state_valid
    if liquidity_method is not None:
        event["liquidity_method"] = liquidity_method
    if liquidity_version is not None:
        event["liquidity_version"] = liquidity_version
    if net_depth_delta is not None:
        event["net_depth_delta"] = net_depth_delta
    if depth_withdrawal is not None:
        event["depth_withdrawal"] = depth_withdrawal
    if depth_replenishment is not None:
        event["depth_replenishment"] = depth_replenishment
    if fragility_score is not None:
        event["fragility_score"] = fragility_score
    if resiliency_score is not None:
        event["resiliency_score"] = resiliency_score
    if total_depth is not None:
        event["total_depth"] = total_depth
    if spread_delta is not None:
        event["spread_delta"] = spread_delta
    if impact_method is not None:
        event["impact_method"] = impact_method
    if impact_version is not None:
        event["impact_version"] = impact_version
    if absorption_score is not None:
        event["absorption_score"] = absorption_score
    if exhaustion_score is not None:
        event["exhaustion_score"] = exhaustion_score
    if price_efficiency is not None:
        event["price_efficiency"] = price_efficiency
    if mid_delta is not None:
        event["mid_delta"] = mid_delta
    if aggression_signed_volume is not None:
        event["aggression_signed_volume"] = aggression_signed_volume
    if impact_regime is not None:
        event["impact_regime"] = impact_regime
    if impact_quality_flags is not None:
        event["impact_quality_flags"] = impact_quality_flags
    if opposing_replenishment is not None:
        event["opposing_replenishment"] = opposing_replenishment
    if forecast_method is not None:
        event["forecast_method"] = forecast_method
    if forecast_version is not None:
        event["forecast_version"] = forecast_version
    if forecast_horizon_seconds is not None:
        event["forecast_horizon_seconds"] = forecast_horizon_seconds
    if expected_mid_delta is not None:
        event["expected_mid_delta"] = expected_mid_delta
    if direction_bias is not None:
        event["direction_bias"] = direction_bias
    if continuation_probability is not None:
        event["continuation_probability"] = continuation_probability
    if reversal_probability is not None:
        event["reversal_probability"] = reversal_probability
    if volatility_proxy is not None:
        event["volatility_proxy"] = volatility_proxy
    if composite_bias is not None:
        event["composite_bias"] = composite_bias
    if model_confidence is not None:
        event["model_confidence"] = model_confidence
    if forecast_quality_flags is not None:
        event["forecast_quality_flags"] = forecast_quality_flags
    if execution_method is not None:
        event["execution_method"] = execution_method
    if execution_version is not None:
        event["execution_version"] = execution_version
    if book_model_version is not None:
        event["book_model_version"] = book_model_version
    if queue_model_version is not None:
        event["queue_model_version"] = queue_model_version
    if aggressive_fill_probability is not None:
        event["aggressive_fill_probability"] = aggressive_fill_probability
    if passive_fill_probability is not None:
        event["passive_fill_probability"] = passive_fill_probability
    if expected_slippage_spread_fraction is not None:
        event["expected_slippage_spread_fraction"] = expected_slippage_spread_fraction
    if expected_slippage_absolute is not None:
        event["expected_slippage_absolute"] = expected_slippage_absolute
    if adverse_selection_risk is not None:
        event["adverse_selection_risk"] = adverse_selection_risk
    if touch_depth_bid is not None:
        event["touch_depth_bid"] = touch_depth_bid
    if touch_depth_ask is not None:
        event["touch_depth_ask"] = touch_depth_ask
    if displayed_depth_consumed_fraction is not None:
        event["displayed_depth_consumed_fraction"] = displayed_depth_consumed_fraction
    if execution_quality_flags is not None:
        event["execution_quality_flags"] = execution_quality_flags
    if queue_method is not None:
        event["queue_method"] = queue_method
    if queue_version is not None:
        event["queue_version"] = queue_version
    if queue_imbalance_mbo is not None:
        event["queue_imbalance_mbo"] = queue_imbalance_mbo
    if mbo_capability_available is not None:
        event["mbo_capability_available"] = mbo_capability_available
    return event


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
    transaction_date: str | None = None,
    shares: float | int | None = None,
    price_per_share: float | None = None,
    shares_owned_following: float | int | None = None,
    is_10b5_1: bool | None = None,
    stake_percent: float | None = None,
    campaign_objective: str | None = None,
    is_passive: bool | None = None,
    quarter_end: str | None = None,
    holdings: list[dict[str, Any]] | None = None,
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
    event: dict[str, Any] = {
        **normalized,
        "accession_number": accession_number,
        "family": "regulatory_disclosure",
        "form_type": form_type,
        "source_revision_id": source_revision_id,
    }
    if transaction_code is not None:
        event["transaction_code"] = transaction_code
    if transaction_date is not None:
        event["transaction_date"] = transaction_date
    if shares is not None:
        event["shares"] = shares
    if price_per_share is not None:
        event["price_per_share"] = price_per_share
    if shares_owned_following is not None:
        event["shares_owned_following"] = shares_owned_following
    if is_10b5_1 is not None:
        event["is_10b5_1"] = is_10b5_1
    if stake_percent is not None:
        event["stake_percent"] = stake_percent
    if campaign_objective is not None:
        event["campaign_objective"] = campaign_objective
    if is_passive is not None:
        event["is_passive"] = is_passive
    if quarter_end is not None:
        event["quarter_end"] = quarter_end
    if holdings is not None:
        event["holdings"] = holdings
    return event


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
