"""Deterministic enums and reason codes for local historical bar intake.

Bar intervals, sessions, and timestamp meaning are reused unchanged from the
existing market-bar adapter so the intake workflow speaks the same vocabulary as
the rest of the repository rather than inventing a parallel one.
"""

from __future__ import annotations

from enum import StrEnum

# Reused market-bar vocabulary -- do not fork these enums.
from squeeze_core.adapters.market_bars.semantics import (  # noqa: F401
    BarInterval,
    BarIntervalKind,
    BarIntervalUnit,
    BarSession,
    BarTimestampMeaning as TimestampSemantics,
)


class ArtifactFormat(StrEnum):
    """Declared raw-artifact format. Only CSV is normalized this batch."""

    CSV = "CSV"
    JSON = "JSON"  # declared-but-unsupported for normalization this batch


class PriceAdjustmentSemantics(StrEnum):
    RAW_UNADJUSTED = "RAW_UNADJUSTED"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    SPLIT_AND_DIVIDEND_ADJUSTED = "SPLIT_AND_DIVIDEND_ADJUSTED"
    UNKNOWN = "UNKNOWN"


class VolumeAdjustmentSemantics(StrEnum):
    RAW_UNADJUSTED = "RAW_UNADJUSTED"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    UNKNOWN = "UNKNOWN"


class CorporateActionHandling(StrEnum):
    RAW_NO_ADJUSTMENT = "RAW_NO_ADJUSTMENT"
    ADJUSTMENTS_APPLIED = "ADJUSTMENTS_APPLIED"
    UNKNOWN = "UNKNOWN"


class DataTimeBasis(StrEnum):
    """Whether the export represents historical or current values."""

    HISTORICAL = "HISTORICAL"
    CURRENT = "CURRENT"
    UNKNOWN = "UNKNOWN"


class ValueAuthenticity(StrEnum):
    """Whether the bar values are vendor-supplied or a synthetic fixture."""

    VENDOR_SUPPLIED = "VENDOR_SUPPLIED"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"


class IntendedUse(StrEnum):
    """Declared downstream use of the bundle."""

    HISTORICAL_EVIDENCE = "HISTORICAL_EVIDENCE"
    INFRASTRUCTURE_FIXTURE = "INFRASTRUCTURE_FIXTURE"


class SessionCoveragePolicy(StrEnum):
    ALLOW_GAPS = "ALLOW_GAPS"
    REQUIRE_CONTINUOUS = "REQUIRE_CONTINUOUS"


class SortExpectation(StrEnum):
    STABLE_SORT_BY_EVENT_START = "STABLE_SORT_BY_EVENT_START"
    REQUIRE_PRESORTED = "REQUIRE_PRESORTED"


class DuplicatePolicy(StrEnum):
    COLLAPSE_IDENTICAL_REJECT_CONFLICTING = "COLLAPSE_IDENTICAL_REJECT_CONFLICTING"
    REJECT_ALL_DUPLICATES = "REJECT_ALL_DUPLICATES"


class ThousandsSeparatorPolicy(StrEnum):
    DISALLOW = "DISALLOW"
    COMMA = "COMMA"
    SPACE = "SPACE"
    UNDERSCORE = "UNDERSCORE"


class IntakeValidationStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"


class RowNormalizationStatus(StrEnum):
    NORMALIZED = "NORMALIZED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"


