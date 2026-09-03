import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.serialization import canonical_hash


_HALT_CODE = re.compile(r"^[A-Z0-9.\-]{1,16}$")


class HaltParseError(ValueError):
    def __init__(self, code: DiagnosticCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class HaltTimestamp:
    timestamp: datetime
    representation: str
    timezone_label: str
    time_only: bool = False


@dataclass(frozen=True, slots=True)
class PublicAvailability:
    timestamp: datetime
    basis: str
    representation: str
    timezone_label: str


def parse_halt_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if not _HALT_CODE.fullmatch(normalized):
        raise HaltParseError(
            DiagnosticCode.HALT_UNKNOWN_CODE,
            "halt code has an unsupported format",
        )
    return normalized


def parse_session_date(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise HaltParseError(
            DiagnosticCode.HALT_DATE_ONLY_VALUE, "session date must be an ISO date"
        ) from error


def _timezone(value: str):
    if value == "UTC":
        return UTC
    if len(value) == 6 and value[0] in "+-" and value[3] == ":":
        hours, minutes = int(value[1:3]), int(value[4:6])
        if hours > 23 or minutes > 59:
            raise ValueError("invalid offset")
        offset = timedelta(hours=hours, minutes=minutes)
        return timezone(-offset if value[0] == "-" else offset)
    return ZoneInfo(value)


def parse_halt_timestamp(
    value: str | None,
    *,
    session_date: date | None,
    timezone_name: str | None,
    field: str,
) -> HaltTimestamp | None:
    if value is None or not value.strip():
        return None
    raw = value.strip()
    if len(raw) == 10:
        try:
            date.fromisoformat(raw)
        except ValueError:
            pass
        else:
            raise HaltParseError(
                DiagnosticCode.HALT_DATE_ONLY_VALUE,
                f"{field} cannot use a date-only value",
            )
    time_only = bool(re.fullmatch(r"\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?", raw))
    try:
        if time_only:
            if session_date is None:
                raise HaltParseError(
                    DiagnosticCode.HALT_TIME_ONLY_VALUE,
                    f"{field} time-only value requires session date",
                )
            if timezone_name is None:
                raise HaltParseError(
                    DiagnosticCode.HALT_UNKNOWN_TIMEZONE,
                    f"{field} time-only value requires timezone",
                )
            parsed_time = time.fromisoformat(raw)
            parsed = datetime.combine(
                session_date, parsed_time, tzinfo=_timezone(timezone_name)
            )
            label = timezone_name
        else:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                if timezone_name is None:
                    raise HaltParseError(
                        DiagnosticCode.HALT_UNKNOWN_TIMEZONE,
                        f"{field} timestamp requires timezone",
                    )
                parsed = parsed.replace(tzinfo=_timezone(timezone_name))
                label = timezone_name
            else:
                label = timezone_name or "EMBEDDED_OFFSET"
    except HaltParseError:
        raise
    except ZoneInfoNotFoundError as error:
        raise HaltParseError(
            DiagnosticCode.HALT_UNKNOWN_TIMEZONE,
            f"{field} timezone is unknown",
        ) from error
    except ValueError as error:
        raise HaltParseError(
            DiagnosticCode.INVALID_NUMERIC_VALUE,
            f"{field} timestamp is invalid",
        ) from error
    return HaltTimestamp(parsed.astimezone(UTC), raw, label, time_only)


def parse_public_availability(
    *,
    publication_at: str | None,
    announcement_at: str | None,
    timezone_name: str | None,
) -> PublicAvailability:
    raw = publication_at if publication_at and publication_at.strip() else announcement_at
    if raw is None or not raw.strip():
        raise HaltParseError(
            DiagnosticCode.HALT_MISSING_ANNOUNCEMENT_TIMESTAMP,
            "no defensible publication or announcement timestamp exists",
        )
    parsed = parse_halt_timestamp(
        raw,
        session_date=None,
        timezone_name=timezone_name,
        field="publication_at" if publication_at else "announcement_at",
    )
    assert parsed is not None
    return PublicAvailability(
        timestamp=parsed.timestamp,
        basis="PUBLICATION_TIMESTAMP" if publication_at else "ANNOUNCEMENT_TIMESTAMP",
        representation=parsed.representation,
        timezone_label=parsed.timezone_label,
    )


def halt_event_key(
    *,
    symbol: str,
    exchange: str | None,
    provider_halt_id: str | None,
    session_date: date | None,
    halt_at: datetime | None,
) -> str:
    if provider_halt_id and provider_halt_id.strip():
        return f"provider:{provider_halt_id.strip()}"
    seed = {
        "symbol": symbol,
        "exchange": exchange,
        "session_date": session_date,
        "halt_at": halt_at,
    }
    return f"derived:{canonical_hash(seed)[:24]}"
