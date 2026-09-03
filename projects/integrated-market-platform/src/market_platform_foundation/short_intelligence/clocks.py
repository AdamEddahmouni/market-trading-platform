"""Point-in-time clocks. Settlement/trade dates are not availability."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..normalization.equity_bars import iso_to_epoch_ns

NY = ZoneInfo("America/New_York")
UTC = timezone.utc


def to_utc_iso(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = text + "T00:00:00Z"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ny_wall_to_utc_iso(date_text: str, hour: int, minute: int, second: int = 0) -> str:
    local = datetime.strptime(date_text[:10], "%Y-%m-%d").replace(
        hour=hour, minute=minute, second=second, tzinfo=NY
    )
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def nyse_file_timestamp_to_utc(stamp: str) -> str:
    """NYSE trailer YYYYMMDDHHMMSS. Timezone treated as America/New_York (INFERRED from NYSE UI)."""
    return nasdaq_file_timestamp_to_utc(stamp)


def cboe_file_timestamp_to_utc(stamp: str) -> str:
    """Cboe trailer YYYYMMDDHHMMSS. Timezone treated as America/Chicago (INFERRED from Cboe operations)."""
    text = stamp.strip()
    if len(text) != 14 or not text.isdigit():
        raise ValueError(f"CBOE_TIMESTAMP_INVALID:{stamp}")
    chicago = ZoneInfo("America/Chicago")
    local = datetime(
        int(text[0:4]),
        int(text[4:6]),
        int(text[6:8]),
        int(text[8:10]),
        int(text[10:12]),
        int(text[12:14]),
        tzinfo=chicago,
    )
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def nasdaq_file_timestamp_to_utc(stamp: str) -> str:
    """Nasdaq trailer YYYYMMDDHHMMSS. Timezone treated as America/New_York (INFERRED from Trader UI)."""
    text = stamp.strip()
    if len(text) != 14 or not text.isdigit():
        raise ValueError(f"NASDAQ_TIMESTAMP_INVALID:{stamp}")
    local = datetime(
        int(text[0:4]),
        int(text[4:6]),
        int(text[6:8]),
        int(text[8:10]),
        int(text[10:12]),
        int(text[12:14]),
        tzinfo=NY,
    )
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def clocks_short_interest(
    *,
    settlement_date: str,
    publication_date: str,
    observed_time: str,
    retrieved_time: str,
    provider_available_time: str = "",
) -> dict[str, str]:
    available = provider_available_time or ny_wall_to_utc_iso(publication_date, 16, 40)
    return {
        "settlement_date": settlement_date[:10],
        "settlement_time": to_utc_iso(settlement_date[:10]),
        "official_publication_date": publication_date[:10],
        "provider_available_time": available,
        "observed_time": to_utc_iso(observed_time),
        "retrieved_time": to_utc_iso(retrieved_time),
        "ingested_time": to_utc_iso(retrieved_time),
        "available_time": available,
    }


def clocks_short_sale(
    *,
    trade_report_date: str,
    observed_time: str,
    retrieved_time: str,
    provider_publication_time: str = "",
) -> dict[str, str]:
    # Daily files are typically next-session. Without an official intraday stamp, available_time
    # is first observation/retrieval, never backdated to the trade date (DOCUMENTED limitation).
    available = to_utc_iso(provider_publication_time or observed_time or retrieved_time)
    return {
        "trade_report_date": trade_report_date[:10],
        "provider_publication_time": to_utc_iso(provider_publication_time) if provider_publication_time else "",
        "observed_time": to_utc_iso(observed_time),
        "retrieved_time": to_utc_iso(retrieved_time),
        "available_time": available,
    }


def clocks_threshold(
    *,
    trade_date: str,
    file_creation_time: str,
    observed_time: str,
    retrieved_time: str,
) -> dict[str, str]:
    available = to_utc_iso(file_creation_time or observed_time or retrieved_time)
    return {
        "trade_date": trade_date[:10],
        "file_creation_time": to_utc_iso(file_creation_time),
        "observed_time": to_utc_iso(observed_time),
        "retrieved_time": to_utc_iso(retrieved_time),
        "available_time": available,
    }


def clocks_ftd(
    *,
    settlement_date: str,
    source_period_start: str,
    source_period_end: str,
    observed_time: str,
    retrieved_time: str,
    official_file_publication_time: str = "",
) -> dict[str, str]:
    # SEC does not publish a reliable per-file timestamp. For live captures,
    # first_observed_time is the safe availability clock.
    available = to_utc_iso(official_file_publication_time or observed_time or retrieved_time)
    return {
        "settlement_date": settlement_date[:10],
        "settlement_time": to_utc_iso(settlement_date[:10]),
        "source_period_start": source_period_start[:10],
        "source_period_end": source_period_end[:10],
        "official_file_publication_time": to_utc_iso(official_file_publication_time)
        if official_file_publication_time
        else "",
        "first_observed_time": to_utc_iso(observed_time),
        "observed_time": to_utc_iso(observed_time),
        "retrieved_time": to_utc_iso(retrieved_time),
        "ingested_time": to_utc_iso(retrieved_time),
        "available_time": available,
    }


def visible_at(clocks: dict[str, str], as_of: str) -> bool:
    available = clocks.get("available_time") or ""
    if not available or not as_of:
        return False
    return iso_to_epoch_ns(to_utc_iso(as_of)) >= iso_to_epoch_ns(to_utc_iso(available))
