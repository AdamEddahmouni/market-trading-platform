"""Frozen, deterministic contracts for local historical bar intake.

Every identity-bearing model reuses the acquisition ``_FrozenAcquisitionModel``
base (UUIDv5 deterministic id over canonical JSON, ``extra='forbid'``, frozen)
so intake records share the project's determinism guarantees rather than a
parallel framework.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import PurePosixPath, PureWindowsPath

from pydantic import Field, field_validator, model_validator

from ..models import _FrozenAcquisitionModel, _aware_utc
from .semantics import (
    ArtifactFormat,
    BarInterval,
    BarSession,
    CorporateActionHandling,
    DataTimeBasis,
    DuplicatePolicy,
    IntakeReasonCode,
    IntakeValidationStatus,
    IntendedUse,
    PriceAdjustmentSemantics,
    RowNormalizationStatus,
    SessionCoveragePolicy,
    SortExpectation,
    ThousandsSeparatorPolicy,
    TimestampSemantics,
    ValueAuthenticity,
    VolumeAdjustmentSemantics,
)


SCHEMA_VERSION = "1.0.0"
INTAKE_CONTRACT_VERSION = "phase_3d_local_bar_intake_contract.v1"


def _relative_posix(value: str) -> str:
    normalized = value.replace("\\", "/")
    if PurePosixPath(normalized).is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError("path must be relative, never absolute")
    if ".." in PurePosixPath(normalized).parts:
        raise ValueError("path cannot escape the intake root")
    return normalized


def _valid_sha256(value: str) -> str:
    normalized = value.lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError("sha256 must be 64 hexadecimal characters")
    return normalized


class ColumnMappingProfile(_FrozenAcquisitionModel):
    """Explicit, provider-neutral parsing profile for a delimited artifact."""

    schema_version: str = SCHEMA_VERSION
    profile_id: str = Field(min_length=1)
    delimiter: str = Field(min_length=1, max_length=1)
    encoding: str = Field(min_length=1)
    has_header: bool
    # Either a single timestamp column, or separate date + time columns.
    timestamp_column: str | None = None
    date_column: str | None = None
    time_column: str | None = None
    timestamp_format: str | None = None
    symbol_column: str | None = None
    venue_column: str | None = None
    open_column: str = Field(min_length=1)
    high_column: str = Field(min_length=1)
    low_column: str = Field(min_length=1)
    close_column: str = Field(min_length=1)
    volume_column: str | None = None
    trade_count_column: str | None = None
    vwap_column: str | None = None
    currency_column: str | None = None
    decimal_separator: str = Field(default=".", min_length=1, max_length=1)
    thousands_separator_policy: ThousandsSeparatorPolicy = ThousandsSeparatorPolicy.DISALLOW
    null_tokens: tuple[str, ...] = ()
    sort_expectation: SortExpectation = SortExpectation.STABLE_SORT_BY_EVENT_START
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.COLLAPSE_IDENTICAL_REJECT_CONFLICTING
    deterministic_id: str | None = None

    @field_validator("null_tokens")
    @classmethod
    def _sort_nulls(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def _validate_timestamp_columns(self):
        single = self.timestamp_column is not None
        split = self.date_column is not None and self.time_column is not None
        if single == split:
            raise ValueError(
                "declare exactly one of timestamp_column or (date_column + time_column)"
            )
        if self.decimal_separator == self.delimiter:
            raise ValueError("decimal_separator cannot equal the field delimiter")
        return self


class IntakeManifest(_FrozenAcquisitionModel):
    """User-supplied intake declaration. Explicit nulls required for unknowns."""

    schema_version: str = SCHEMA_VERSION
    intake_contract_version: str = INTAKE_CONTRACT_VERSION
    bundle_id: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    provider_product_or_export_name: str = Field(min_length=1)
    user_entitlement_assertion: str = Field(min_length=1)
    license_or_terms_reference: str | None = None
    retrieval_time: datetime
    export_time: datetime
    artifact_relative_path: str
    artifact_sha256: str
    artifact_byte_length: int = Field(ge=0)
    artifact_media_type: str = Field(min_length=1)
    artifact_format: ArtifactFormat
    provider_symbol: str = Field(min_length=1)
    canonical_symbol: str = Field(min_length=1)
    market_or_venue: str = Field(min_length=1)
    bar_interval: BarInterval
    event_timezone: str = Field(min_length=1)
    timestamp_semantics: TimestampSemantics
    session_coverage: BarSession
    session_coverage_policy: SessionCoveragePolicy = SessionCoveragePolicy.ALLOW_GAPS
    price_adjustment_semantics: PriceAdjustmentSemantics
    volume_adjustment_semantics: VolumeAdjustmentSemantics
    corporate_action_handling: CorporateActionHandling
    data_time_basis: DataTimeBasis
    value_authenticity: ValueAuthenticity
    intended_use: IntendedUse
    expected_start_time: datetime
    expected_end_time: datetime
    column_mapping_profile_id: str = Field(min_length=1)
    notes: str | None = None
    deterministic_id: str | None = None

    @field_validator("artifact_relative_path")
    @classmethod
    def _relative(cls, value: str) -> str:
        return _relative_posix(value)

    @field_validator("artifact_sha256")
    @classmethod
    def _sha(cls, value: str) -> str:
        return _valid_sha256(value)

    @field_validator("canonical_symbol", "provider_symbol")
    @classmethod
    def _symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @field_validator(
        "retrieval_time", "export_time", "expected_start_time", "expected_end_time"
    )
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _validate_window(self):
        if self.expected_end_time <= self.expected_start_time:
            raise ValueError("expected_end_time must be after expected_start_time")
        return self


class RawArtifactDescriptor(_FrozenAcquisitionModel):
    """Lean identity for the preserved raw artifact (bytes never modified)."""

    schema_version: str = SCHEMA_VERSION
    bundle_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    relative_path: str
    media_type: str = Field(min_length=1)
    artifact_format: ArtifactFormat
    byte_length: int = Field(ge=0)
    sha256: str
    deterministic_id: str | None = None

    @field_validator("relative_path")
    @classmethod
    def _relative(cls, value: str) -> str:
        return _relative_posix(value)

    @field_validator("sha256")
    @classmethod
    def _sha(cls, value: str) -> str:
        return _valid_sha256(value)


class ArtifactValidationReport(_FrozenAcquisitionModel):
    bundle_id: str
    artifact_id: str
    status: IntakeValidationStatus
    expected_byte_length: int = Field(ge=0)
    actual_byte_length: int | None = None
    expected_sha256: str
    actual_sha256: str | None = None
    reason_codes: tuple[IntakeReasonCode, ...] = ()
    deterministic_id: str | None = None

    @field_validator("reason_codes")
    @classmethod
    def _sort_codes(cls, value: tuple[IntakeReasonCode, ...]) -> tuple[IntakeReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class CanonicalMarketBar(_FrozenAcquisitionModel):
    """Deterministic, provider-neutral normalized bar. OHLCV never inferred."""

    schema_version: str = SCHEMA_VERSION
    canonical_symbol: str
    provider_symbol: str
    market_or_venue: str
    interval: BarInterval
    event_start_time: datetime
    event_end_time: datetime
    event_timezone: str
    session: BarSession
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None = None
    trade_count: int | None = None
    vwap: Decimal | None = None
    currency: str | None = None
    price_adjustment_semantics: PriceAdjustmentSemantics
    volume_adjustment_semantics: VolumeAdjustmentSemantics
    value_authenticity: ValueAuthenticity
    source_artifact_id: str
    source_row_number: int = Field(ge=1)
    source_record_id: str
    deterministic_id: str | None = None

    @field_validator("event_start_time", "event_end_time")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]

    @field_validator("open", "high", "low", "close", "vwap")
    @classmethod
    def _finite_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if not value.is_finite():
            raise ValueError("price must be a finite decimal")
        return value

    @model_validator(mode="after")
    def _validate_integrity(self):
        if self.event_end_time <= self.event_start_time:
            raise ValueError("event_end_time must be after event_start_time")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= max(open, close, low)")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= min(open, close, high)")
        if self.volume is not None and self.volume < 0:
            raise ValueError("volume must be non-negative")
        if self.trade_count is not None and self.trade_count < 0:
            raise ValueError("trade_count must be non-negative")
        return self


class NormalizedBarSet(_FrozenAcquisitionModel):
    schema_version: str = SCHEMA_VERSION
    bundle_id: str
    canonical_symbol: str
    interval: BarInterval
    source_artifact_id: str
    bars: tuple[CanonicalMarketBar, ...]
    deterministic_id: str | None = None

    @field_validator("bars")
    @classmethod
    def _sort_bars(cls, value: tuple[CanonicalMarketBar, ...]) -> tuple[CanonicalMarketBar, ...]:
        return tuple(
            sorted(value, key=lambda bar: (bar.event_start_time, bar.source_row_number))
        )


class RowDiagnostic(_FrozenAcquisitionModel):
    source_row_number: int = Field(ge=1)
    source_record_id: str | None = None
    status: RowNormalizationStatus
    reason_codes: tuple[IntakeReasonCode, ...] = ()
    message: str = ""

    @field_validator("reason_codes")
    @classmethod
    def _sort_codes(cls, value: tuple[IntakeReasonCode, ...]) -> tuple[IntakeReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class NormalizationDiagnostics(_FrozenAcquisitionModel):
    schema_version: str = SCHEMA_VERSION
    bundle_id: str
    status: IntakeValidationStatus
    total_rows: int = Field(ge=0)
    normalized_count: int = Field(ge=0)
    quarantined_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    bundle_reason_codes: tuple[IntakeReasonCode, ...] = ()
    row_diagnostics: tuple[RowDiagnostic, ...] = ()
    deterministic_id: str | None = None

    @field_validator("bundle_reason_codes")
    @classmethod
    def _sort_codes(cls, value: tuple[IntakeReasonCode, ...]) -> tuple[IntakeReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))

    @field_validator("row_diagnostics")
    @classmethod
    def _sort_rows(cls, value: tuple[RowDiagnostic, ...]) -> tuple[RowDiagnostic, ...]:
        return tuple(sorted(value, key=lambda item: item.source_row_number))


class IntakeSummary(_FrozenAcquisitionModel):
    schema_version: str = SCHEMA_VERSION
    intake_contract_version: str = INTAKE_CONTRACT_VERSION
    bundle_id: str
    provider_name: str
    canonical_symbol: str
    market_or_venue: str
    interval: BarInterval
    artifact_validation_status: IntakeValidationStatus
    normalization_status: IntakeValidationStatus
    normalized_bar_count: int = Field(ge=0)
    quarantined_row_count: int = Field(ge=0)
    rejected_row_count: int = Field(ge=0)
    # Event time is kept strictly separate from retrieval/export time.
    event_start_min: datetime | None = None
    event_end_max: datetime | None = None
    retrieval_time: datetime
    export_time: datetime
    price_adjustment_semantics: PriceAdjustmentSemantics
    volume_adjustment_semantics: VolumeAdjustmentSemantics
    session_coverage: BarSession
    value_authenticity: ValueAuthenticity
    reason_codes: tuple[IntakeReasonCode, ...] = ()
    deterministic_id: str | None = None

    @field_validator("retrieval_time", "export_time", "event_start_min", "event_end_max")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)

    @field_validator("reason_codes")
    @classmethod
    def _sort_codes(cls, value: tuple[IntakeReasonCode, ...]) -> tuple[IntakeReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


class CaseAssociationMapping(_FrozenAcquisitionModel):
    """Declarative, non-executing link from a validated bundle to a case."""

    schema_version: str = SCHEMA_VERSION
    case_id: str = Field(min_length=1)
    canonical_symbol: str = Field(min_length=1)
    frozen_detection_boundary_id: str = Field(min_length=1)
    requested_window_start: datetime
    requested_window_end: datetime
    required_interval: BarInterval
    required_session_coverage: BarSession
    bundle_id: str = Field(min_length=1)
    deterministic_id: str | None = None

    @field_validator("canonical_symbol")
    @classmethod
    def _symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("requested_window_start", "requested_window_end")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return _aware_utc(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _validate_window(self):
        if self.requested_window_end <= self.requested_window_start:
            raise ValueError("requested_window_end must be after requested_window_start")
        return self


class CaseAssociationValidationResult(_FrozenAcquisitionModel):
    schema_version: str = SCHEMA_VERSION
    mapping_id: str
    case_id: str
    bundle_id: str
    valid: bool
    case_id_exists: bool
    boundary_id_exists: bool
    symbol_compatible: bool
    coverage_compatible: bool
    interval_compatible: bool
    # These are structurally impossible in this batch and asserted false always.
    outcome_computed: bool = False
    phase_3a_or_3b_record_created: bool = False
    reason_codes: tuple[IntakeReasonCode, ...] = ()
    deterministic_id: str | None = None

    @field_validator("reason_codes")
    @classmethod
    def _sort_codes(cls, value: tuple[IntakeReasonCode, ...]) -> tuple[IntakeReasonCode, ...]:
        return tuple(sorted(set(value), key=lambda item: item.value))


__all__ = [
    "SCHEMA_VERSION",
    "INTAKE_CONTRACT_VERSION",
    "ColumnMappingProfile",
    "IntakeManifest",
    "RawArtifactDescriptor",
    "ArtifactValidationReport",
    "CanonicalMarketBar",
    "NormalizedBarSet",
    "RowDiagnostic",
    "NormalizationDiagnostics",
    "IntakeSummary",
    "CaseAssociationMapping",
    "CaseAssociationValidationResult",
]
