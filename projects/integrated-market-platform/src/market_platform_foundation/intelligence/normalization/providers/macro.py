"""Macro/FRED observation normalization (BUILD 03)."""

from __future__ import annotations

from ....fred.contracts import MacroObservation
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
from ..timestamps import derive_available_time_ns, iso_string_to_ns

ADAPTER_ID = "fred.macro"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/macro/1"
PROVIDER_ID = "fred"


def normalize_macro_observation(
    observation: MacroObservation,
    *,
    context: NormalizationContext,
) -> NormalizationResult:
    available_iso = observation.available_time or observation.source_publication_time or observation.realtime_end
    if not available_iso:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNDETERMINABLE_AVAILABILITY,
                    message="Macro observation lacks availability timestamp",
                ),
            ),
        )

    historical_available, diag = iso_string_to_ns(available_iso, field_name="available_time")
    if diag is not None or historical_available is None:
        return NormalizationResult(event=None, diagnostics=(diag,) if diag else ())

    obs_date = observation.observation_date[:10]
    event_time_ns, _ = iso_string_to_ns(obs_date + "T00:00:00Z", field_name="observation_date")
    if event_time_ns is None:
        event_time_ns = historical_available

    precision = SourcePrecision.DAY
    if observation.availability_precision:
        try:
            precision = SourcePrecision(observation.availability_precision.upper())
        except ValueError:
            precision = SourcePrecision.DAY

    hist_context = NormalizationContext(
        received_time_ns=context.received_time_ns,
        ingestion_mode=context.ingestion_mode,
        adapter_version=context.adapter_version,
        raw_payload_ref=context.raw_payload_ref,
        historical_available_time_ns=historical_available,
        availability_basis=AvailabilityBasis.RELEASE_TIME,
        availability_confidence=AvailabilityConfidence.SOURCE_REPORTED,
        source_precision=precision,
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
                    message="Could not derive macro availability",
                ),
            ),
        )

    source_record_id = f"{observation.series_id}:{observation.observation_date}:r{observation.revision_number}"
    event_id = derive_event_id_from_provider(
        provider_id=PROVIDER_ID,
        venue_id="GLOBAL",
        source_record_id=source_record_id,
        event_family="MACRO_RELEASE",
        channel_id=observation.canonical_indicator_id,
        source_revision_id=str(observation.revision_number),
    )

    payload = sanitize_payload(
        {
            "canonical_indicator_id": observation.canonical_indicator_id,
            "series_id": observation.series_id,
            "observation_date": observation.observation_date,
            "normalized_value": observation.normalized_value,
            "raw_value": observation.raw_value,
            "units": observation.units,
            "frequency": observation.frequency,
            "revision_number": observation.revision_number,
        }
    )

    provenance = ProviderProvenance(
        provider_id=PROVIDER_ID,
        source_record_type="macro_observation",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_record_id=source_record_id,
        provider_event_type="MACRO_RELEASE",
        raw_payload_ref=context.raw_payload_ref or observation.provenance_ref,
        raw_payload_hash=hash_raw_payload(payload),
        availability=availability,
        source_publication_id=str(observation.fred_release_id) if observation.fred_release_id else None,
        source_revision_id=str(observation.revision_number),
        ingestion_mode=context.ingestion_mode,
    )

    source = SourceReference(
        provider_id=PROVIDER_ID,
        source_type="MACRO",
        source_record_id=source_record_id,
        raw_reference=context.raw_payload_ref,
        external_id=observation.series_id,
    )

    event = build_event_v1(
        event_id=event_id,
        event_type="MACRO_RELEASE",
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload,
        source=source,
        provenance=provenance,
        instrument_id=None,
        received_time_ns=context.received_time_ns,
        quality_state=QualityState.DEGRADED if observation.quality_flags else QualityState.GOOD,
        quality_flags=observation.quality_flags,
    )
    return NormalizationResult(event=event, provenance=provenance)


__all__ = ["normalize_macro_observation"]
