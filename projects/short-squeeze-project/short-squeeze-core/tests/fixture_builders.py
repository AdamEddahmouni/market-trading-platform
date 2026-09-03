from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from squeeze_core.contracts import (
    AssetClass,
    BarPayload,
    BorrowAvailabilityPayload,
    BorrowFeePayload,
    Completeness,
    CorporateActionPayload,
    DataFreshness,
    DerivedIndicatorPayload,
    EntitlementState,
    EventType,
    IngestionMethod,
    MarketSession,
    NewsItemPayload,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    PublishedShortInterestPayload,
    Quality,
    QualityState,
    QuotePayload,
    SecFilingPayload,
    SourceHealth,
    SourceStatusPayload,
    TradePayload,
    TradingHaltPayload,
)
from squeeze_core.serialization import serialize_jsonl


BASE = datetime(2026, 1, 2, 14, 30, tzinfo=UTC)


def _observation(
    record_id: str,
    offset: int,
    event_type: EventType,
    payload_type: PayloadType,
    payload: object,
    *,
    quality: Quality | None = None,
    symbol: str | None = "TESTA",
    source: str = "synthetic-fixture",
    kind: ObservationKind = ObservationKind.SYNTHETIC,
    freshness: DataFreshness = DataFreshness.HISTORICAL,
    ingestion_method: IngestionMethod = IngestionMethod.LOADED_FIXTURE,
    completeness: Completeness = Completeness.COMPLETE,
    upstream_ids: tuple[str, ...] = (),
    **extra: Any,
) -> Observation:
    timestamp = BASE + timedelta(seconds=offset)
    return Observation.model_validate(
        {
            "schema_version": "1.0.0",
            "event_type": event_type,
            "symbol": symbol,
            "asset_class": AssetClass.EQUITY if symbol else AssetClass.UNKNOWN,
            "source": source,
            "source_record_id": record_id,
            "source_timestamp": timestamp,
            "received_timestamp": timestamp + timedelta(milliseconds=25),
            "effective_timestamp": timestamp,
            "market_session": MarketSession.REGULAR,
            "data_freshness": freshness,
            "observation_kind": kind,
            "quality": quality or Quality(state=QualityState.KNOWN_VALUE),
            "payload_type": payload_type,
            "payload": payload,
            "provenance": Provenance(
                provider=source,
                ingestion_method=ingestion_method,
                origin_kind=kind,
                normalized=True,
                normalization_version="fixture-v1",
                upstream_observation_ids=upstream_ids,
                completeness=completeness,
                entitlement_state=EntitlementState.NOT_APPLICABLE,
                source_timezone="America/New_York",
                source_timestamp_representation=timestamp.astimezone(
                    timezone(timedelta(hours=-5))
                ).isoformat(),
                provider_metadata={"fixture_family": "phase-1a"},
            ),
            "sequence_number": offset,
            "exchange": "XTEST" if symbol else None,
            "currency": "USD" if symbol else None,
            "timezone": "America/New_York",
            "normalization_version": "fixture-v1",
            **extra,
        }
    )


