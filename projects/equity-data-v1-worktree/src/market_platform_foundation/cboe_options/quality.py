"""Cboe public options statistics quality taxonomy."""

from __future__ import annotations

from enum import StrEnum


class CboeOptionsQualityFlag(StrEnum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    COVERAGE_SCOPE_UNCERTAIN = "COVERAGE_SCOPE_UNCERTAIN"
    HISTORICAL_PUBLICATION_TIME_UNKNOWN = "HISTORICAL_PUBLICATION_TIME_UNKNOWN"
    DELAYED_DATA = "DELAYED_DATA"
    SNAPSHOT_CONSISTENCY_UNCERTAIN = "SNAPSHOT_CONSISTENCY_UNCERTAIN"
    SOURCE_RATIO_MISMATCH = "SOURCE_RATIO_MISMATCH"
    TOTAL_RECONCILIATION_MISMATCH = "TOTAL_RECONCILIATION_MISMATCH"
    CUMULATIVE_SERIES_NONMONOTONIC = "CUMULATIVE_SERIES_NONMONOTONIC"
    OPEN_CLOSE_UNKNOWN = "OPEN_CLOSE_UNKNOWN"
    DIRECTION_UNKNOWN = "DIRECTION_UNKNOWN"
    REFERENCE_VERSION_CHANGED = "REFERENCE_VERSION_CHANGED"
    HISTORICAL_COVERAGE_REGIME_CHANGED = "HISTORICAL_COVERAGE_REGIME_CHANGED"
    CURRENT_SNAPSHOT_ONLY = "CURRENT_SNAPSHOT_ONLY"
    PAID_SOURCE_NOT_AUTHORIZED = "PAID_SOURCE_NOT_AUTHORIZED"
    MISSING_VALUE = "MISSING_VALUE"
    UNDEFINED_RATIO = "UNDEFINED_RATIO"


_BLOCKING_FLAGS = frozenset(
    {
        CboeOptionsQualityFlag.SOURCE_UNAVAILABLE.value,
        CboeOptionsQualityFlag.SCHEMA_CHANGED.value,
        CboeOptionsQualityFlag.COVERAGE_SCOPE_UNCERTAIN.value,
        CboeOptionsQualityFlag.MISSING_VALUE.value,
        CboeOptionsQualityFlag.PAID_SOURCE_NOT_AUTHORIZED.value,
    }
)


def quality_blocks_statistic(flags: tuple[str, ...]) -> bool:
    return any(flag in _BLOCKING_FLAGS for flag in flags)


def quality_blocks_snapshot(flags: tuple[str, ...]) -> bool:
    blocking = _BLOCKING_FLAGS | {
        CboeOptionsQualityFlag.CURRENT_SNAPSHOT_ONLY.value,
    }
    return any(flag in blocking for flag in flags)


def quality_blocks_reference(flags: tuple[str, ...]) -> bool:
    return quality_blocks_statistic(flags)


def default_activity_flags() -> tuple[str, ...]:
    """Aggregate activity never reveals opening/closing or aggressor direction."""
    return (
        CboeOptionsQualityFlag.OPEN_CLOSE_UNKNOWN.value,
        CboeOptionsQualityFlag.DIRECTION_UNKNOWN.value,
    )


__all__ = [
    "CboeOptionsQualityFlag",
    "default_activity_flags",
    "quality_blocks_reference",
    "quality_blocks_snapshot",
    "quality_blocks_statistic",
]
