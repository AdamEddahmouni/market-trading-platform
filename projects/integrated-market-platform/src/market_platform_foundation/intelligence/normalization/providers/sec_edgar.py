"""SEC EDGAR filing normalization (BUILD 03)."""

from __future__ import annotations

import copy
from typing import Any

from ....sec_edgar.identity import normalize_accession
from ....sec_edgar.timestamps import clocks_from_submission_row
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

ADAPTER_ID = "sec.edgar.filing"
ADAPTER_VERSION = "1"
NORMALIZATION_VERSION = "intelligence/normalization/sec_edgar/1"
PROVIDER_ID = "sec.edgar"


def normalize_sec_filing(
    filing: dict[str, Any],
    *,
    context: NormalizationContext,
    instrument_id: str | None = None,
    observed_time: str = "",
) -> NormalizationResult:
    raw = copy.deepcopy(filing)
    accession = normalize_accession(str(raw.get("accession_number") or raw.get("accessionNumber") or ""))
    if not accession:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.MISSING_REQUIRED_FIELD,
                    message="accession_number is required",
                    field="accession_number",
                ),
            ),
        )

    form_type = str(raw.get("form_type") or raw.get("form") or "FILING")
    filing_date = str(raw.get("filing_date") or raw.get("filingDate") or "")
    acceptance = str(raw.get("acceptance_datetime") or raw.get("acceptanceDateTime") or "")
    clocks = clocks_from_submission_row(
        filing_date=filing_date,
        acceptance_datetime=acceptance,
        observed_time=observed_time or acceptance or filing_date,
    )
    event_time_ns = clocks.filing_date_ns or clocks.acceptance_time_ns
    provider_time_ns = clocks.acceptance_time_ns

    hist_context = NormalizationContext(
        received_time_ns=context.received_time_ns,
        ingestion_mode=context.ingestion_mode,
        adapter_version=context.adapter_version,
        raw_payload_ref=context.raw_payload_ref,
        historical_available_time_ns=clocks.available_time_ns,
        availability_basis=AvailabilityBasis.PUBLICATION_TIME,
        availability_confidence=AvailabilityConfidence.SOURCE_REPORTED,
        source_precision=SourcePrecision.SECOND if "T" in acceptance else SourcePrecision.DAY,
    )
    try:
        available_time_ns, availability = derive_available_time_ns(
            context=hist_context,
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
                    message="Could not derive filing availability",
                ),
            ),
        )

    cik = str(raw.get("cik") or raw.get("CIK") or "")
    event_id = derive_event_id_from_provider(
        provider_id=PROVIDER_ID,
        venue_id="US_EQUITY" if instrument_id else "GLOBAL",
        source_record_id=accession,
        event_family="FILING",
        channel_id=form_type,
        publisher_id=PROVIDER_ID,
    )

    payload = sanitize_payload(
        {
            "form_type": form_type,
            "filing_date": filing_date,
            "acceptance_datetime": acceptance,
            "cik": cik,
            "accession_number": accession,
            "primary_document": raw.get("primary_document") or raw.get("primaryDocument"),
        }
    )

    provenance = ProviderProvenance(
        provider_id=PROVIDER_ID,
        source_record_type="sec_filing",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        provider_native_record_id=accession,
        provider_event_type=form_type,
        raw_payload_ref=context.raw_payload_ref,
        raw_payload_hash=hash_raw_payload(raw),
        availability=availability,
        source_publication_id=accession,
        ingestion_mode=context.ingestion_mode,
    )

    source = SourceReference(
        provider_id=PROVIDER_ID,
        source_type="FILING",
        source_record_id=accession,
        raw_reference=context.raw_payload_ref,
        external_id=accession,
    )

    event = build_event_v1(
        event_id=event_id,
        event_type="FILING",
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload,
        source=source,
        provenance=provenance,
        instrument_id=instrument_id,
        provider_time_ns=provider_time_ns,
        received_time_ns=context.received_time_ns,
        quality_state=QualityState.GOOD,
    )
    return NormalizationResult(event=event, provenance=provenance)


__all__ = ["normalize_sec_filing"]
