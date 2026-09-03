from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
from pydantic import ValidationError

from squeeze_core.adapters.market_bars import (
    BarCompletionStatus,
    BarInterval,
    BarIntervalKind,
    BarIntervalUnit,
    BarParseError,
    BarSession,
    BarTimestampMeaning,
    BarVolumeUnit,
    MarketBarRecord,
    parse_bar_timestamp,
    resolve_bar_boundaries,
)
from squeeze_core.serialization import canonical_hash


def record_values(**updates):
    values = {
        "source_record_id": "bar-fixture-1",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "provider": "SCHWAB_SHAPED",
        "provider_record_id": "TESTA-20260115-0930-1m",
        "symbol": "testa",
        "asset_class": "EQUITY",
        "exchange": "xnas",
        "interval": "1_MINUTE",
        "bar_start": "2026-01-15T09:30:00-05:00",
        "bar_end": "2026-01-15T09:31:00-05:00",
        "open": "10.10",
        "high": "10.30",
        "low": "10.00",
        "close": "10.25",
        "volume": "1000",
        "trade_count": "25",
        "vwap": "10.20",
        "volume_unit": "SHARES",
        "session": "REGULAR",
        "session_date": "2026-01-15",
        "timezone": "America/New_York",
        "status": "COMPLETED",
        "publication_timestamp": "2026-01-15T09:31:01-05:00",
    }
    values.update(updates)
    return values


def test_record_is_strict_immutable_and_normalizes_identity_fields():
    record = MarketBarRecord.model_validate(record_values())
    assert record.symbol == "TESTA"
    assert record.exchange == "XNAS"
    assert record.interval is BarInterval.ONE_MINUTE
    assert record.status is BarCompletionStatus.COMPLETED
    assert record.session is BarSession.REGULAR
    assert record.volume_unit is BarVolumeUnit.SHARES
    with pytest.raises(ValidationError):
        MarketBarRecord.model_validate(record_values(unknown=True))
    with pytest.raises(ValidationError):
        record.symbol = "TESTB"


@pytest.mark.parametrize(
    ("interval", "magnitude", "unit", "kind"),
    [
        (BarInterval.ONE_MINUTE, 1, BarIntervalUnit.MINUTE, BarIntervalKind.FIXED),
        (BarInterval.FIVE_MINUTES, 5, BarIntervalUnit.MINUTE, BarIntervalKind.FIXED),
        (BarInterval.FIFTEEN_MINUTES, 15, BarIntervalUnit.MINUTE, BarIntervalKind.FIXED),
        (BarInterval.THIRTY_MINUTES, 30, BarIntervalUnit.MINUTE, BarIntervalKind.FIXED),
        (BarInterval.ONE_HOUR, 1, BarIntervalUnit.HOUR, BarIntervalKind.FIXED),
        (BarInterval.ONE_DAY, 1, BarIntervalUnit.DAY, BarIntervalKind.SESSION_BASED),
    ],
)
def test_interval_identity_is_explicit(interval, magnitude, unit, kind):
    assert interval.magnitude == magnitude
    assert interval.unit is unit
    assert interval.kind is kind


@pytest.mark.parametrize("value", ["1", "5", "daily", "minute", "2_HOURS"])
def test_ambiguous_or_unsupported_intervals_reject(value):
    with pytest.raises(ValidationError):
        MarketBarRecord.model_validate(record_values(interval=value))


def test_supported_provider_aliases_are_explicit():
    values = record_values(
        timestamp="2026-01-15T09:30:00-05:00",
        timestamp_meaning="START",
        bar_start=None,
        bar_end=None,
        Open="10.10",
        High="10.30",
        Low="10.00",
        Close="10.25",
        Volume="1000",
    )
    for name in ("open", "high", "low", "close", "volume"):
        values.pop(name)
    record = MarketBarRecord.model_validate(values)
    assert record.provider_timestamp == "2026-01-15T09:30:00-05:00"
    assert record.timestamp_meaning is BarTimestampMeaning.START
    assert record.open == "10.10"
    assert record.volume == "1000"


def test_conflicting_aliases_reject():
    with pytest.raises(ValidationError):
        MarketBarRecord.model_validate(record_values(Open="99"))


def test_offset_timestamp_normalizes_to_utc():
    parsed = parse_bar_timestamp(
        "2026-01-15T09:30:00-05:00",
        session_date=None,
        timezone_name=None,
        field="bar_start",
    )
    assert parsed.timestamp == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert parsed.timezone_label == "EMBEDDED_OFFSET"


