"""Deterministic availability / knowledge-time policy for FRED macro observations."""

from __future__ import annotations

from enum import StrEnum

from .quality import FredQualityFlag

OPEN_KNOWLEDGE_ENDS = frozenset({"", ".", "#NA"})


class AvailabilityPrecision(StrEnum):
    TIMESTAMP = "TIMESTAMP"
    DATE_ONLY = "DATE_ONLY"
    SNAPSHOT = "SNAPSHOT"


def is_date_only(value: str) -> bool:
    text = value.strip()
    return len(text) == 10 and text[4] == "-" and text[7] == "-"


def has_intraday_time(value: str) -> bool:
    if not value or is_date_only(value):
        return False
    normalized = value.replace("Z", "+00:00")
    if "T" not in normalized:
        return False
    time_part = normalized.split("T", 1)[1]
    return time_part not in {"00:00:00", "00:00:00.000000000", "00:00:00+00:00"}


def normalize_knowledge_end(realtime_end: str) -> str:
    text = str(realtime_end or "").strip()
    if text in OPEN_KNOWLEDGE_ENDS or text == "9999-12-31":
        return ""
    return text


def derive_v1_availability(
    *,
    realtime_start: str,
    realtime_end: str,
    observed_time: str = "",
    source_publication_time: str = "",
) -> tuple[str, str, str, str, str, tuple[str, ...]]:
    """Return availability fields for a V1 / ALFRED observation row.

    Policy hierarchy:
    1. Live/platform first observation timestamp (observed_time with intraday precision)
    2. ALFRED realtime_start (knowledge interval start; date-only when provided)
    3. observed_time fallback

    realtime_end is preserved as knowledge_end_date and never used as first availability.
    """
    flags: list[str] = []
    knowledge_start_date = str(realtime_start or "").strip()
    knowledge_end_date = normalize_knowledge_end(realtime_end)
    provider_first_observed_time = ""
    source_pub = str(source_publication_time or "").strip()

    if observed_time and has_intraday_time(observed_time) and observed_time != realtime_end:
        provider_first_observed_time = observed_time
        available_time = observed_time
        precision = AvailabilityPrecision.TIMESTAMP.value
    elif knowledge_start_date:
        if is_date_only(knowledge_start_date):
            available_time = knowledge_start_date
            precision = AvailabilityPrecision.DATE_ONLY.value
        else:
            available_time = knowledge_start_date
            precision = AvailabilityPrecision.TIMESTAMP.value
    elif observed_time:
        available_time = observed_time
        precision = (
            AvailabilityPrecision.DATE_ONLY.value
            if is_date_only(observed_time)
            else AvailabilityPrecision.TIMESTAMP.value
        )
    else:
        available_time = ""
        precision = AvailabilityPrecision.DATE_ONLY.value
        flags.append(FredQualityFlag.PIT_UNAVAILABLE.value)

    if source_pub and source_pub != available_time:
        pass  # retained separately on the observation; not silently aliased

    return (
        available_time,
        precision,
        knowledge_start_date,
        knowledge_end_date,
        provider_first_observed_time,
        tuple(flags),
    )


def derive_v2_snapshot_availability(
    *,
    last_updated: str,
    observed_time: str,
    retrieved_time: str,
) -> tuple[str, str, str, str, tuple[str, ...]]:
    """V2 bulk history is current-state evidence only — never historical vintage truth."""
    snapshot_observed_time = observed_time or retrieved_time
    available_time = snapshot_observed_time
    precision = AvailabilityPrecision.SNAPSHOT.value
    series_last_updated = str(last_updated or "").strip()
    return (
        available_time,
        precision,
        series_last_updated,
        snapshot_observed_time,
        tuple(),
    )


def knowledge_interval_contains(
    decision_time: str,
    *,
    knowledge_start: str,
    knowledge_end: str,
    availability_precision: str,
    available_time: str = "",
) -> tuple[bool, tuple[str, ...]]:
    """True when decision_time falls inside the revision knowledge interval."""
    flags: list[str] = []
    start = str(knowledge_start or available_time or "").strip()
    end = normalize_knowledge_end(knowledge_end)
    if not start or not decision_time:
        return False, tuple(flags)

    precision = availability_precision or (
        AvailabilityPrecision.DATE_ONLY.value if is_date_only(start) else AvailabilityPrecision.TIMESTAMP.value
    )

    if precision == AvailabilityPrecision.DATE_ONLY.value:
        decision_date = decision_time[:10]
        start_date = start[:10]
        end_date = end[:10] if end else ""
        if decision_date < start_date:
            return False, tuple(flags)
        if end_date and decision_date > end_date:
            return False, tuple(flags)
        if decision_date == start_date and has_intraday_time(decision_time):
            flags.append(FredQualityFlag.PIT_UNCERTAIN.value)
            return False, tuple(flags)
        return True, tuple(flags)

    if decision_time < start:
        return False, tuple(flags)
    if end:
        if is_date_only(end):
            if decision_time[:10] > end[:10]:
                return False, tuple(flags)
        elif decision_time > end:
            return False, tuple(flags)
    return True, tuple(flags)


__all__ = [
    "AvailabilityPrecision",
    "OPEN_KNOWLEDGE_ENDS",
    "derive_v1_availability",
    "derive_v2_snapshot_availability",
    "has_intraday_time",
    "is_date_only",
    "knowledge_interval_contains",
    "normalize_knowledge_end",
]
