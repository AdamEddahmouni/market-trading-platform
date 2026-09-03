import json
from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.contracts import (
    AssetClass,
    DataFreshness,
    EventType,
    IngestionMethod,
    MarketSession,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
    TradePayload,
)
from squeeze_core.serialization import (
    canonical_hash,
    deserialize_observation,
    serialize_observation,
)


def observation() -> Observation:
    timestamp = datetime(2026, 1, 2, 14, 30, 0, 123000, tzinfo=UTC)
    return Observation(
        schema_version="1.0.0",
        observation_id="serialization-test",
        event_type=EventType.TRADE,
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        source="synthetic-fixture",
        source_record_id="trade-serialization",
        source_timestamp=timestamp,
        received_timestamp=timestamp,
        effective_timestamp=timestamp,
        market_session=MarketSession.REGULAR,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.SYNTHETIC,
        quality=Quality(state=QualityState.KNOWN_VALUE),
        payload_type=PayloadType.TRADE,
        payload=TradePayload(price=Decimal("10.2500"), size=0),
        provenance=Provenance(
            provider="synthetic-fixture",
            ingestion_method=IngestionMethod.LOADED_FIXTURE,
            origin_kind=ObservationKind.SYNTHETIC,
            normalized=False,
        ),
        currency="USD",
        notes=None,
    )


def test_serialization_is_byte_identical_and_key_sorted() -> None:
    first = serialize_observation(observation())
    second = serialize_observation(observation())
    assert first == second
    assert first.startswith(b'{"asset_class"')


def test_serialization_uses_stable_utc_and_decimal_formats() -> None:
    serialized = serialize_observation(observation()).decode("utf-8")
    assert '"source_timestamp":"2026-01-02T14:30:00.123000Z"' in serialized
    assert '"price":"10.25"' in serialized


def test_contractually_meaningful_nulls_are_explicit() -> None:
    decoded = json.loads(serialize_observation(observation()))
    assert "notes" in decoded
    assert decoded["notes"] is None
    assert decoded["payload"]["exchange"] is None


def test_round_trip_preserves_observation_meaning() -> None:
    original = observation()
    restored = deserialize_observation(serialize_observation(original))
    assert restored == original.model_copy(
        update={"payload": original.payload.model_copy(update={"price": Decimal("10.25")})}
    )


def test_canonical_hash_is_stable_and_content_sensitive() -> None:
    original = observation()
    assert canonical_hash(original) == canonical_hash(original)
    changed = original.model_copy(update={"notes": "changed"})
    assert canonical_hash(original) != canonical_hash(changed)


def test_serialized_output_uses_no_environment_path() -> None:
    serialized = serialize_observation(observation())
    assert b"short-squeeze-project" not in serialized
    assert b"Users\\" not in serialized

