import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import MarketBarRecord
from .semantics import BarInterval, BarIntervalKind, BarIntervalUnit, BarTimestampMeaning


class BarParseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ParsedBarTimestamp:
    timestamp: datetime
    representation: str
    timezone_label: str
    time_only: bool = False


@dataclass(frozen=True, slots=True)
class BarBoundaries:
    start: datetime
    end: datetime
    end_exclusive: bool = True


def _fixed_duration(interval: BarInterval) -> timedelta:
    return {
        BarIntervalUnit.MINUTE: timedelta(minutes=interval.magnitude),
        BarIntervalUnit.HOUR: timedelta(hours=interval.magnitude),
    }[interval.unit]


def _timezone(value: str):
    if value == "UTC":
        return UTC
    if re.fullmatch(r"[+-]\d{2}:\d{2}", value):
        hours, minutes = int(value[1:3]), int(value[4:6])
        if hours > 23 or minutes > 59:
            raise ValueError("invalid offset")
        offset = timedelta(hours=hours, minutes=minutes)
        return timezone(-offset if value[0] == "-" else offset)
    return ZoneInfo(value)


def _localize(naive: datetime, timezone_name: str, field: str) -> datetime:
    try:
        zone = _timezone(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise BarParseError("BAR_MISSING_TIMEZONE", f"{field} timezone is unknown") from error
    if isinstance(zone, ZoneInfo):
        candidates = []
        for fold in (0, 1):
            candidate = naive.replace(tzinfo=zone, fold=fold)
            roundtrip = candidate.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
            if roundtrip == naive:
                candidates.append(candidate)
        unique_offsets = {candidate.utcoffset() for candidate in candidates}
        if not candidates:
            raise BarParseError("BAR_NONEXISTENT_LOCAL_TIME", f"{field} local time is nonexistent")
        if len(unique_offsets) > 1:
            raise BarParseError("BAR_AMBIGUOUS_LOCAL_TIME", f"{field} local time is ambiguous")
        return candidates[0]
    return naive.replace(tzinfo=zone)


def parse_bar_timestamp(
    value: str | None,
    *,
    session_date: date | None,
    timezone_name: str | None,
    field: str,
) -> ParsedBarTimestamp | None:
    if value is None or not value.strip():
        return None
    raw = value.strip()
    time_only = bool(re.fullmatch(r"\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?", raw))
    try:
        if time_only:
            if session_date is None:
                raise BarParseError("BAR_MISSING_START", f"{field} time-only value requires session date")
            if timezone_name is None:
                raise BarParseError("BAR_MISSING_TIMEZONE", f"{field} time-only value requires timezone")
            naive = datetime.combine(session_date, time.fromisoformat(raw))
            parsed = _localize(naive, timezone_name, field)
            label = timezone_name
        else:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                if timezone_name is None:
                    raise BarParseError("BAR_MISSING_TIMEZONE", f"{field} timestamp requires timezone")
                parsed = _localize(parsed, timezone_name, field)
                label = timezone_name
            else:
                label = timezone_name or "EMBEDDED_OFFSET"
    except BarParseError:
        raise
    except ValueError as error:
        raise BarParseError("BAR_INVALID_TIMESTAMP", f"{field} timestamp is invalid") from error
    return ParsedBarTimestamp(parsed.astimezone(UTC), raw, label, time_only)


def resolve_bar_boundaries(record: MarketBarRecord) -> BarBoundaries:
    start = parse_bar_timestamp(
        record.bar_start,
        session_date=record.session_date,
        timezone_name=record.timezone,
        field="bar_start",
    )
    end = parse_bar_timestamp(
        record.bar_end,
        session_date=record.session_date,
        timezone_name=record.timezone,
        field="bar_end",
    )
    if start is not None and end is not None:
        if end.timestamp <= start.timestamp:
            raise BarParseError("BAR_INVALID_BOUNDARY", "bar end must be after bar start")
        if (
            record.interval.kind is BarIntervalKind.FIXED
            and end.timestamp - start.timestamp != _fixed_duration(record.interval)
        ):
            raise BarParseError(
                "BAR_INVALID_BOUNDARY",
                "explicit bar boundary duration does not match the fixed interval",
            )
        return BarBoundaries(start.timestamp, end.timestamp)
    if start is not None or end is not None:
        raise BarParseError("BAR_INVALID_BOUNDARY", "both explicit bar boundaries are required")
    if record.interval.kind is BarIntervalKind.SESSION_BASED:
        raise BarParseError("BAR_INVALID_BOUNDARY", "session-based daily bars require explicit boundaries")
    if record.provider_timestamp is None:
        raise BarParseError("BAR_MISSING_START", "bar boundaries or provider timestamp are required")
    if record.timestamp_meaning not in {BarTimestampMeaning.START, BarTimestampMeaning.END}:
        raise BarParseError("BAR_UNKNOWN_TIMESTAMP_MEANING", "provider timestamp meaning must be START or END")
    label = parse_bar_timestamp(
        record.provider_timestamp,
        session_date=record.session_date,
        timezone_name=record.timezone,
        field="provider_timestamp",
    )
    assert label is not None
    duration = _fixed_duration(record.interval)
    if record.timestamp_meaning is BarTimestampMeaning.START:
        return BarBoundaries(label.timestamp, label.timestamp + duration)
    return BarBoundaries(label.timestamp - duration, label.timestamp)
