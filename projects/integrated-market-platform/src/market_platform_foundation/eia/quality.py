"""EIA physical energy quality taxonomy — fail closed on ambiguity."""

from __future__ import annotations

from enum import StrEnum


class EiaQualityFlag(StrEnum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    AUTH_UNAVAILABLE = "AUTH_UNAVAILABLE"
    REPORT_NOT_YET_RELEASED = "REPORT_NOT_YET_RELEASED"
    EXPECTED_NOT_YET_RELEASED = "EXPECTED_NOT_YET_RELEASED"
    PUBLICATION_PENDING = "PUBLICATION_PENDING"
    API_RELEASE_LAG = "API_RELEASE_LAG"
    HISTORICAL_VINTAGE_UNAVAILABLE = "HISTORICAL_VINTAGE_UNAVAILABLE"
    PIT_UNCERTAIN = "PIT_UNCERTAIN"
    SERIES_UNAVAILABLE = "SERIES_UNAVAILABLE"
    FACET_MAPPING_UNRESOLVED = "FACET_MAPPING_UNRESOLVED"
    METHODOLOGY_CHANGED = "METHODOLOGY_CHANGED"
    SOURCE_VERSION_CHANGED = "SOURCE_VERSION_CHANGED"
    WITHHELD = "WITHHELD"
    MISSING_VALUE = "MISSING_VALUE"
    REGION_UNRESOLVED = "REGION_UNRESOLVED"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    METRIC_CLASS_MISMATCH = "METRIC_CLASS_MISMATCH"


_BLOCKING_FLAGS = frozenset(
    {
        EiaQualityFlag.SOURCE_UNAVAILABLE.value,
        EiaQualityFlag.AUTH_UNAVAILABLE.value,
        EiaQualityFlag.REPORT_NOT_YET_RELEASED.value,
        EiaQualityFlag.EXPECTED_NOT_YET_RELEASED.value,
        EiaQualityFlag.PUBLICATION_PENDING.value,
        EiaQualityFlag.SERIES_UNAVAILABLE.value,
        EiaQualityFlag.FACET_MAPPING_UNRESOLVED.value,
        EiaQualityFlag.REGION_UNRESOLVED.value,
        EiaQualityFlag.UNIT_MISMATCH.value,
        EiaQualityFlag.METRIC_CLASS_MISMATCH.value,
    }
)


def quality_blocks_fundamentals(flags: tuple[str, ...]) -> bool:
    return any(flag in _BLOCKING_FLAGS for flag in flags)


def empty_is_not_zero(flags: tuple[str, ...]) -> bool:
    return quality_blocks_fundamentals(flags)


def vintage_honesty_flags(*, history_class: str, pit_confidence: str) -> tuple[str, ...]:
    """Stamp current API history as not original-release vintage.

    Does not select, rank, or derive analytics. ``HISTORICAL_VINTAGE_UNAVAILABLE``
    and ``PIT_UNCERTAIN`` are honesty flags, not blocking fundamentals gates.
    """
    if history_class != "CURRENT_API_HISTORY":
        return ()
    flags = [EiaQualityFlag.HISTORICAL_VINTAGE_UNAVAILABLE.value]
    if pit_confidence == "HISTORICAL_PIT_UNCERTAIN":
        flags.append(EiaQualityFlag.PIT_UNCERTAIN.value)
    return tuple(flags)


__all__ = [
    "EiaQualityFlag",
    "empty_is_not_zero",
    "quality_blocks_fundamentals",
    "vintage_honesty_flags",
]
