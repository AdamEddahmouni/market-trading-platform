"""CFTC COT quality taxonomy — fail closed on ambiguity."""

from __future__ import annotations

from enum import StrEnum


class CotQualityFlag(StrEnum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    REPORT_NOT_YET_RELEASED = "REPORT_NOT_YET_RELEASED"
    PUBLICATION_TIME_INFERRED = "PUBLICATION_TIME_INFERRED"
    HISTORICAL_PUBLICATION_TIME_INFERRED = "HISTORICAL_PUBLICATION_TIME_INFERRED"
    PRODUCT_MAPPING_UNRESOLVED = "PRODUCT_MAPPING_UNRESOLVED"
    REPORT_SCOPE_AMBIGUOUS = "REPORT_SCOPE_AMBIGUOUS"
    CLASSIFICATION_UNAVAILABLE = "CLASSIFICATION_UNAVAILABLE"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    SOURCE_VERSION_CHANGED = "SOURCE_VERSION_CHANGED"
    EXPECTED_NOT_YET_AVAILABLE = "EXPECTED_NOT_YET_AVAILABLE"
    BELOW_REPORTING_THRESHOLD = "BELOW_REPORTING_THRESHOLD"
    REPORT_FAMILY_NOT_APPLICABLE = "REPORT_FAMILY_NOT_APPLICABLE"


def quality_blocks_positioning(flags: tuple[str, ...]) -> bool:
    blocking = {
        CotQualityFlag.SOURCE_UNAVAILABLE.value,
        CotQualityFlag.REPORT_NOT_YET_RELEASED.value,
        CotQualityFlag.REPORT_SCOPE_AMBIGUOUS.value,
        CotQualityFlag.PRODUCT_MAPPING_UNRESOLVED.value,
        CotQualityFlag.EXPECTED_NOT_YET_AVAILABLE.value,
    }
    return any(flag in blocking for flag in flags)


def empty_is_not_zero(flags: tuple[str, ...]) -> bool:
    """Distinguish no-data from zero positions."""
    return quality_blocks_positioning(flags)


__all__ = [
    "CotQualityFlag",
    "empty_is_not_zero",
    "quality_blocks_positioning",
]
