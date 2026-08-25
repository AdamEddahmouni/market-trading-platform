"""SEC FTD observation normalization (BUILD 03)."""

from __future__ import annotations

from ....short_intelligence.contracts import FailsToDeliverObservation
from ...contracts.common import QualityState, SourceReference
from ..errors import NormalizationDiagnostic, NormalizationErrorCode
from ..event_builder import build_event_v1
from ..identity import derive_event_id_from_provider, hash_raw_payload
from ..models import (
    AvailabilityBasis,
    AvailabilityConfidence,
    NormalizationContext,
    NormalizationResult,
    ProviderProvenance,
    SourcePrecision,
)
from ..numeric import sanitize_payload
from ..timestamps import date_only_end_of_day_utc_ns, derive_available_time_ns, iso_string_to_ns

ADAPTER_ID = "sec.ftd"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/sec_ftd/1"
PROVIDER_ID = "sec.ftd"


def normalize_ftd_observation(
    observation: FailsToDeliverObservation,
    *,
    context: NormalizationContext,
) -> NormalizationResult:
    settlement = observation.settlement_date[:10]
    source_record_id = f"{settlement}:{observation.raw_symbol}:{observation.source_file_id or 'ftd'}"

    pub_time = observation.clocks.get("official_file_publication_time") or observation.clocks.get("available_time") or ""
    if pub_time:
        historical_available, diag = iso_string_to_ns(pub_time, field_name="official_file_publication_time")
        if diag is not None:
            historical_available, diag = date_only_end_of_day_utc_ns(settlement, field_name="settlement_date")
    else:
        historical_available, diag = date_only_end_of_day_utc_ns(settlement, field_name="settlement_date")
    if diag is not None or historical_available is None:
        return NormalizationResult(event=None, diagnostics=(diag,) if diag else ())

    settlement_ns, _ = date_only_end_of_day_utc_ns(settlement, field_name="settlement_date")
    event_time_ns = settlement_ns or historical_available

    hist_context = NormalizationContext(
        received_time_ns=context.received_time_ns,
        ingestion_mode=context.ingestion_mode,
        adapter_version=context.adapter_version,
        raw_payload_ref=context.raw_payload_ref,
        historical_available_time_ns=historical_available,
        availability_basis=AvailabilityBasis.PUBLICATION_TIME,
        availability_confidence=AvailabilityConfidence.APPROXIMATE,
        source_precision=SourcePrecision.DAY,
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
                    message="Could not derive FTD availability",
                ),
            ),
        )

    event_id = derive_event_id_from_provider(
        provider_id=PROVIDER_ID,
        venue_id="US_EQUITY",
        source_record_id=source_record_id,
        event_family="FAIL_TO_DELIVER",
        channel_id=observation.raw_symbol,
    )

    payload = sanitize_payload(
        {
            "settlement_date": settlement,
            "ftd_balance_quantity": observation.ftd_balance_quantity,
            "cusip": observation.cusip,
            "approx_notional": observation.approx_ftd_notional_sec_price,
            "source_file_id": observation.source_file_id,
        }
    )

    provenance = ProviderProvenance(
        provider_id=PROVIDER_ID,
        source_record_type="ftd_observation",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_symbol=observation.raw_symbol,
        provider_native_record_id=source_record_id,
        provider_event_type="FAIL_TO_DELIVER",
        raw_payload_ref=context.raw_payload_ref,
        raw_payload_hash=observation.raw_payload_hash or hash_raw_payload(payload),
        availability=availability,
        source_publication_id=observation.source_file_id,
        ingestion_mode=context.ingestion_mode,
    )

    source = SourceReference(
        provider_id=PROVIDER_ID,
        source_type="FAIL_TO_DELIVER",
        source_record_id=source_record_id,
        raw_reference=context.raw_payload_ref,
    )

    event = build_event_v1(
        event_id=event_id,
        event_type="FAIL_TO_DELIVER",
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload,
        source=source,
        provenance=provenance,
        instrument_id=observation.instrument_id,
        received_time_ns=context.received_time_ns,
        quality_state=QualityState.DEGRADED if observation.quality_flags else QualityState.GOOD,
        quality_flags=observation.quality_flags,
    )
    return NormalizationResult(event=event, provenance=provenance)


__all__ = ["normalize_ftd_observation"]
