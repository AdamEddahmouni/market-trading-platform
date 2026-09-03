from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from squeeze_core.contracts import (
    AssetClass,
    BarPayload,
    Completeness,
    DataFreshness,
    EntitlementState,
    EventType,
    IngestionMethod,
    MarketSession,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
)
from squeeze_core.serialization import canonical_json_bytes
from squeeze_core.validation.outcome_amendment import (
    BIYA_EARLIEST_BOUNDARY,
    BIYA_LATEST_BOUNDARY,
    OutcomeEvaluationWindow,
    OutcomeMissingDataState,
    OutcomeReferencePolicy,
    build_boundary_outcome,
)
from squeeze_core.validation.outcome_normalization import HistoricalMarketDataset


RETRIEVED = datetime(2026, 7, 21, 21, 0, tzinfo=UTC)


def bar(
    start: datetime,
    close: str,
    *,
    high: str | None = None,
    low: str | None = None,
    volume: int | None = 100,
    session: MarketSession = MarketSession.REGULAR,
    status: str = "COMPLETED",
    adjustment: str = "PROVIDER_ADJUSTED",
) -> Observation:
    close_value = Decimal(close)
    high_value = Decimal(high or close)
    low_value = Decimal(low or close)
    record_id = f"BIYA-{start.isoformat()}-{close}"
    return Observation(
        schema_version="1.0.0",
        event_type=EventType.BAR,
        symbol="BIYA",
        asset_class=AssetClass.EQUITY,
        source="offline-market-bars:test",
        source_record_id=record_id,
        source_timestamp=RETRIEVED,
        received_timestamp=RETRIEVED,
        effective_timestamp=RETRIEVED,
        market_session=session,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.MARKET_OBSERVED,
        quality=Quality(state=QualityState.KNOWN_VALUE),
        payload_type=PayloadType.BAR,
        payload=BarPayload(
            timeframe="1_MINUTE",
            open=close_value,
            high=high_value,
            low=low_value,
            close=close_value,
            volume=volume,
        ),
        provenance=Provenance(
            provider="test",
            ingestion_method=IngestionMethod.DOWNLOADED,
            origin_kind=ObservationKind.MARKET_OBSERVED,
            normalized=True,
            normalization_version="market-bar-v1",
            completeness=(Completeness.PARTIAL if status == "PARTIAL" else Completeness.COMPLETE),
            entitlement_state=EntitlementState.NOT_APPLICABLE,
            provider_metadata={
                "bar_start": start,
                "bar_end": start + timedelta(minutes=1),
                "interval": "1_MINUTE",
                "session": session.value,
                "status": status,
                "provider_metadata": {"adjustment_policy": adjustment},
            },
        ),
    )


def dataset(observations: tuple[Observation, ...], adjustment: str = "PROVIDER_ADJUSTED"):
    return HistoricalMarketDataset(
        acquisition_id="acq-test",
        raw_sha256="sha256:" + "a" * 64,
        provider="test",
        adjustment_policy=adjustment,
        observations=observations,
        deterministic_id="dataset-test",
    )


def minute_series(start: datetime, count: int, first: Decimal = Decimal("4")) -> tuple[Observation, ...]:
    return tuple(
        bar(
            start + timedelta(minutes=index),
            str(first + Decimal(index) / Decimal("100")),
            high=str(first + Decimal(index) / Decimal("100") + Decimal("0.05")),
            low=str(first + Decimal(index) / Decimal("100") - Decimal("0.03")),
        )
        for index in range(count)
    )


def test_both_boundaries_use_first_bar_start_at_or_after_boundary() -> None:
    observations = (
        bar(datetime(2026, 7, 17, 14, 23, tzinfo=UTC), "4.00"),
        bar(datetime(2026, 7, 17, 14, 24, tzinfo=UTC), "4.20"),
        bar(datetime(2026, 7, 17, 16, 54, tzinfo=UTC), "4.80"),
        bar(datetime(2026, 7, 17, 16, 55, tzinfo=UTC), "5.00"),
    )
    earliest = build_boundary_outcome(BIYA_EARLIEST_BOUNDARY, dataset(observations))
    latest = build_boundary_outcome(BIYA_LATEST_BOUNDARY, dataset(observations))
    assert earliest.reference.policy is OutcomeReferencePolicy.FIRST_ELIGIBLE_BAR_CLOSE
    assert earliest.reference.price == Decimal("4.20")
    assert earliest.reference.bar_start == datetime(2026, 7, 17, 14, 24, tzinfo=UTC)
    assert latest.reference.price == Decimal("5.00")
    assert latest.reference.bar_start == datetime(2026, 7, 17, 16, 55, tzinfo=UTC)