def minimal_session() -> list[Observation]:
    items = [
        _observation(
            "minimal-01-source",
            1,
            EventType.SOURCE_STATUS,
            PayloadType.SOURCE_STATUS,
            SourceStatusPayload(status="HEALTHY", latency_ms=25, last_successful_event_at=BASE),
            symbol=None,
        ),
        _observation(
            "minimal-02-quote",
            2,
            EventType.QUOTE,
            PayloadType.QUOTE,
            QuotePayload(
                bid_price=Decimal("10.00"), bid_size=500, ask_price=Decimal("10.02"), ask_size=400
            ),
        ),
        _observation(
            "minimal-03-trade",
            3,
            EventType.TRADE,
            PayloadType.TRADE,
            TradePayload(price=Decimal("10.01"), size=100, exchange="XTEST"),
        ),
        _observation(
            "minimal-04-bar",
            4,
            EventType.BAR,
            PayloadType.BAR,
            BarPayload(
                timeframe="1m",
                open=Decimal("10.00"),
                high=Decimal("10.05"),
                low=Decimal("9.99"),
                close=Decimal("10.01"),
                volume=10000,
                trade_count=80,
                vwap=Decimal("10.0125"),
            ),
        ),
        _observation(
            "minimal-05-short",
            5,
            EventType.PUBLISHED_SHORT_INTEREST,
            PayloadType.PUBLISHED_SHORT_INTEREST,
            PublishedShortInterestPayload(
                short_shares=250000,
                float_shares=1000000,
                short_float_percent=Decimal("25"),
                settlement_date=date(2025, 12, 31),
                publication_date=date(2026, 1, 2),
                days_to_cover=Decimal("2.5"),
            ),
            source="synthetic-publisher",
            kind=ObservationKind.PROVIDER_PUBLISHED,
            ingestion_method=IngestionMethod.DOWNLOADED,
            freshness=DataFreshness.DELAYED,
        ),
        _observation(
            "minimal-06-availability",
            6,
            EventType.BORROW_AVAILABILITY,
            PayloadType.BORROW_AVAILABILITY,
            BorrowAvailabilityPayload(available_shares=50000, lender_count=3, hard_to_borrow=True),
        ),
        _observation(
            "minimal-07-fee",
            7,
            EventType.BORROW_FEE,
            PayloadType.BORROW_FEE,
            BorrowFeePayload(annualized_fee_percent=Decimal("12.5"), fee_type="indicative"),
        ),
        _observation(
            "minimal-08-news",
            8,
            EventType.NEWS_ITEM,
            PayloadType.NEWS_ITEM,
            NewsItemPayload(
                headline="Synthetic TESTA issuer update",
                summary="Offline fixture content.",
                publisher="Synthetic Wire",
                published_at=BASE + timedelta(seconds=8),
                associated_symbols=("TESTA",),
            ),
        ),
        _observation(
            "minimal-09-filing",
            9,
            EventType.SEC_FILING,
            PayloadType.SEC_FILING,
            SecFilingPayload(
                form_type="8-K",
                accession_number="0000000000-26-000001",
                filed_at=BASE + timedelta(seconds=9),
                period_of_report=date(2026, 1, 2),
                primary_document="synthetic-8k.htm",
                issuer_cik="0000000000",
            ),
        ),
        _observation(
            "minimal-10-halt",
            10,
            EventType.TRADING_HALT,
            PayloadType.TRADING_HALT,
            TradingHaltPayload(
                halt_status="HALTED",
                halt_reason="SYNTHETIC_TEST",
                halt_time=BASE + timedelta(seconds=10),
            ),
        ),
        _observation(
            "minimal-11-resume",
            11,
            EventType.TRADING_HALT,
            PayloadType.TRADING_HALT,
            TradingHaltPayload(
                halt_status="RESUMED",
                halt_reason="SYNTHETIC_TEST",
                halt_time=BASE + timedelta(seconds=10),
                resume_time=BASE + timedelta(seconds=11),
            ),
        ),
        _observation(
            "minimal-12-action",
            12,
            EventType.CORPORATE_ACTION,
            PayloadType.CORPORATE_ACTION,
            CorporateActionPayload(
                action_type="SPLIT_NOTICE",
                effective_date=date(2026, 1, 5),
                description="Synthetic illustrative notice",
            ),
        ),
    ]
    parent_ids = tuple(item.observation_id for item in items[1:4])
    items.append(
        _observation(
            "minimal-13-derived",
            13,
            EventType.DERIVED_INDICATOR,
            PayloadType.DERIVED_INDICATOR,
            DerivedIndicatorPayload(
                calculation_name="future_ttm_placeholder",
                calculation_version="not-implemented",
                input_observation_ids=parent_ids,
                parameters={"implemented": False},
                result=None,
            ),
            kind=ObservationKind.DERIVED,
            freshness=DataFreshness.DERIVED,
            ingestion_method=IngestionMethod.CALCULATED,
            upstream_ids=parent_ids,
            parent_observation_ids=parent_ids,
            notes="Representation only; no indicator calculation was performed.",
        )
    )
    return items


