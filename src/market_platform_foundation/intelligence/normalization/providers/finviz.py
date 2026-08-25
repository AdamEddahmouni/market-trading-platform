"""Finviz discovery/screener normalization (BUILD 03)."""

from __future__ import annotations

import copy
from typing import Any

from ....finviz.symbols import finviz_to_canonical
from ...contracts.common import QualityState, SourceReference
from ..errors import NormalizationDiagnostic, NormalizationErrorCode
from ..event_builder import build_event_v1
from ..identity import derive_event_id_composite, hash_raw_payload
from ..models import (
    AvailabilityBasis,
    AvailabilityConfidence,
    NormalizationContext,
    NormalizationResult,
    ProviderProvenance,
    SourcePrecision,
)
from ..numeric import sanitize_payload
from ..timestamps import derive_available_time_ns, iso_string_to_ns

ADAPTER_ID = "finviz.discovery"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/finviz/1"
PROVIDER_ID = "finviz.elite"


def normalize_finviz_candidate(
    candidate: dict[str, Any],
    *,
    context: NormalizationContext,
    run_id: str = "",
) -> NormalizationResult:
    raw = copy.deepcopy(candidate)
    ticker = str(raw.get("provider_symbol") or raw.get("instrument_id") or raw.get("ticker") or "")
    if not ticker:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.INVALID_INSTRUMENT,
                    message="Finviz ticker is required",
                    field="provider_symbol",
                ),
            ),
        )

    mapping = finviz_to_canonical(ticker)
    discovered_at = str(raw.get("discovered_at") or raw.get("received_at") or "")
    available_ns_raw = raw.get("available_time_ns")
    if available_ns_raw is not None:
        event_time_ns = int(available_ns_raw)
        historical_available = int(available_ns_raw)
    elif discovered_at:
        parsed, diag = iso_string_to_ns(discovered_at, field_name="discovered_at")
        if diag is not None:
            return NormalizationResult(event=None, diagnostics=(diag,))
        event_time_ns = parsed or context.received_time_ns
        historical_available = parsed or context.received_time_ns
    else:
        event_time_ns = context.received_time_ns
        historical_available = context.received_time_ns

    hist_context = NormalizationContext(
        received_time_ns=context.received_time_ns,
        ingestion_mode=context.ingestion_mode,
        adapter_version=context.adapter_version,
        raw_payload_ref=context.raw_payload_ref,
        historical_available_time_ns=historical_available,
        availability_basis=AvailabilityBasis.PROVIDER_REPORTED_AVAILABILITY,
        availability_confidence=AvailabilityConfidence.SOURCE_REPORTED,
        source_precision=SourcePrecision.SECOND,
    )
    try:
        available_time_ns, availability = derive_available_time_ns(
            context=hist_context,
            event_time_ns=event_time_ns,
            source_reported_available_time_ns=historical_available,
        )
    except ValueError:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNDETERMINABLE_AVAILABILITY,
                    message="Could not derive Finviz availability",
                ),
            ),
        )

    screen_id = str(raw.get("screen_id") or "SCREENER")
    rank = raw.get("rank")
    source_record_id = f"{screen_id}:{mapping.instrument_id}:{rank or 0}:{run_id or 'single'}"
    event_id = derive_event_id_composite(
        provider_id=PROVIDER_ID,
        identity_fields={
            "screen_id": screen_id,
            "instrument_id": mapping.instrument_id,
            "rank": rank,
            "run_id": run_id,
        },
        event_family="DISCOVERY_CANDIDATE",
    )

    payload = sanitize_payload(
        {
            "screen_id": screen_id,
            "screen_version": raw.get("screen_version"),
            "metrics": raw.get("metrics") or {},
            "matched_reasons": raw.get("matched_reasons") or [],
            "inspection_priority": raw.get("inspection_priority"),
            "candidate_role": "INVESTIGATE",
        }
    )

    quality_raw = str(raw.get("quality") or "PASS").upper()
    quality_state = QualityState.GOOD if quality_raw == "PASS" else QualityState.DEGRADED

    provenance = ProviderProvenance(
        provider_id=PROVIDER_ID,
        source_record_type="finviz_candidate",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_symbol=mapping.provider_symbol,
        provider_native_record_id=source_record_id,
        provider_event_type="DISCOVERY_CANDIDATE",
        raw_payload_ref=context.raw_payload_ref,
        raw_payload_hash=hash_raw_payload(raw),
        availability=availability,
        ingestion_mode=context.ingestion_mode,
    )

    source = SourceReference(
        provider_id=PROVIDER_ID,
        source_type="DISCOVERY",
        source_record_id=source_record_id,
        raw_reference=context.raw_payload_ref,
    )

    event = build_event_v1(
        event_id=event_id,
        event_type="DISCOVERY_CANDIDATE",
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload,
        source=source,
        provenance=provenance,
        instrument_id=mapping.instrument_id,
        provider_time_ns=event_time_ns,
        received_time_ns=context.received_time_ns,
        quality_state=quality_state,
    )
    return NormalizationResult(event=event, provenance=provenance)


__all__ = ["normalize_finviz_candidate"]