def test_emits_every_required_window_without_favorable_selection() -> None:
    result = build_boundary_outcome(
        BIYA_EARLIEST_BOUNDARY,
        dataset(minute_series(datetime(2026, 7, 17, 14, 24, tzinfo=UTC), 61)),
    )
    assert {item.window for item in result.windows} == set(OutcomeEvaluationWindow)


def test_fifteen_minute_window_computes_extrema_returns_timing_and_volume() -> None:
    result = build_boundary_outcome(
        BIYA_EARLIEST_BOUNDARY,
        dataset(minute_series(datetime(2026, 7, 17, 14, 24, tzinfo=UTC), 16)),
    )
    window = next(item for item in result.windows if item.window is OutcomeEvaluationWindow.MINUTES_15)
    assert window.maximum_observed_price == Decimal("4.19")
    assert window.minimum_observed_price == Decimal("3.97")
    assert window.maximum_observed_return_percent == Decimal("4.75")
    assert window.maximum_adverse_move_percent == Decimal("-0.75")
    assert window.time_to_maximum_seconds == 842
    assert window.time_to_minimum_seconds == 2
    assert window.volume == 1500


@pytest.mark.parametrize(
    "prices,expected",
    [
        (("4", "5"), Decimal("25")),
        (("4", "3"), Decimal("0")),
        (("4", "4"), Decimal("0")),
    ],
)
def test_positive_negative_and_flat_movement(prices: tuple[str, str], expected: Decimal) -> None:
    start = datetime(2026, 7, 17, 14, 24, tzinfo=UTC)
    result = build_boundary_outcome(
        BIYA_EARLIEST_BOUNDARY,
        dataset((bar(start, prices[0]), bar(start + timedelta(minutes=1), prices[1]))),
    )
    maximum = next(item for item in result.windows if item.window is OutcomeEvaluationWindow.DATASET_END)
    assert maximum.maximum_observed_return_percent == expected


def test_missing_reference_and_incomplete_window_are_explicit() -> None:
    missing = build_boundary_outcome(BIYA_EARLIEST_BOUNDARY, dataset(()))
    assert missing.reference.price is None
    assert all(item.missing_data_state is OutcomeMissingDataState.UNAVAILABLE for item in missing.windows)

    start = datetime(2026, 7, 17, 14, 24, tzinfo=UTC)
    incomplete = build_boundary_outcome(
        BIYA_EARLIEST_BOUNDARY,
        dataset((bar(start, "4"),)),
    )
    fifteen = next(item for item in incomplete.windows if item.window is OutcomeEvaluationWindow.MINUTES_15)
    assert fifteen.missing_data_state is OutcomeMissingDataState.PARTIAL


def test_extended_hours_and_partial_bar_limitations_are_preserved() -> None:
    start = datetime(2026, 7, 17, 14, 24, tzinfo=UTC)
    result = build_boundary_outcome(
        BIYA_EARLIEST_BOUNDARY,
        dataset(
            (
                bar(start, "4"),
                bar(
                    start + timedelta(minutes=1),
                    "5",
                    high="6",
                    session=MarketSession.AFTER_HOURS,
                    status="PARTIAL",
                ),
            )
        ),
    )
    maximum = next(item for item in result.windows if item.window is OutcomeEvaluationWindow.DATASET_END)
    assert maximum.session_coverage == ("AFTER_HOURS", "REGULAR")
    assert "partial bar extrema included with explicit limitation" in maximum.limitations


def test_mixed_adjustment_status_is_rejected() -> None:
    start = datetime(2026, 7, 17, 14, 24, tzinfo=UTC)
    with pytest.raises(ValueError, match="adjustment"):
        build_boundary_outcome(
            BIYA_EARLIEST_BOUNDARY,
            dataset(
                (
                    bar(start, "4", adjustment="PROVIDER_ADJUSTED"),
                    bar(start + timedelta(minutes=1), "5", adjustment="UNADJUSTED"),
                )
            ),
        )


def test_output_is_order_invariant_and_has_no_trading_fields() -> None:
    observations = minute_series(datetime(2026, 7, 17, 14, 24, tzinfo=UTC), 20)
    first = build_boundary_outcome(BIYA_EARLIEST_BOUNDARY, dataset(observations))
    second = build_boundary_outcome(BIYA_EARLIEST_BOUNDARY, dataset(tuple(reversed(observations))))
    assert first == second
    rendered = canonical_json_bytes(first).decode("utf-8").lower()
    for forbidden in ("profit", "p&l", "entry", "exit", "fill", "position", "recommend", "buy", "sell"):
        assert forbidden not in rendered