def quality_edge_cases() -> list[Observation]:
    stale = Quality(
        state=QualityState.STALE,
        reasons=("quote age exceeds fixture threshold",),
        evaluated_at=BASE,
        age_ms=120000,
        source_health=SourceHealth.DEGRADED,
    )
    delayed = Quality(
        state=QualityState.DELAYED,
        reasons=("published on scheduled reporting delay",),
        expected_delay_ms=1_209_600_000,
    )
    return [
        _observation(
            "quality-01-zero-fee",
            1,
            EventType.BORROW_FEE,
            PayloadType.BORROW_FEE,
            BorrowFeePayload(annualized_fee_percent=Decimal("0"), fee_type="indicative"),
        ),
        _observation(
            "quality-02-missing-fee",
            2,
            EventType.BORROW_FEE,
            PayloadType.BORROW_FEE,
            BorrowFeePayload(annualized_fee_percent=None, fee_type="indicative"),
            quality=Quality(state=QualityState.MISSING, reasons=("source omitted fee",)),
        ),
        _observation(
            "quality-03-delayed-short",
            3,
            EventType.PUBLISHED_SHORT_INTEREST,
            PayloadType.PUBLISHED_SHORT_INTEREST,
            PublishedShortInterestPayload(
                short_shares=100000,
                float_shares=1000000,
                short_float_percent=Decimal("10"),
                settlement_date=date(2025, 12, 15),
                publication_date=date(2025, 12, 24),
            ),
            quality=delayed,
            source="synthetic-publisher",
            kind=ObservationKind.PROVIDER_PUBLISHED,
            ingestion_method=IngestionMethod.DOWNLOADED,
            freshness=DataFreshness.DELAYED,
        ),
        _observation(
            "quality-04-stale-quote",
            4,
            EventType.QUOTE,
            PayloadType.QUOTE,
            QuotePayload(bid_price=Decimal("9.99"), bid_size=1, ask_price=Decimal("10.01"), ask_size=1),
            quality=stale,
        ),
        _observation(
            "quality-05-crossed-quote",
            5,
            EventType.QUOTE,
            PayloadType.QUOTE,
            QuotePayload(bid_price=Decimal("10.02"), bid_size=1, ask_price=Decimal("10.01"), ask_size=1),
            quality=Quality(state=QualityState.INVALID, reasons=("bid exceeds ask",)),
        ),
        _observation(
            "quality-06-unassociated-news",
            6,
            EventType.NEWS_ITEM,
            PayloadType.NEWS_ITEM,
            NewsItemPayload(
                headline="Synthetic market-wide notice",
                publisher="Synthetic Wire",
                published_at=BASE + timedelta(seconds=6),
                associated_symbols=(),
            ),
            symbol=None,
        ),
        _observation(
            "quality-07-incomplete-derived",
            7,
            EventType.DERIVED_INDICATOR,
            PayloadType.DERIVED_INDICATOR,
            DerivedIndicatorPayload(
                calculation_name="future_placeholder",
                calculation_version="not-implemented",
                input_observation_ids=("missing-parent",),
                parameters={},
                result=None,
            ),
            quality=Quality(
                state=QualityState.ESTIMATED,
                reasons=("parent observation set is incomplete",),
                completeness=Completeness.PARTIAL,
            ),
            kind=ObservationKind.DERIVED,
            freshness=DataFreshness.DERIVED,
            ingestion_method=IngestionMethod.CALCULATED,
            completeness=Completeness.PARTIAL,
            upstream_ids=("missing-parent",),
            parent_observation_ids=("missing-parent",),
        ),
        _observation(
            "quality-08-conflict-a",
            8,
            EventType.BORROW_FEE,
            PayloadType.BORROW_FEE,
            BorrowFeePayload(annualized_fee_percent=Decimal("5"), fee_type="indicative"),
            quality=Quality(state=QualityState.CONFLICTED, reasons=("conflicts with source B",)),
            source="synthetic-source-a",
            correlation_id="borrow-fee-conflict",
        ),
        _observation(
            "quality-09-conflict-b",
            9,
            EventType.BORROW_FEE,
            PayloadType.BORROW_FEE,
            BorrowFeePayload(annualized_fee_percent=Decimal("7"), fee_type="indicative"),
            quality=Quality(state=QualityState.CONFLICTED, reasons=("conflicts with source A",)),
            source="synthetic-source-b",
            correlation_id="borrow-fee-conflict",
        ),
    ]


def out_of_order_session() -> list[Observation]:
    ordered = [
        _observation(
            f"ooo-{index}",
            index,
            EventType.TRADE,
            PayloadType.TRADE,
            TradePayload(price=Decimal(f"10.0{index}"), size=index * 100),
        )
        for index in (1, 2, 3)
    ]
    return [ordered[2], ordered[0], ordered[1]]


FIXTURES = {
    "minimal_session.jsonl": minimal_session,
    "quality_edge_cases.jsonl": quality_edge_cases,
    "out_of_order_session.jsonl": out_of_order_session,
}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=FIXTURES)
    args = parser.parse_args()
    print(serialize_jsonl(FIXTURES[args.name]()).decode("utf-8"), end="")
