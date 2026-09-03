from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import (
    AssetClass, BarPayload, BorrowAvailabilityPayload, BorrowFeePayload, Completeness,
    CorporateActionPayload, DataFreshness, EntitlementState, EventType, IngestionMethod,
    MarketSession, MarketSnapshotPayload, NewsItemPayload, Observation, ObservationKind,
    PayloadType, Provenance, PublishedShortInterestPayload, Quality, QualityState,
    SecFilingPayload,
)
from squeeze_core.metrics import (
    MetricName, MetricUnit, NormalizedMetricResult, PressureMetricResult,
    ProviderScopeMode,
)


AS_OF = datetime(2026, 7, 17, 14, 23, 58, tzinfo=UTC)


def quality(state: QualityState = QualityState.KNOWN_VALUE, reason: str = "unavailable") -> Quality:
    return Quality(
        state=state,
        reasons=() if state is QualityState.KNOWN_VALUE else (reason,),
        evaluated_at=AS_OF,
        completeness=Completeness.COMPLETE,
    )


def provenance(provider: str, **metadata) -> Provenance:
    return Provenance(
        provider=provider,
        ingestion_method=IngestionMethod.LOADED_FIXTURE,
        origin_kind=ObservationKind.PROVIDER_PUBLISHED,
        normalized=True,
        normalization_version="test-v1",
        entitlement_state=EntitlementState.NOT_APPLICABLE,
        provider_metadata=metadata,
    )


def observation(event_type: EventType, payload, *, provider: str = "provider-a",
                source_time: datetime = AS_OF - timedelta(minutes=1),
                received_time: datetime | None = None, status: str = "ORIGINAL") -> Observation:
    payload_type = {
        EventType.BAR: PayloadType.BAR,
        EventType.MARKET_SNAPSHOT: PayloadType.MARKET_SNAPSHOT,
        EventType.PUBLISHED_SHORT_INTEREST: PayloadType.PUBLISHED_SHORT_INTEREST,
        EventType.BORROW_FEE: PayloadType.BORROW_FEE,
        EventType.BORROW_AVAILABILITY: PayloadType.BORROW_AVAILABILITY,
        EventType.NEWS_ITEM: PayloadType.NEWS_ITEM,
        EventType.SEC_FILING: PayloadType.SEC_FILING,
        EventType.CORPORATE_ACTION: PayloadType.CORPORATE_ACTION,
    }[event_type]
    metadata = {"status": status}
    if event_type is EventType.BAR:
        metadata.update({
            "bar_start": (source_time - timedelta(minutes=1)).isoformat(),
            "bar_end": source_time.isoformat(),
            "interval": "1_MINUTE",
        })
    return Observation(
        schema_version="1.0.0", event_type=event_type, symbol="TESTA",
        asset_class=AssetClass.EQUITY, source=provider,
        source_record_id=f"{event_type.value}-{provider}-{source_time.isoformat()}-{status}",
        source_timestamp=source_time, received_timestamp=received_time or source_time,
        effective_timestamp=source_time, market_session=MarketSession.REGULAR,
        data_freshness=DataFreshness.LIVE, observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=quality(), payload_type=payload_type, payload=payload,
        provenance=provenance(provider, **metadata),
    )


def bar(close: str = "10", *, provider: str = "provider-a", status: str = "COMPLETED",
        source_time: datetime = AS_OF - timedelta(seconds=1)) -> Observation:
    price = Decimal(close)
    return observation(
        EventType.BAR,
        BarPayload(timeframe="1_MINUTE", open=price, high=price, low=price, close=price, volume=100),
        provider=provider, source_time=source_time, status=status,
    )


def snapshot(*, float_shares: int | None = 10_000_000, provider: str = "provider-a") -> Observation:
    return observation(EventType.MARKET_SNAPSHOT, MarketSnapshotPayload(float_shares=float_shares),
                       provider=provider)


def short_interest(*, shares: int | None = 1_000_000, provider: str = "provider-a") -> Observation:
    return observation(
        EventType.PUBLISHED_SHORT_INTEREST,
        PublishedShortInterestPayload(short_shares=shares, settlement_date=date(2026, 6, 30),
                                      publication_date=date(2026, 7, 10)),
        provider=provider,
    )


def borrow_fee(value: str | None = "12", *, provider: str = "provider-a") -> Observation:
    return observation(EventType.BORROW_FEE,
                       BorrowFeePayload(annualized_fee_percent=None if value is None else Decimal(value)),
                       provider=provider)


def borrow_availability(value: int | None = 0, *, provider: str = "provider-a") -> Observation:
    return observation(EventType.BORROW_AVAILABILITY,
                       BorrowAvailabilityPayload(available_shares=value), provider=provider)


def news(*, published_at: datetime | None = None, source_time: datetime | None = None,
         status: str = "ORIGINAL") -> Observation:
    published = AS_OF - timedelta(hours=1) if published_at is None and source_time is None else published_at
    source = source_time or published or (AS_OF - timedelta(minutes=1))
    return observation(EventType.NEWS_ITEM,
                       NewsItemPayload(headline="Objective event", published_at=published,
                                       associated_symbols=("TESTA",)),
                       provider="news-a", source_time=source, status=status)


def sec_filing(*, filed_at: datetime = AS_OF - timedelta(hours=1)) -> Observation:
    return observation(EventType.SEC_FILING,
                       SecFilingPayload(form_type="8-K", accession_number="0001", filed_at=filed_at),
                       provider="sec", source_time=filed_at)


def corporate_action() -> Observation:
    return observation(EventType.CORPORATE_ACTION,
                       CorporateActionPayload(action_type="REVERSE_SPLIT", effective_date=date(2026, 7, 13)),
                       provider="actions")


def normalized_metric(name: MetricName, value: str | None, unit: MetricUnit,
                      *, state: QualityState = QualityState.KNOWN_VALUE,
                      provider: str = "provider-a") -> NormalizedMetricResult:
    return NormalizedMetricResult(
        metric_name=name, metric_version=f"{name.value.lower()}.v1",
        calculation_policy_version="test-policy.v1", symbol="TESTA",
        asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_MINUTE,
        session_scope=(BarSession.REGULAR,), provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        provider=provider, value=None if value is None else Decimal(value), unit=unit,
        quality=quality(state, "insufficient history" if state is QualityState.MISSING else "unavailable"),
    )


def pressure_metric(name: MetricName, value: str | None, unit: MetricUnit,
                    *, state: QualityState = QualityState.KNOWN_VALUE,
                    provider: str = "provider-a") -> PressureMetricResult:
    return PressureMetricResult(
        metric_name=name, metric_version=f"{name.value.lower()}.v1",
        calculation_policy_version="test-policy.v1", symbol="TESTA",
        asset_class=AssetClass.EQUITY, as_of=AS_OF,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER, provider=provider,
        value=None if value is None else Decimal(value), unit=unit,
        quality=quality(state, "insufficient history" if state is QualityState.MISSING else "unavailable"),
    )
