from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.contracts import (
    AssetClass,
    DataFreshness,
    EventType,
    IngestionMethod,
    MarketSession,
    Observation,
    ObservationKind,
    PayloadType,
    PublishedShortInterestPayload,
    Provenance,
    Quality,
    QualityState,
    QuotePayload,
    TradePayload,
)


NOW = datetime(2026, 1, 2, 14, 30, tzinfo=UTC)


def provenance() -> Provenance:
    return Provenance(
        provider="synthetic-fixture",
        ingestion_method=IngestionMethod.LOADED_FIXTURE,
        origin_kind=ObservationKind.SYNTHETIC,
        normalized=True,
        normalization_version="fixture-v1",
    )


def trade_observation(**overrides: object) -> Observation:
    values: dict[str, object] = {
        "schema_version": "1.0.0",
        "event_type": EventType.TRADE,
        "symbol": "TESTA",
        "asset_class": AssetClass.EQUITY,
        "source": "synthetic-fixture",
        "source_record_id": "trade-1",
        "source_timestamp": NOW,
        "received_timestamp": NOW,
        "effective_timestamp": NOW,
        "market_session": MarketSession.REGULAR,
        "data_freshness": DataFreshness.HISTORICAL,
        "observation_kind": ObservationKind.SYNTHETIC,
        "quality": Quality(state=QualityState.KNOWN_VALUE),
        "payload_type": PayloadType.TRADE,
        "payload": TradePayload(price=Decimal("10.2500"), size=100),
        "provenance": provenance(),
    }
    values.update(overrides)
    return Observation.model_validate(values)


def test_observation_normalizes_aware_timestamps_to_utc() -> None:
    eastern = datetime.fromisoformat("2026-01-02T09:30:00-05:00")
    observation = trade_observation(source_timestamp=eastern)
    assert observation.source_timestamp == NOW
    assert observation.source_timestamp.tzinfo is UTC


def test_observation_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        trade_observation(source_timestamp=datetime(2026, 1, 2, 14, 30))


def test_observation_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError):
        trade_observation(schema_version="2.0.0")


def test_payload_must_match_event_and_payload_type() -> None:
    quote = QuotePayload(
        bid_price=Decimal("10.00"), bid_size=10, ask_price=Decimal("10.01"), ask_size=20
    )
    with pytest.raises(ValidationError, match="payload_type.*event_type"):
        trade_observation(payload_type=PayloadType.QUOTE, payload=quote)


def test_price_and_quantity_ranges_are_validated() -> None:
    with pytest.raises(ValidationError):
        TradePayload(price=Decimal("-0.01"), size=1)
    with pytest.raises(ValidationError):
        TradePayload(price=Decimal("1.00"), size=-1)


def test_observation_id_is_content_deterministic_when_omitted() -> None:
    first = trade_observation()
    second = trade_observation()
    changed = trade_observation(source_record_id="trade-2")
    assert first.observation_id == second.observation_id
    assert first.observation_id != changed.observation_id


def test_explicit_observation_id_is_preserved() -> None:
    observation = trade_observation(observation_id="fixture-explicit-id")
    assert observation.observation_id == "fixture-explicit-id"


def test_deterministic_identity_supports_date_only_payload_fields() -> None:
    observation = trade_observation(
        event_type=EventType.PUBLISHED_SHORT_INTEREST,
        payload_type=PayloadType.PUBLISHED_SHORT_INTEREST,
        payload=PublishedShortInterestPayload(
            settlement_date=date(2025, 12, 31),
            publication_date=date(2026, 1, 2),
        ),
    )
    assert observation.observation_id is not None


def test_crossed_quote_preserves_explicit_invalid_quality() -> None:
    quote = QuotePayload(
        bid_price=Decimal("10.02"), bid_size=10, ask_price=Decimal("10.01"), ask_size=20
    )
    common = {
        "event_type": EventType.QUOTE,
        "payload_type": PayloadType.QUOTE,
        "payload": quote,
        "source_record_id": "quote-crossed",
    }
    invalid = trade_observation(
        **common,
        quality=Quality(state=QualityState.INVALID, reasons=["bid exceeds ask"]),
    )
    known = trade_observation(**common)
    assert invalid.quality.state is QualityState.INVALID
    assert known.quality.state is QualityState.KNOWN_VALUE


def test_provenance_is_required() -> None:
    with pytest.raises(ValidationError):
        trade_observation(provenance=None)
