from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from urllib.parse import unquote_plus, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from squeeze_core.adapters.diagnostics import DiagnosticCode

from .semantics import NewsDateOnlyPolicy, URL_POLICY_VERSION


class NewsParseError(ValueError):
    def __init__(self, code: DiagnosticCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ParsedNewsTimestamp:
    timestamp: datetime
    representation: str
    timezone_label: str
    date_only: bool = False
    uncertain: bool = False


@dataclass(frozen=True, slots=True)
class SanitizedNewsUrl:
    url: str
    policy_version: str
    fragment_removed: bool
    removed_tracking_parameters: tuple[str, ...]


_TRACKING_KEYS = frozenset({"gclid", "fbclid", "mc_cid", "mc_eid"})
_SENSITIVE_KEYS = frozenset(
    {"token", "api_key", "apikey", "auth", "authorization", "session", "signature"}
)


def sanitize_news_url(value: str | None) -> SanitizedNewsUrl | None:
    if value is None or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as error:
        raise NewsParseError(DiagnosticCode.NEWS_INVALID_URL, "news URL is invalid") from error
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise NewsParseError(DiagnosticCode.NEWS_INVALID_URL, "news URL requires HTTP(S) and a host")
    if parsed.username is not None or parsed.password is not None:
        raise NewsParseError(DiagnosticCode.NEWS_INVALID_URL, "news URL cannot contain credentials")

    kept: list[str] = []
    removed: list[str] = []
    for pair in parsed.query.split("&") if parsed.query else ():
        raw_key = pair.partition("=")[0]
        key = unquote_plus(raw_key).lower()
        if key in _SENSITIVE_KEYS:
            raise NewsParseError(DiagnosticCode.NEWS_SENSITIVE_URL, "news URL contains a sensitive query key")
        if key.startswith("utm_") or key in _TRACKING_KEYS:
            removed.append(unquote_plus(raw_key))
        else:
            kept.append(pair)

    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    default_port = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    netloc = host if port is None or default_port else f"{host}:{port}"
    sanitized = urlunsplit((scheme, netloc, parsed.path or "", "&".join(kept), ""))
    return SanitizedNewsUrl(
        url=sanitized,
        policy_version=URL_POLICY_VERSION,
        fragment_removed=bool(parsed.fragment),
        removed_tracking_parameters=tuple(removed),
    )


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


def parse_news_timestamp(
    value: str | None,
    *,
    timezone_name: str | None,
    policy: NewsDateOnlyPolicy,
    field: str,
    received_at: datetime,
) -> ParsedNewsTimestamp | None:
    if value is None or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed_date = date.fromisoformat(raw) if len(raw) == 10 else None
    except ValueError:
        parsed_date = None
    if parsed_date is not None:
        if policy is NewsDateOnlyPolicy.STRICT:
            raise NewsParseError(
                DiagnosticCode.NEWS_DATE_ONLY_PUBLICATION,
                f"{field} date-only value is rejected by strict policy",
            )
        if policy is NewsDateOnlyPolicy.UNCERTAIN_PLACEHOLDER:
            return ParsedNewsTimestamp(
                received_at.astimezone(UTC), raw, "UNKNOWN", date_only=True, uncertain=True
            )
        if timezone_name is None:
            raise NewsParseError(
                DiagnosticCode.NEWS_UNKNOWN_PUBLICATION_TIMEZONE,
                f"{field} date-only value requires timezone",
            )
        try:
            local = datetime.combine(parsed_date, time.max, tzinfo=_timezone(timezone_name))
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise NewsParseError(
                DiagnosticCode.NEWS_UNKNOWN_PUBLICATION_TIMEZONE,
                f"{field} timezone is unknown",
            ) from error
        return ParsedNewsTimestamp(
            local.astimezone(UTC), raw, timezone_name, date_only=True
        )

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            if timezone_name is None:
                raise NewsParseError(
                    DiagnosticCode.NEWS_UNKNOWN_PUBLICATION_TIMEZONE,
                    f"{field} timestamp requires timezone",
                )
            parsed = parsed.replace(tzinfo=_timezone(timezone_name))
            label = timezone_name
        else:
            label = timezone_name or "EMBEDDED_OFFSET"
    except NewsParseError:
        raise
    except ZoneInfoNotFoundError as error:
        raise NewsParseError(
            DiagnosticCode.NEWS_UNKNOWN_PUBLICATION_TIMEZONE,
            f"{field} timezone is unknown",
        ) from error
    except ValueError as error:
        raise NewsParseError(
            DiagnosticCode.NEWS_INVALID_TIMESTAMP, f"{field} timestamp is invalid"
        ) from error
    return ParsedNewsTimestamp(parsed.astimezone(UTC), raw, label)
