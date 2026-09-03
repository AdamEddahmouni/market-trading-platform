import json
from datetime import UTC, datetime

from squeeze_core.contracts import MarketSession
from squeeze_core.validation.outcome_acquisition import (
    AcquisitionDataType,
    AcquisitionEntitlementState,
    AcquisitionResultState,
    build_acquisition_manifest,
)
from squeeze_core.validation.outcome_normalization import normalize_acquired_market_bars


RETRIEVED = datetime(2026, 7, 21, 21, 0, tzinfo=UTC)


def payload(
    timestamps: list[int] | None = None,
    *,
    interval: str = "1m",
    volumes: list[int | None] | None = None,
    opens: list[float | None] | None = None,
) -> bytes:
    timestamps = timestamps or [1784298240, 1784298300]  # 2026-07-17 10:24/10:25 ET
    size = len(timestamps)
    opens = opens or [4.1 + index / 10 for index in range(size)]
    quote = {
        "open": opens,
        "high": [None if value is None else value + 0.2 for value in opens],
        "low": [None if value is None else value - 0.1 for value in opens],
        "close": [None if value is None else value + 0.1 for value in opens],
        "volume": volumes if volumes is not None else [1000 + index for index in range(size)],
    }
    return json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "symbol": "BIYA",
                            "exchangeName": "NCM",
                            "exchangeTimezoneName": "America/New_York",
                            "dataGranularity": interval,
                            "priceHint": 2,
                        },
                        "timestamp": timestamps,
                        "indicators": {"quote": [quote]},
                    }
                ],
                "error": None,
            }
        },
        separators=(",", ":"),
    ).encode("utf-8")


def manifest(raw: bytes, *, bar_size: str = "1_MINUTE", data_type=AcquisitionDataType.INTRADAY_MARKET_BARS):
    return build_acquisition_manifest(
        symbol="BIYA",
        provider="yahoo-chart",
        data_type=data_type,
        requested_start=datetime(2026, 7, 16, 4, 0, tzinfo=UTC),
        requested_end=RETRIEVED,
        retrieved_at=RETRIEVED,
        request_timezone="America/New_York",
        response_timezone="America/New_York",
        bar_size=bar_size,
        session_scope="REGULAR_AND_EXTENDED",
        adjustment_policy="PROVIDER_ADJUSTED",
        request_parameters={"interval": "1m"},
        result_state=AcquisitionResultState.SUCCESS,
        raw_relative_path="raw/intraday_market_bars/biya.json",
        raw_bytes=raw,
        record_count=2,
        earliest_record_time=datetime.fromtimestamp(1784298240, tz=UTC),
        latest_record_time=datetime.fromtimestamp(1784298300, tz=UTC),
        entitlement_state=AcquisitionEntitlementState.NOT_REQUIRED,
    )


def test_normalizes_one_minute_regular_session_bars_through_phase_1_contract() -> None:
    raw = payload()
    result = normalize_acquired_market_bars(manifest(raw), raw)
    assert len(result.observations) == 2
    first = result.observations[0]
    assert first.payload.timeframe == "1_MINUTE"
    assert first.market_session is MarketSession.REGULAR
    provider_raw = first.provenance.provider_metadata["provider_metadata"]
    assert provider_raw["raw_acquisition_id"] == result.acquisition_id
    assert provider_raw["adjustment_policy"] == "PROVIDER_ADJUSTED"


def test_distinguishes_extended_hours() -> None:
    # 08:00 and 16:30 America/New_York.
    raw = payload([1784289600, 1784320200])
    result = normalize_acquired_market_bars(manifest(raw), raw)
    assert {item.market_session for item in result.observations} == {
        MarketSession.PRE_MARKET,
        MarketSession.AFTER_HOURS,
    }


def test_normalizes_five_minute_fallback_and_daily_bars() -> None:
    five_raw = payload([1784298300, 1784298600], interval="5m")
    five = normalize_acquired_market_bars(manifest(five_raw, bar_size="5_MINUTES"), five_raw)
    assert {item.payload.timeframe for item in five.observations} == {"5_MINUTES"}

    daily_raw = payload([1784250000, 1784336400], interval="1d")
    daily = normalize_acquired_market_bars(
        manifest(daily_raw, bar_size="1_DAY", data_type=AcquisitionDataType.DAILY_MARKET_BARS),
        daily_raw,
    )
    assert {item.payload.timeframe for item in daily.observations} == {"1_DAY"}


def test_missing_and_zero_volume_remain_distinct() -> None:
    raw = payload(volumes=[None, 0])
    result = normalize_acquired_market_bars(manifest(raw), raw)
    assert [item.payload.volume for item in result.observations] == [None, 0]
    codes = {diagnostic.code.value for diagnostic in result.diagnostics}
    assert "BAR_MISSING_VOLUME" in codes
    assert "BAR_ZERO_VOLUME" in codes


def test_missing_timestamp_or_ohlc_is_rejected_not_fabricated() -> None:
    raw = payload(opens=[None, 4.2])
    result = normalize_acquired_market_bars(manifest(raw), raw)
    assert len(result.observations) == 1
    assert result.rejected_record_count == 1


def test_input_order_is_invariant_and_observation_ids_are_stable() -> None:
    ordered = payload([1784298240, 1784298300], opens=[4.1, 4.2])
    reversed_raw = payload(
        [1784298300, 1784298240], opens=[4.2, 4.1], volumes=[1001, 1000]
    )
    first = normalize_acquired_market_bars(manifest(ordered), ordered)
    second = normalize_acquired_market_bars(manifest(reversed_raw), reversed_raw)
    assert [item.observation_id for item in first.observations] == [
        item.observation_id for item in second.observations
    ]
    assert first.deterministic_id == second.deterministic_id


def test_duplicate_and_conflicting_bars_remain_diagnosed() -> None:
    duplicate = payload(
        [1784298240, 1784298240], opens=[4.1, 4.1], volumes=[1000, 1000]
    )
    duplicate_result = normalize_acquired_market_bars(manifest(duplicate), duplicate)
    assert len(duplicate_result.observations) == 1
    assert "BAR_DUPLICATE_RECORD" in {
        item.code.value for item in duplicate_result.diagnostics
    }

    conflict = payload([1784298240, 1784298240], opens=[4.1, 5.1])
    conflict_result = normalize_acquired_market_bars(manifest(conflict), conflict)
    assert len(conflict_result.observations) == 2
    assert all(item.quality.state.value == "CONFLICTED" for item in conflict_result.observations)
