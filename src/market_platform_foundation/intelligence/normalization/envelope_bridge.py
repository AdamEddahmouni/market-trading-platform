"""Bridge Revision-1 provider envelopes to EventV1 (BUILD 03)."""

from __future__ import annotations

import copy
from typing import Any

from ...providers.contracts import SymbolMapping
from ..contracts.common import QualityState, SourceReference
from .errors import NormalizationDiagnostic, NormalizationErrorCode
from .event_builder import build_event_v1
from .identity import derive_event_id_from_provider, hash_raw_payload
from .models import (
    AvailabilityBasis,
    AvailabilityConfidence,
    IngestionMode,
    NormalizationContext,
    NormalizationResult,
    ProviderProvenance,
    SourcePrecision,
)
from .numeric import sanitize_payload
from .timestamps import derive_available_time_ns


ADAPTER_ID = "envelope.bridge"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/envelope/1"


def normalize_envelope(
    envelope: dict[str, Any],
    *,
    context: NormalizationContext,
) -> NormalizationResult:
    raw = copy.deepcopy(envelope)
    diagnostics: list[NormalizationDiagnostic] = []

    provider_id = str(raw.get("publisher_id") or raw.get("source_instance_id") or "unknown.provider")
    event_type = str(raw.get("event_type") or "")
    if not event_type:
        diagnostics.append(
            NormalizationDiagnostic(
                code=NormalizationErrorCode.MISSING_REQUIRED_FIELD,
                message="event_type is required",
                field="event_type",
            )
        )
        return NormalizationResult(event=None, diagnostics=tuple(diagnostics))

    event_time = raw.get("event_time")
    if event_time is None:
        diagnostics.append(
            NormalizationDiagnostic(
                code=NormalizationErrorCode.MISSING_REQUIRED_FIELD,
                message="event_time is required",
                field="event_time",
            )
        )
        return NormalizationResult(event=None, diagnostics=tuple(diagnostics))

    event_time_ns = int(event_time)
    provider_time_ns = int(raw["source_publish_time"]) if raw.get("source_publish_time") is not None else None
    source_reported = int(raw["available_time"]) if raw.get("available_time") is not None else None

    try:
        available_time_ns, availability = derive_available_time_ns(
            context=context,
            event_time_ns=event_time_ns,
            provider_time_ns=provider_time_ns,
            source_reported_available_time_ns=source_reported,
        )
    except ValueError:
        diagnostics.append(
            NormalizationDiagnostic(
                code=NormalizationErrorCode.UNDETERMINABLE_AVAILABILITY,
                message="Could not derive available_time_ns",
                field="available_time_ns",
            )
        )
        return NormalizationResult(event=None, diagnostics=tuple(diagnostics))

    instrument_id = raw.get("instrument_id")
    venue_id = str(raw.get("venue_id") or "US_EQUITY")
    channel_id = str(raw.get("channel_id") or instrument_id or "")
    source_record_id = str(raw.get("source_record_id") or raw.get("normalized_event_id") or event_type)
    source_revision_id = str(raw.get("source_revision_id") or "1")
    event_family = event_type

    event_id = str(raw.get("normalized_event_id") or derive_event_id_from_provider(
        provider_id=provider_id,
        venue_id=venue_id,
        source_record_id=source_record_id,
        event_family=event_family,
        source_revision_id=source_revision_id,
        channel_id=channel_id,
        publisher_id=str(raw.get("publisher_id") or provider_id),
        source_instance_id=str(raw.get("source_instance_id") or provider_id),
    ))

    payload = sanitize_payload(dict(raw.get("payload") or {}))
    quality_state = QualityState.GOOD
    flags = tuple(str(f) for f in (raw.get("quality_observation_refs") or ()))
    if flags:
        quality_state = QualityState.DEGRADED

    provenance = ProviderProvenance(
        provider_id=provider_id,
        source_record_type="envelope",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_symbol=channel_id or None,
        provider_native_record_id=source_record_id,
        provider_event_type=event_type,
        raw_payload_ref=context.raw_payload_ref or str(raw.get("raw_reference") or ""),
        raw_payload_hash=hash_raw_payload(raw),
        availability=availability,
        source_revision_id=source_revision_id,
        ingestion_mode=context.ingestion_mode,
    )

    source = SourceReference(
        provider_id=provider_id,
        source_type=event_type,
        source_record_id=source_record_id,
        raw_reference=provenance.raw_payload_ref,
        external_id=str(raw.get("normalized_event_id") or event_id),
    )

    event = build_event_v1(
        event_id=event_id,
        event_type=event_type,
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload,
        source=source,
        provenance=provenance,
        instrument_id=str(instrument_id) if instrument_id else None,
        provider_time_ns=provider_time_ns,
        received_time_ns=context.received_time_ns,
        quality_state=quality_state,
        quality_flags=flags,
    )
    return NormalizationResult(event=event, provenance=provenance)


__all__ = ["normalize_envelope"]
