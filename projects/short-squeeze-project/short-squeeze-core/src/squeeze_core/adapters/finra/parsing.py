import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.contracts.validation import require_aware_utc

from .semantics import DateOnlyPublicationPolicy, PercentageUnit


_DECIMAL = re.compile(r"^[+]?(?:\d+(?:\.\d*)?|\.\d+)$")


class FinraParseError(ValueError):
    def __init__(self, code: DiagnosticCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class PublicationAvailability:
    timestamp: datetime
    publication_date: date
    uncertain: bool
    policy: DateOnlyPublicationPolicy | None
    timezone_label: str


def _decimal(value: Any, *, code: DiagnosticCode, label: str) -> Decimal:
    if isinstance(value, bool):
        raise FinraParseError(code, f"{label} must be numeric")
    text = str(value).strip()
    if not _DECIMAL.fullmatch(text):
        raise FinraParseError(code, f"{label} uses an unsupported numeric format")
    try:
        converted = Decimal(text)
    except InvalidOperation as error:
        raise FinraParseError(code, f"{label} must be numeric") from error
    if not converted.is_finite():
        raise FinraParseError(code, f"{label} must be finite")
    return converted


def parse_nonnegative_integer(value: Any, field: str) -> int | None:
    if value is None or value == "":
        return None
    code = (
        DiagnosticCode.FINRA_INVALID_SHORT_SHARES
        if field == "short_shares"
        else DiagnosticCode.INVALID_NUMERIC_VALUE
    )
    converted = _decimal(value, code=code, label=field)
    if converted < 0 or converted != converted.to_integral_value():
        raise FinraParseError(code, f"{field} must be a nonnegative whole number")
    return int(converted)


def parse_nonnegative_decimal(value: Any, field: str) -> Decimal | None:
    if value is None or value == "":
        return None
    converted = _decimal(
        value, code=DiagnosticCode.INVALID_NUMERIC_VALUE, label=field
    )
    if converted < 0:
        raise FinraParseError(
            DiagnosticCode.INVALID_NUMERIC_VALUE,
            f"{field} must not be negative",
        )
    return converted


def parse_percentage(
    value: Any, unit: PercentageUnit | str | None
) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed_unit = PercentageUnit(unit)
    except (TypeError, ValueError) as error:
        raise FinraParseError(
            DiagnosticCode.FINRA_UNSUPPORTED_PERCENT_UNIT,
            "percentage unit is unsupported or absent",
        ) from error
    text = str(value).strip()
    if parsed_unit is PercentageUnit.FORMATTED_PERCENT_STRING:
        if not text.endswith("%"):
            raise FinraParseError(
                DiagnosticCode.FINRA_INVALID_PERCENT_FORMAT,
                "formatted percentage must end with a percent sign",
            )
        text = text[:-1].strip()
    elif text.endswith("%"):
        raise FinraParseError(
            DiagnosticCode.FINRA_INVALID_PERCENT_FORMAT,
            "percent sign requires FORMATTED_PERCENT_STRING",
        )
    converted = _decimal(
        text, code=DiagnosticCode.FINRA_INVALID_PERCENT_FORMAT, label="percentage"
    )
    if parsed_unit is PercentageUnit.DECIMAL_FRACTION:
        converted *= Decimal("100")
    if converted < 0:
        raise FinraParseError(
            DiagnosticCode.FINRA_INVALID_PERCENT_FORMAT,
            "percentage must not be negative",
        )
    return converted


def parse_settlement_date(value: str | None) -> date:
    if value is None or not value.strip():
        raise FinraParseError(
            DiagnosticCode.FINRA_MISSING_SETTLEMENT_DATE,
            "settlement date is required",
        )
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as error:
        raise FinraParseError(
            DiagnosticCode.FINRA_INVALID_SETTLEMENT_DATE,
            "settlement date must be an ISO date",
        ) from error
    return parsed


def _timezone(value: str):
    if value == "UTC":
        return UTC
    if len(value) == 6 and value[0] in "+-" and value[3] == ":":
        hours = int(value[1:3])
        minutes = int(value[4:6])
        if hours > 23 or minutes > 59:
            raise ValueError("invalid UTC offset")
        offset = timedelta(hours=hours, minutes=minutes)
        return timezone(-offset if value[0] == "-" else offset)
    return ZoneInfo(value)


def parse_timestamp(
    value: str, timezone_name: str | None, *, field: str
) -> tuple[datetime, str]:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            if timezone_name is None:
                raise ZoneInfoNotFoundError("timezone is absent")
            parsed = parsed.replace(tzinfo=_timezone(timezone_name))
        return parsed.astimezone(UTC), timezone_name or "EMBEDDED_OFFSET"
    except (ValueError, ZoneInfoNotFoundError) as error:
        code = (
            DiagnosticCode.FINRA_UNKNOWN_PUBLICATION_TIMEZONE
            if field == "publication_date"
            else DiagnosticCode.UNKNOWN_TIMEZONE
        )
        raise FinraParseError(code, f"{field} timezone is unknown or invalid") from error


def parse_publication_availability(
    value: str | None,
    *,
    timezone_name: str | None,
    policy: DateOnlyPublicationPolicy,
    received_at: datetime,
) -> PublicationAvailability:
    received = require_aware_utc(received_at)
    if value is None or not value.strip():
        raise FinraParseError(
            DiagnosticCode.FINRA_MISSING_PUBLICATION_DATE,
            "publication date is required for point-in-time availability",
        )
    raw = value.strip()
    if len(raw) != 10:
        timestamp, label = parse_timestamp(raw, timezone_name, field="publication_date")
        try:
            local_date = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError as error:
            raise FinraParseError(
                DiagnosticCode.FINRA_INVALID_PUBLICATION_DATE,
                "publication timestamp is invalid",
            ) from error
        return PublicationAvailability(timestamp, local_date, False, None, label)

    try:
        publication_date = date.fromisoformat(raw)
    except ValueError as error:
        raise FinraParseError(
            DiagnosticCode.FINRA_INVALID_PUBLICATION_DATE,
            "publication date must be ISO formatted",
        ) from error
    if policy is DateOnlyPublicationPolicy.STRICT_REJECT:
        raise FinraParseError(
            DiagnosticCode.FINRA_DATE_ONLY_PUBLICATION,
            "date-only publication lacks a defensible exact availability time",
        )
    if policy is DateOnlyPublicationPolicy.INGESTION_TIME_UNCERTAIN_PLACEHOLDER:
        return PublicationAvailability(
            received, publication_date, True, policy, "UNKNOWN"
        )
    if timezone_name is None:
        raise FinraParseError(
            DiagnosticCode.FINRA_UNKNOWN_PUBLICATION_TIMEZONE,
            "end-of-day publication policy requires a timezone",
        )
    try:
        next_day = publication_date + timedelta(days=1)
        boundary = datetime.combine(next_day, time.min, tzinfo=_timezone(timezone_name))
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise FinraParseError(
            DiagnosticCode.FINRA_UNKNOWN_PUBLICATION_TIMEZONE,
            "publication timezone is unknown or invalid",
        ) from error
    return PublicationAvailability(
        boundary.astimezone(UTC), publication_date, True, policy, timezone_name
    )
