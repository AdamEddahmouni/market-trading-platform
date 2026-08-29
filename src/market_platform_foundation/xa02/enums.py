"""XA-02 versioned enumerations."""

from __future__ import annotations

from enum import StrEnum


class SourceProvider(StrEnum):
    FRED = "FRED"


class AdmissionStatus(StrEnum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


class RevisionClassification(StrEnum):
    ORIGINAL_OR_AS_REPORTED = "ORIGINAL_OR_AS_REPORTED"
    VINTAGE_IDENTIFIED = "VINTAGE_IDENTIFIED"
    LATEST_ONLY = "LATEST_ONLY"
    REVISION_STATUS_UNKNOWN = "REVISION_STATUS_UNKNOWN"


class CrossAssetReferenceType(StrEnum):
    MACRO_REFERENCE_FOR = "MACRO_REFERENCE_FOR"
    BENCHMARK_FOR = "BENCHMARK_FOR"
    REFERENCE_RELEVANT_TO = "REFERENCE_RELEVANT_TO"
    UNDERLYING_REFERENCE_FOR = "UNDERLYING_REFERENCE_FOR"


class ReferenceSubjectType(StrEnum):
    CANONICAL_INDICATOR = "CANONICAL_INDICATOR"


class ReferenceTargetType(StrEnum):
    XA_INSTRUMENT = "XA_INSTRUMENT"


SCHEMA_VERSION = 1
IDENTITY_PROFILE = "imp-xa02-admitted-observation-v1"
RELATIONSHIP_PROFILE = "imp-xa02-cross-asset-reference-v1"
