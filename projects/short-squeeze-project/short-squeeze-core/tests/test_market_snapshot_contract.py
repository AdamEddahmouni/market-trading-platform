from datetime import UTC, date, datetime
from decimal import Decimal

from squeeze_core.contracts import (
    AssetClass,
    DataFreshness,
    EarningsSession,
    EntitlementState,
    EventType,
    IngestionMethod,
    MarketSession,
    MarketSnapshotPayload,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
)
from squeeze_core.serialization import deserialize_observation, serialize_observation


NOW = datetime(2026, 1, 15, 15, 0, tzinfo=UTC)


def snapshot_observation() -> Observation:
    return Observation(
        schema_version="1.0.0",
        event_type=EventType.MARKET_SNAPSHOT,
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        source="representative-screener",
        source_record_id="snapshot-001",
        source_timestamp=NOW,
        received_timestamp=NOW,
        effective_timestamp=NOW,
        market_session=MarketSession.REGULAR,
        data_freshness=DataFreshness.UNKNOWN,
        observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=Quality(state=QualityState.KNOWN_VALUE),
        payload_type=PayloadType.MARKET_SNAPSHOT,
        payload=MarketSnapshotPayload(
            last_price=Decimal("5.25"),
            previous_close=Decimal("4.75"),
            change_percent=Decimal("10.526315789"),
            volume=125000,
            average_volume=25000,
            relative_volume=Decimal("5"),
            float_shares=8000000,
            shares_outstanding=12000000,
            short_float_percent=Decimal("12.5"),
            short_ratio_days=Decimal("2.75"),
            market_cap=63000000,
            sector="Synthetic Sector",
            industry="Synthetic Industry",
            country="Synthetic Country",
            exchange="XTEST",
            earnings_date=date(2026, 2, 2),
            earnings_session=EarningsSession.BEFORE_MARKET,
            snapshot_scope="candidate-universe descriptive snapshot",
        ),
        provenance=Provenance(
            provider="representative-screener",
            ingestion_method=IngestionMethod.LOADED_FIXTURE,
            origin_kind=ObservationKind.PROVIDER_PUBLISHED,
            normalized=True,
            normalization_version="finviz-normalization-v1",
            entitlement_state=EntitlementState.UNKNOWN,
        ),
        normalization_version="finviz-normalization-v1",
    )


def test_market_snapshot_is_additive_provider_neutral_contract() -> None:
    observation = snapshot_observation()

    assert observation.event_type is EventType.MARKET_SNAPSHOT
    assert observation.payload_type is PayloadType.MARKET_SNAPSHOT
    assert isinstance(observation.payload, MarketSnapshotPayload)
    assert observation.event_type is not EventType.BAR
    assert observation.payload.short_float_percent == Decimal("12.5")
    assert "short_interest_percent" not in MarketSnapshotPayload.model_fields


def test_market_snapshot_round_trip_is_canonical_and_schema_stays_1_0_0() -> None:
    original = snapshot_observation()
    serialized = serialize_observation(original)
    restored = deserialize_observation(serialized)

    assert restored == original
    assert restored.schema_version == "1.0.0"
    assert serialize_observation(restored) == serialized


def test_market_snapshot_nullable_values_preserve_missing_and_explicit_zero() -> None:
    payload = MarketSnapshotPayload(volume=0, float_shares=None, short_float_percent=Decimal("0"))

    assert payload.volume == 0
    assert payload.float_shares is None
    assert payload.short_float_percent == 0
