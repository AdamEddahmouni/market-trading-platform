from datetime import UTC, datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .validation import TradeQuoteValidationError


_OFFSET = re.compile(r"^(?P<sign>[+-])(?P<hours>\d{2}):(?P<minutes>\d{2})$")


def _source_zone(label: str | None):
    if label is None:
        raise TradeQuoteValidationError(
            "TRADE_QUOTE_MISSING_TIMEZONE",
            "A naive trade/quote timestamp requires an explicit source timezone.",
        )
    match = _OFFSET.fullmatch(label)
    if match:
        minutes = int(match.group("hours")) * 60 + int(match.group("minutes"))
        if minutes > 14 * 60:
            raise TradeQuoteValidationError(
                "TRADE_QUOTE_UNKNOWN_TIMEZONE", "Numeric timezone offset is out of range."
            )
        if match.group("sign") == "-":
            minutes = -minutes
        return timezone(timedelta(minutes=minutes))
    try:
        return ZoneInfo(label)
    except ZoneInfoNotFoundError as exc:
        raise TradeQuoteValidationError(
            "TRADE_QUOTE_UNKNOWN_TIMEZONE", "Source timezone is not available."
        ) from exc


def parse_trade_quote_timestamp(
    value: str | datetime, *, source_timezone: str | None
) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text or re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            raise TradeQuoteValidationError(
                "TRADE_QUOTE_INVALID_TIMESTAMP", "Timestamp must include an exact time."
            )
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TradeQuoteValidationError(
                "TRADE_QUOTE_INVALID_TIMESTAMP", "Timestamp is not valid ISO-8601."
            ) from exc
    else:
        raise TradeQuoteValidationError(
            "TRADE_QUOTE_INVALID_TIMESTAMP", "Timestamp must be text or datetime."
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=_source_zone(source_timezone))
    return parsed.astimezone(UTC)

