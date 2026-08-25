"""Timestamp normalization helpers (BUILD 03)."""

from __future__ import annotations

from ..contracts.common import validate_timestamp_ns
from .errors import NormalizationDiagnostic, NormalizationErrorCode
from .models import (
    AvailabilityBasis,
    AvailabilityConfidence,
    AvailabilityDerivation,
    IngestionMode,
    NormalizationContext,
    SourcePrecision,
)


def parse_timestamp_ns(
    value: object,
    *,
    field_name: str,
    unit: str,
) -> tuple[int | None, NormalizationDiagnostic | None]:
    """Parse a provider timestamp with explicit unit declaration."""
    if value is None or value == "":
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.MISSING_REQUIRED_FIELD,
            message=f"{field_name} is required",
            field=field_name,
        )
    try:
        if unit == "ns":
            result = int(value)
        elif unit == "us":
            result = int(value) * 1_000
        elif unit == "ms":
            result = int(value) * 1_000_000
        elif unit == "s":
            result = int(value) * 1_000_000_000
        else:
            return None, NormalizationDiagnostic(
                code=NormalizationErrorCode.UNKNOWN_TIMESTAMP_UNIT,
                message=f"Unsupported timestamp unit {unit!r} for {field_name}",
                field=field_name,
                details={"unit": unit},
            )
        validate_timestamp_ns(result, field_name=field_name)
        return result, None
    except (TypeError, ValueError) as exc:
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.INVALID_TIMESTAMP,
            message=f"Invalid {field_name}: {exc}",
            field=field_name,
        )


def derive_available_time_ns(
    *,
    context: NormalizationContext,
    event_time_ns: int,
    provider_time_ns: int | None = None,
    source_reported_available_time_ns: int | None = None,
) -> tuple[int, AvailabilityDerivation]:
    """Derive available_time_ns and record how it was determined."""
    if context.ingestion_mode == IngestionMode.LIVE_OBSERVED:
        provider_avail = (
            context.provider_reported_available_time_ns
            or source_reported_available_time_ns
            or provider_time_ns
        )
        available = context.received_time_ns
        if provider_avail is not None and provider_avail > available:
            available = provider_avail
        basis = context.availability_basis or AvailabilityBasis.LOCAL_RECEIPT
        confidence = context.availability_confidence or AvailabilityConfidence.DIRECTLY_OBSERVED
        if provider_avail is not None and provider_avail > context.received_time_ns:
            basis = AvailabilityBasis.PROVIDER_REPORTED_AVAILABILITY
            confidence = AvailabilityConfidence.SOURCE_REPORTED
        return available, AvailabilityDerivation(
            basis=basis,
            confidence=confidence,
            source_precision=context.source_precision,
            provider_reported_available_time_ns=provider_avail,
        )

    if context.ingestion_mode in {IngestionMode.HISTORICAL_RECONSTRUCTED, IngestionMode.REPLAY, IngestionMode.FIXTURE}:
        historical = context.historical_available_time_ns or source_reported_available_time_ns
        if historical is None:
            raise ValueError("UNDETERMINABLE_AVAILABILITY")
        basis = context.availability_basis or AvailabilityBasis.RECONSTRUCTED_FROM_SOURCE
        confidence = context.availability_confidence or AvailabilityConfidence.SOURCE_REPORTED
        return historical, AvailabilityDerivation(
            basis=basis,
            confidence=confidence,
            source_precision=context.source_precision,
            provider_reported_available_time_ns=source_reported_available_time_ns,
        )

    raise ValueError(f"UNSUPPORTED_INGESTION_MODE:{context.ingestion_mode}")


def iso_string_to_ns(value: str, *, field_name: str) -> tuple[int | None, NormalizationDiagnostic | None]:
    if not value or not str(value).strip():
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.MISSING_REQUIRED_FIELD,
            message=f"{field_name} is required",
            field=field_name,
        )
    try:
        from ...normalization.equity_bars import iso_to_epoch_ns

        result = iso_to_epoch_ns(str(value))
        validate_timestamp_ns(result, field_name=field_name)
        return result, None
    except (TypeError, ValueError) as exc:
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.INVALID_TIMESTAMP,
            message=f"Invalid ISO timestamp for {field_name}: {exc}",
            field=field_name,
        )


def date_only_end_of_day_utc_ns(date_text: str, *, field_name: str) -> tuple[int | None, NormalizationDiagnostic | None]:
    """Conservative date-only availability: end of UTC day."""
    text = str(date_text).strip()
    if len(text) < 10:
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.INVALID_TIMESTAMP,
            message=f"Invalid date for {field_name}",
            field=field_name,
        )
    iso = text[:10] + "T23:59:59Z"
    ns, diag = iso_string_to_ns(iso, field_name=field_name)
    if diag is not None:
        return None, diag
    return ns, None


__all__ = [
    "date_only_end_of_day_utc_ns",
    "derive_available_time_ns",
    "iso_string_to_ns",
    "parse_timestamp_ns",
]
