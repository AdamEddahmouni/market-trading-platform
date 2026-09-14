"""Market Trackers SEC Forms 3/4/5 insider row normalization (BUILD 03)."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from ....market_trackers.sec_insider.event_map import map_event_v1_prep
from ....market_trackers.sec_insider.reconcile import EdgarPrimarySubmission, reconcile_sec_insider_clocks
from ....market_trackers.sec_insider.validate import validate_market_trackers_row
from ....research.security_identity import resolve_us_equity_ticker
from ....sec_edgar.identity import normalize_accession
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
    SourcePrecision,
)
from ..numeric import sanitize_payload
from ..timestamps import derive_available_time_ns

ADAPTER_ID = "market_trackers.sec_insider.row"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/market_trackers_sec_insider/1"
PROVIDER_ID = "market_trackers.sec_insider"
PRIMARY_PUBLISHER_ID = "sec.edgar"


def _resolve_instrument_id(row: Mapping[str, Any]) -> tuple[str | None, tuple[str, ...]]:
    ticker = row.get("ticker")
    if ticker is None or str(ticker).strip() == "":
        return None, ("INSTRUMENT_UNRESOLVED_TICKER_NULL",)
    try:
        sec = resolve_us_equity_ticker(
            str(ticker),
            venue_id="US_EQUITY",
            namespace="xa01.provisional",
        )
        return sec.instrument.qualified_id(), ()
    except ValueError:
        return None, ("TICKER_XA01_RESOLUTION_FAILED",)


def normalize_sec_insider_row(
    row: dict[str, Any],
    *,
    context: NormalizationContext,
    edgar_primary: Mapping[str, Any] | EdgarPrimarySubmission | None = None,
) -> NormalizationResult:
    """Normalize a Market Trackers insider JSON row to EventV1 (optional EDGAR-primary reconcile)."""
    raw = copy.deepcopy(row)
    validation = validate_market_trackers_row(raw)
    if not validation.ok:
        return NormalizationResult(
            event=None,
            diagnostics=tuple(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.MALFORMED_PAYLOAD,
                    message=err,
                )
                for err in validation.errors
            ),
        )

    instrument_id, identity_flags = _resolve_instrument_id(raw)
    if instrument_id is None:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.INVALID_INSTRUMENT,
                    message="instrument_id unresolved (XA-01 fail-closed)",
                    field="ticker",
                    details={"identity_flags": list(identity_flags)},
                ),
            ),
        )

    try:
        clocks = reconcile_sec_insider_clocks(
            raw,
            platform_received_time_ns=context.received_time_ns,
            edgar_primary=edgar_primary,
        )
    except ValueError as exc:
        code = NormalizationErrorCode.UNDETERMINABLE_AVAILABILITY
        message = str(exc)
        if "FILED_AT" in message or "FILING_DATE" in message:
            code = NormalizationErrorCode.MISSING_REQUIRED_FIELD
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=code,
                    message=message,
                ),
            ),
        )

    try:
        event_prep = map_event_v1_prep(raw)
    except ValueError as exc:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.MISSING_REQUIRED_FIELD,
                    message=str(exc),
                ),
            ),
        )

    accession = normalize_accession(str(raw.get("accessionNumber") or ""))
    row_id = str(raw.get("id") or accession)
    event_time_ns = clocks.economic_event_time_ns or clocks.filing_publication_time_ns
    provider_time_ns = clocks.sec_acceptance_time_ns or clocks.filing_publication_time_ns

    basis = AvailabilityBasis.PUBLICATION_TIME
    confidence = AvailabilityConfidence.SOURCE_REPORTED
    precision = SourcePrecision.SECOND if clocks.sec_acceptance_time_ns else SourcePrecision.DAY
    if clocks.available_time_basis.startswith("market_trackers"):
        basis = AvailabilityBasis.PROVIDER_REPORTED_AVAILABILITY
    if "imp.platform" in clocks.available_time_basis:
        basis = AvailabilityBasis.LOCAL_RECEIPT
        confidence = AvailabilityConfidence.DIRECTLY_OBSERVED

    hist_context = NormalizationContext(
        received_time_ns=context.received_time_ns,
        ingestion_mode=context.ingestion_mode,
        adapter_version=context.adapter_version,
        raw_payload_ref=context.raw_payload_ref,
        historical_available_time_ns=clocks.available_time_ns,
        availability_basis=basis,
        availability_confidence=confidence,
        source_precision=precision,
    )
    effective = hist_context
    if context.ingestion_mode == IngestionMode.LIVE_OBSERVED:
        effective = context

    try:
        available_time_ns, availability = derive_available_time_ns(
            context=effective,
            event_time_ns=event_time_ns,
            provider_time_ns=provider_time_ns,
            source_reported_available_time_ns=clocks.available_time_ns,
        )
    except ValueError:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNDETERMINABLE_AVAILABILITY,
                    message="Could not derive insider row availability",
                ),
            ),
        )

    if clocks.economic_event_time_ns is not None and available_time_ns <= clocks.economic_event_time_ns:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.INVALID_TIMESTAMP,
                    message="available_time_ns must be after economic transaction attribution",
                    field="available_time_ns",
                ),
            ),
        )

    edgar_primary_supplied = edgar_primary is not None
    publication_authority = PRIMARY_PUBLISHER_ID if edgar_primary_supplied else PROVIDER_ID

    payload = sanitize_payload(
        {
            **event_prep.payload_core,
            "clocks": clocks.to_payload_clocks(),
            "clock_doctrine": {
                "edgar_primary_supplied": edgar_primary_supplied,
                "publication_authority": publication_authority,
                "aggregator_provider": PROVIDER_ID,
                "event_time_role": "economic_attribution_when_transactedAt_present",
                "available_time_role": "lawful_publication_acceptance_retrieved_received",
            },
            "reconcile_flags": list(clocks.reconcile_flags),
            "identity_flags": list(event_prep.identity_flags),
            "interpretation": "regulatory_fact_not_trade_signal",
        }
    )

    event_id = derive_event_id_from_provider(
        provider_id=PROVIDER_ID,
        venue_id="US_EQUITY",
        source_record_id=row_id,
        event_family=event_prep.event_family,
        channel_id=event_prep.channel_id,
        publisher_id=PRIMARY_PUBLISHER_ID,
        subrecord_discriminator=accession,
    )

    provenance = ProviderProvenance(
        provider_id=PROVIDER_ID,
        source_record_type="market_trackers_insider_row",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_symbol=str(raw.get("ticker") or "") or None,
        provider_native_record_id=row_id,
        provider_event_type=event_prep.event_type,
        raw_payload_ref=context.raw_payload_ref,
        raw_payload_hash=hash_raw_payload(raw),
        availability=availability,
        source_publication_id=accession,
        ingestion_mode=context.ingestion_mode,
    )

    source = SourceReference(
        provider_id=PROVIDER_ID,
        source_type="REGULATORY_OWNERSHIP",
        source_record_id=row_id,
        raw_reference=context.raw_payload_ref,
        external_id=accession,
    )

    quality_flags = tuple(dict.fromkeys((*clocks.reconcile_flags, *identity_flags, *event_prep.identity_flags)))

    event = build_event_v1(
        event_id=event_id,
        event_type=event_prep.event_type,
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload,
        source=source,
        provenance=provenance,
        instrument_id=instrument_id,
        provider_time_ns=provider_time_ns,
        received_time_ns=context.received_time_ns,
        quality_state=QualityState.GOOD,
        quality_flags=quality_flags,
    )
    return NormalizationResult(event=event, provenance=provenance)


__all__ = ["normalize_sec_insider_row"]