class IntakeReasonCode(StrEnum):
    """Deterministic reason codes for blocking, rejecting, or quarantining."""

    # Artifact integrity
    ARTIFACT_MISSING = "ARTIFACT_MISSING"
    ARTIFACT_EMPTY = "ARTIFACT_EMPTY"
    ARTIFACT_BYTE_LENGTH_MISMATCH = "ARTIFACT_BYTE_LENGTH_MISMATCH"
    ARTIFACT_SHA256_MISMATCH = "ARTIFACT_SHA256_MISMATCH"
    UNSUPPORTED_ENCODING = "UNSUPPORTED_ENCODING"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    # Manifest / declaration
    MALFORMED_MANIFEST = "MALFORMED_MANIFEST"
    MANIFEST_SCHEMA_MISMATCH = "MANIFEST_SCHEMA_MISMATCH"
    UNKNOWN_TIMEZONE = "UNKNOWN_TIMEZONE"
    AMBIGUOUS_TIMEZONE = "AMBIGUOUS_TIMEZONE"
    NONEXISTENT_LOCAL_TIME = "NONEXISTENT_LOCAL_TIME"
    MISSING_TIMESTAMP_SEMANTICS = "MISSING_TIMESTAMP_SEMANTICS"
    MISSING_INTERVAL = "MISSING_INTERVAL"
    UNSUPPORTED_INTERVAL = "UNSUPPORTED_INTERVAL"
    MISSING_ADJUSTMENT_SEMANTICS = "MISSING_ADJUSTMENT_SEMANTICS"
    UNSUPPORTED_ADJUSTMENT_SEMANTICS = "UNSUPPORTED_ADJUSTMENT_SEMANTICS"
    CONTRADICTORY_ADJUSTMENT_SEMANTICS = "CONTRADICTORY_ADJUSTMENT_SEMANTICS"
    DATA_TIME_BASIS_UNKNOWN = "DATA_TIME_BASIS_UNKNOWN"
    # Row / value integrity
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    EVENT_TIME_OUTSIDE_COVERAGE = "EVENT_TIME_OUTSIDE_COVERAGE"
    MIXED_INTERVALS_UNDECLARED = "MIXED_INTERVALS_UNDECLARED"
    SYMBOL_MISMATCH = "SYMBOL_MISMATCH"
    MARKET_VENUE_MISMATCH = "MARKET_VENUE_MISMATCH"
    MISSING_OHLC_VALUE = "MISSING_OHLC_VALUE"
    MALFORMED_DECIMAL = "MALFORMED_DECIMAL"
    NAN_OR_INFINITY = "NAN_OR_INFINITY"
    NEGATIVE_VOLUME = "NEGATIVE_VOLUME"
    NEGATIVE_TRADE_COUNT = "NEGATIVE_TRADE_COUNT"
    INVALID_OHLC_RELATIONSHIP = "INVALID_OHLC_RELATIONSHIP"
    INVALID_BOUNDARY_DURATION = "INVALID_BOUNDARY_DURATION"
    MALFORMED_ROW = "MALFORMED_ROW"
    # Cross-row integrity
    DUPLICATE_TIMESTAMP = "DUPLICATE_TIMESTAMP"
    CONFLICTING_DUPLICATE_BAR = "CONFLICTING_DUPLICATE_BAR"
    OVERLAPPING_BARS = "OVERLAPPING_BARS"
    NON_MONOTONIC_ORDER = "NON_MONOTONIC_ORDER"
    COVERAGE_GAP = "COVERAGE_GAP"
    # Provenance / safety
    CURRENT_VALUE_AS_HISTORICAL = "CURRENT_VALUE_AS_HISTORICAL"
    SYNTHETIC_VALUE_AS_HISTORICAL = "SYNTHETIC_VALUE_AS_HISTORICAL"
    ABSOLUTE_PATH_IN_IDENTITY = "ABSOLUTE_PATH_IN_IDENTITY"
    CREDENTIAL_LIKE_VALUE_PRESENT = "CREDENTIAL_LIKE_VALUE_PRESENT"
    # Case association
    CASE_ASSOCIATION_WITHOUT_DECLARATION = "CASE_ASSOCIATION_WITHOUT_DECLARATION"
    UNKNOWN_CASE_ID = "UNKNOWN_CASE_ID"
    UNKNOWN_BOUNDARY_ID = "UNKNOWN_BOUNDARY_ID"
    CASE_SYMBOL_INCOMPATIBLE = "CASE_SYMBOL_INCOMPATIBLE"
    CASE_COVERAGE_INCOMPATIBLE = "CASE_COVERAGE_INCOMPATIBLE"
    CASE_INTERVAL_INCOMPATIBLE = "CASE_INTERVAL_INCOMPATIBLE"


# Encodings the CSV adapter will decode. Anything else is UNSUPPORTED_ENCODING.
SUPPORTED_ENCODINGS = frozenset({"utf-8", "utf-8-sig", "ascii", "latin-1"})

# Substrings that mark a value as credential-like. Used to keep secrets out of
# committed fixtures and generated outputs. Kept specific enough not to collide
# with legitimate schema field names (e.g. the ``null_tokens`` mapping field).
CREDENTIAL_LIKE_TOKENS = (
    "password", "passwd", "secret", "api_key", "apikey", "access_key",
    "private_key", "client_secret", "auth_token", "access_token", "refresh_token",
    "bearer ", "authorization",
)
