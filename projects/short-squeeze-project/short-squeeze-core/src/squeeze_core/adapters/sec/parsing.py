import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import PurePath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.contracts.validation import require_aware_utc

from .semantics import DateOnlyAvailabilityPolicy


_CIK = re.compile(r"^\d{1,10}$")
_ACCESSION = re.compile(r"^(\d{10})-(\d{2})-(\d{6})$")
_COMPACT_ACCESSION = re.compile(r"^(\d{10})(\d{2})(\d{6})$")
_FORM = re.compile(r"^[A-Z0-9]+(?:[ -][A-Z0-9]+)*(?:/A)?$")


class SecParseError(ValueError):
    def __init__(self, code: DiagnosticCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class PublicAvailability:
    timestamp: datetime
    basis: str
    uncertain: bool
    timezone_label: str


def parse_cik(value: str | None) -> str:
    if value is None or not str(value).strip():
        raise SecParseError(DiagnosticCode.SEC_MISSING_CIK, "CIK is missing")
    text = str(value).strip()
    if not _CIK.fullmatch(text):
        raise SecParseError(DiagnosticCode.SEC_INVALID_CIK, "CIK must contain one to ten digits")
    return text.zfill(10)


def parse_accession_number(value: str | None) -> str:
    if value is None or not str(value).strip():
        raise SecParseError(DiagnosticCode.SEC_MISSING_ACCESSION, "accession number is missing")
    text = str(value).strip()
    if match := _ACCESSION.fullmatch(text):
        return "-".join(match.groups())
    if match := _COMPACT_ACCESSION.fullmatch(text):
        return "-".join(match.groups())
    raise SecParseError(DiagnosticCode.SEC_INVALID_ACCESSION, "accession number has an unsupported format")


def parse_form_type(value: str | None) -> str:
    if value is None or not str(value).strip():
        raise SecParseError(DiagnosticCode.SEC_MISSING_FORM_TYPE, "form type is missing")
    normalized = " ".join(str(value).strip().upper().split())
    if not _FORM.fullmatch(normalized):
        raise SecParseError(DiagnosticCode.SEC_INVALID_FORM_TYPE, "form type is malformed")
    return normalized


def parse_period_of_report(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise SecParseError(DiagnosticCode.INVALID_NUMERIC_VALUE, "period of report must be an ISO date") from error


def parse_document_count(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        converted = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as error:
        raise SecParseError(DiagnosticCode.SEC_INVALID_DOCUMENT_COUNT, "document count must be numeric") from error
    if not converted.is_finite() or converted < 0 or converted != converted.to_integral_value():
        raise SecParseError(DiagnosticCode.SEC_INVALID_DOCUMENT_COUNT, "document count must be a nonnegative whole number")
    return int(converted)


def sanitize_primary_document(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    text = value.strip()
    if (
        "://" in text
        or "?" in text
        or "#" in text
        or "\\" in text
        or "/" in text
        or PurePath(text).name != text
        or text in {".", ".."}
    ):
        raise SecParseError(DiagnosticCode.SEC_REMOTE_URL_SANITIZED, "primary document must be a sanitized basename")
    return text


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


def _exact_timestamp(value: str, timezone_name: str | None) -> tuple[datetime, str]:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            if timezone_name is None:
                raise ZoneInfoNotFoundError("timezone missing")
            parsed = parsed.replace(tzinfo=_timezone(timezone_name))
        return parsed.astimezone(UTC), timezone_name or "EMBEDDED_OFFSET"
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise SecParseError(DiagnosticCode.SEC_UNKNOWN_PUBLICATION_TIMEZONE, "timestamp timezone is unknown or invalid") from error


def _availability_value(
    value: str,
    timezone_name: str | None,
    policy: DateOnlyAvailabilityPolicy,
    received_at: datetime,
) -> tuple[datetime, bool, str]:
    raw = value.strip()
    if len(raw) != 10:
        timestamp, label = _exact_timestamp(raw, timezone_name)
        return timestamp, False, label
    try:
        day = date.fromisoformat(raw)
    except ValueError as error:
        raise SecParseError(DiagnosticCode.SEC_UNKNOWN_AVAILABILITY_TIME, "availability date is invalid") from error
    if policy is DateOnlyAvailabilityPolicy.STRICT_REJECT:
        raise SecParseError(DiagnosticCode.SEC_DATE_ONLY_PUBLICATION, "date-only availability lacks exact time")
    if policy is DateOnlyAvailabilityPolicy.INGESTION_TIME_UNCERTAIN_PLACEHOLDER:
        return require_aware_utc(received_at), True, "UNKNOWN"
    if timezone_name is None:
        raise SecParseError(DiagnosticCode.SEC_UNKNOWN_PUBLICATION_TIMEZONE, "end-of-date policy requires timezone")
    try:
        boundary = datetime.combine(day + timedelta(days=1), time.min, tzinfo=_timezone(timezone_name))
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise SecParseError(DiagnosticCode.SEC_UNKNOWN_PUBLICATION_TIMEZONE, "publication timezone is invalid") from error
    return boundary.astimezone(UTC), True, timezone_name


def parse_public_availability(
    *,
    published_at: str | None,
    publication_timezone: str | None,
    accepted_at: str | None,
    acceptance_timezone: str | None,
    date_only_policy: DateOnlyAvailabilityPolicy,
    received_at: datetime,
) -> PublicAvailability:
    if published_at is not None and published_at.strip():
        timestamp, uncertain, label = _availability_value(
            published_at, publication_timezone, date_only_policy, received_at
        )
        return PublicAvailability(timestamp, "PUBLICATION_TIMESTAMP", uncertain, label)
    if accepted_at is not None and accepted_at.strip():
        if len(accepted_at.strip()) == 10:
            timestamp, uncertain, label = _availability_value(
                accepted_at, acceptance_timezone, date_only_policy, received_at
            )
        else:
            timestamp, label = _exact_timestamp(accepted_at, acceptance_timezone)
            uncertain = False
        return PublicAvailability(timestamp, "SEC_ACCEPTANCE_TIMESTAMP", uncertain, label)
    raise SecParseError(DiagnosticCode.SEC_UNKNOWN_AVAILABILITY_TIME, "no defensible public availability timestamp exists")