def test_time_only_requires_session_date_and_timezone():
    with pytest.raises(BarParseError, match="session date"):
        parse_bar_timestamp("09:30:00", session_date=None, timezone_name="-05:00", field="bar_start")
    with pytest.raises(BarParseError, match="timezone"):
        parse_bar_timestamp("09:30:00", session_date=date(2026, 1, 15), timezone_name=None, field="bar_start")
    parsed = parse_bar_timestamp(
        "09:30:00",
        session_date=date(2026, 1, 15),
        timezone_name="-05:00",
        field="bar_start",
    )
    assert parsed.timestamp == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert parsed.time_only is True


def test_naive_timestamp_never_silently_becomes_utc():
    with pytest.raises(BarParseError, match="timezone"):
        parse_bar_timestamp(
            "2026-01-15T09:30:00", session_date=None, timezone_name=None, field="bar_start"
        )


def test_dst_nonexistent_and_ambiguous_local_times_reject():
    try:
        ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        pytest.skip("runtime has no IANA timezone database; explicit rejection is tested separately")
    with pytest.raises(BarParseError, match="nonexistent"):
        parse_bar_timestamp(
            "2026-03-08T02:30:00",
            session_date=None,
            timezone_name="America/New_York",
            field="bar_start",
        )
    with pytest.raises(BarParseError, match="ambiguous"):
        parse_bar_timestamp(
            "2026-11-01T01:30:00",
            session_date=None,
            timezone_name="America/New_York",
            field="bar_start",
        )


def test_fixed_interval_derives_exclusive_end_from_start_label():
    record = MarketBarRecord.model_validate(
        record_values(
            bar_start=None,
            bar_end=None,
            provider_timestamp="2026-01-15T09:30:00-05:00",
            timestamp_meaning="START",
        )
    )
    boundaries = resolve_bar_boundaries(record)
    assert boundaries.start == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert boundaries.end == datetime(2026, 1, 15, 14, 31, tzinfo=UTC)
    assert boundaries.end_exclusive is True


def test_fixed_interval_derives_start_from_end_label():
    record = MarketBarRecord.model_validate(
        record_values(
            bar_start=None,
            bar_end=None,
            provider_timestamp="2026-01-15T09:31:00-05:00",
            timestamp_meaning="END",
        )
    )
    boundaries = resolve_bar_boundaries(record)
    assert boundaries.start == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("interval", "bar_end"),
    [
        ("15_MINUTES", datetime(2026, 1, 15, 14, 45, tzinfo=UTC)),
        ("1_HOUR", datetime(2026, 1, 15, 15, 30, tzinfo=UTC)),
    ],
)
def test_required_fixed_intervals_derive_exact_exclusive_end(interval, bar_end):
    record = MarketBarRecord.model_validate(
        record_values(
            interval=interval,
            bar_start=None,
            bar_end=None,
            provider_timestamp="2026-01-15T09:30:00-05:00",
            timestamp_meaning="START",
        )
    )
    assert resolve_bar_boundaries(record).end == bar_end


def test_explicit_fixed_boundaries_must_match_interval_duration():
    with pytest.raises(BarParseError, match="duration"):
        resolve_bar_boundaries(
            MarketBarRecord.model_validate(record_values(interval="15_MINUTES"))
        )


def test_unknown_timestamp_meaning_and_invalid_boundary_reject():
    with pytest.raises(BarParseError, match="meaning"):
        resolve_bar_boundaries(
            MarketBarRecord.model_validate(
                record_values(
                    bar_start=None,
                    bar_end=None,
                    provider_timestamp="2026-01-15T09:30:00-05:00",
                    timestamp_meaning="UNKNOWN",
                )
            )
        )
    with pytest.raises(BarParseError, match="after"):
        resolve_bar_boundaries(
            MarketBarRecord.model_validate(
                record_values(bar_end="2026-01-15T09:29:00-05:00")
            )
        )


def test_daily_bar_is_session_based_and_requires_explicit_boundaries():
    record = MarketBarRecord.model_validate(
        record_values(
            interval="1_DAY",
            bar_start="2026-01-15T09:30:00-05:00",
            bar_end="2026-01-15T16:00:00-05:00",
        )
    )
    boundaries = resolve_bar_boundaries(record)
    assert boundaries.end - boundaries.start != pytest.approx(24 * 60 * 60)
    with pytest.raises(BarParseError, match="explicit"):
        resolve_bar_boundaries(
            MarketBarRecord.model_validate(
                record_values(
                    interval="1_DAY",
                    bar_start=None,
                    bar_end=None,
                    provider_timestamp="2026-01-15",
                    timestamp_meaning="LABEL",
                )
            )
        )


def test_raw_identity_hash_is_stable():
    first = record_values(provider_metadata={"b": 2, "a": 1})
    second = record_values(provider_metadata={"a": 1, "b": 2})
    assert canonical_hash(first) == canonical_hash(second)
