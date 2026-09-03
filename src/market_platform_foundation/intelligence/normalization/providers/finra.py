"""FINRA short-interest normalization (BUILD 03)."""

from __future__ import annotations

from ....short_intelligence.contracts import ShortInterestObservation
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

ADAPTER_ID = "finra.short_interest"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/finra/1"
PROVIDER_ID = "finra.short_interest"


def normalize_short_interest_observation(
    observation: ShortInterestObservation,
    *,
    context: NormalizationContext,
) -> NormalizationResult:
    pub_date = observation.publication_date[:10]
    settlement = observation.settlement_date[:10]
    pub_time = observation.clocks.get("publication_time") or observation.clocks.get("available_time") or pub_date
    if "T" in pub_time:
        historical_available, diag = iso_string_to_ns(pub_time, field_name="publication_time")
    else:
        historical_available, diag = date_only_end_of_day_utc_ns(pub_date, field_name="publication_date")
    if diag is not None or historical_available is None:
        return NormalizationResult(event=None, diagnostics=(diag,) if diag else ())

    settlement_ns, _ = date_only_end_of_day_utc_ns(settlement, field_name="settlement_date")
    event_time_ns = settlement_ns or historical_available
    source_record_id = observation.finra_request_id or f"{settlement}:{observation.provider_symbol}"

    hist_context = NormalizationContext(
        received_time_ns=context.received_time_ns,
        ingestion_mode=context.ingestion_mode,
        adapter_version=context.adapter_version,
        raw_payload_ref=context.raw_payload_ref,
        historical_available_time_ns=historical_available,
        availability_basis=AvailabilityBasis.PUBLICATION_TIME,
        availability_confidence=AvailabilityConfidence.SOURCE_REPORTED,
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
                    message="Could not derive short-interest availability",
                ),
            ),
        )

    event_id = derive_event_id_from_provider(
        provider_id=PROVIDER_ID,
        venue_id="US_EQUITY",
        source_record_id=source_record_id,
        event_family="SHORT_INTEREST",
        channel_id=observation.provider_symbol,
        source_revision_id=str(observation.record_version),
    )

    payload = sanitize_payload(
        {
            "settlement_date": settlement,
            "publication_date": pub_date,
            "current_short_position_quantity": observation.current_short_position_quantity,
            "previous_short_position_quantity": observation.previous_short_position_quantity,
            "days_to_cover_provider": observation.days_to_cover_provider,
            "market_class_code": observation.market_class_code,
        }
    )

    provenance = ProviderProvenance(
        provider_id=PROVIDER_ID,
        source_record_type="short_interest",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_symbol=observation.provider_symbol,
        provider_native_record_id=source_record_id,
        provider_event_type="SHORT_INTEREST",
        raw_payload_ref=context.raw_payload_ref,
        raw_payload_hash=observation.raw_payload_hash or hash_raw_payload(payload),
        availability=availability,
        source_revision_id=str(observation.record_version),
        ingestion_mode=context.ingestion_mode,
    )

    source = SourceReference(
        provider_id=PROVIDER_ID,
        source_type="SHORT_INTEREST",
        source_record_id=source_record_id,
        raw_reference=context.raw_payload_ref,
        external_id=observation.finra_request_id or None,
    )

    event = build_event_v1(
        event_id=event_id,
        event_type="SHORT_INTEREST",
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


__all__ = ["normalize_short_interest_observation"]
