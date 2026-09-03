"""The frozen, self-describing local-bar-intake contract document.

``build_intake_contract`` renders a deterministic description of the manifest
fields, supported formats, enums, reason codes, and preregistered policies so the
contract can be committed as a canonical fixture and referenced by later batches.
"""

from __future__ import annotations

from .models import INTAKE_CONTRACT_VERSION, SCHEMA_VERSION
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
    SUPPORTED_ENCODINGS,
    SessionCoveragePolicy,
    SortExpectation,
    ThousandsSeparatorPolicy,
    TimestampSemantics,
    ValueAuthenticity,
    VolumeAdjustmentSemantics,
)


MANIFEST_FIELDS = (
    "schema_version", "intake_contract_version", "bundle_id", "provider_name",
    "provider_product_or_export_name", "user_entitlement_assertion",
    "license_or_terms_reference", "retrieval_time", "export_time",
    "artifact_relative_path", "artifact_sha256", "artifact_byte_length",
    "artifact_media_type", "artifact_format", "provider_symbol", "canonical_symbol",
    "market_or_venue", "bar_interval", "event_timezone", "timestamp_semantics",
    "session_coverage", "session_coverage_policy", "price_adjustment_semantics",
    "volume_adjustment_semantics", "corporate_action_handling", "data_time_basis",
    "value_authenticity", "intended_use", "expected_start_time", "expected_end_time",
    "column_mapping_profile_id", "notes",
)

CANONICAL_BAR_FIELDS = (
    "canonical_symbol", "provider_symbol", "market_or_venue", "interval",
    "event_start_time", "event_end_time", "event_timezone", "session",
    "open", "high", "low", "close", "volume", "trade_count", "vwap", "currency",
    "price_adjustment_semantics", "volume_adjustment_semantics", "value_authenticity",
    "source_artifact_id", "source_row_number", "source_record_id",
)


def _values(enum) -> tuple[str, ...]:
    return tuple(member.value for member in enum)


def build_intake_contract() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "intake_contract_version": INTAKE_CONTRACT_VERSION,
        "document": "phase_3d_local_bar_intake_contract",
        "scope": (
            "Offline validation and deterministic normalization of user-supplied or "
            "licensed historical market-bar exports. No acquisition, no outcome work, "
            "no Phase 3A/3B records, no Phase 3E."
        ),
        "manifest_fields": MANIFEST_FIELDS,
        "canonical_bar_fields": CANONICAL_BAR_FIELDS,
        "supported_artifact_formats_for_normalization": (ArtifactFormat.CSV.value,),
        "declared_but_unsupported_formats": (ArtifactFormat.JSON.value,),
        "supported_encodings": tuple(sorted(SUPPORTED_ENCODINGS)),
        "supported_intervals": _values(BarInterval),
        "sessions": _values(BarSession),
        "timestamp_semantics": _values(TimestampSemantics),
        "price_adjustment_semantics": _values(PriceAdjustmentSemantics),
        "volume_adjustment_semantics": _values(VolumeAdjustmentSemantics),
        "corporate_action_handling": _values(CorporateActionHandling),
        "data_time_basis": _values(DataTimeBasis),
        "value_authenticity": _values(ValueAuthenticity),
        "intended_use": _values(IntendedUse),
        "session_coverage_policies": _values(SessionCoveragePolicy),
        "sort_expectations": _values(SortExpectation),
        "duplicate_policies": _values(DuplicatePolicy),
        "thousands_separator_policies": _values(ThousandsSeparatorPolicy),
        "validation_statuses": _values(IntakeValidationStatus),
        "row_statuses": _values(RowNormalizationStatus),
        "reason_codes": _values(IntakeReasonCode),
        "preregistered_safe_normalizations": (
            "STABLE_SORT_BY_EVENT_START preserves source_row_number provenance",
        ),
        "guarantees": (
            "raw artifact bytes are never modified",
            "missing OHLCV is never inferred",
            "ambiguous evidence stays ambiguous; bars are never repaired by guessing",
            "no absolute path enters any deterministic identity",
            "retrieval_time, export_time, and event times are distinct concepts",
            "no outcome value enters any pre-outcome identity",
            "case association validates references only and performs no outcome work",
        ),
    }


__all__ = [
    "MANIFEST_FIELDS",
    "CANONICAL_BAR_FIELDS",
    "build_intake_contract",
]
