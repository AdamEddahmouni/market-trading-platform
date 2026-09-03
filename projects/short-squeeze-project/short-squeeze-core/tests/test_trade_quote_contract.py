from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.contracts import (
    AssetClass,
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
    QuotePayload,
    TradePayload,
)
from squeeze_core.serialization import canonical_json_bytes


def _quote_observation(payload: QuotePayload) -> Observation:
    timestamp = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    return Observation(
        schema_version="1.0.0",
        event_type=EventType.QUOTE,
        symbol="TESTA",
        asset_class=AssetClass.EQUITY,
        source="fixture",
        source_record_id="crossed-quote",
        source_timestamp=timestamp,
        received_timestamp=timestamp,
        effective_timestamp=timestamp,
        market_session=MarketSession.REGULAR,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.SYNTHETIC,
        quality=Quality(
            state=QualityState.KNOWN_VALUE,
            evaluated_at=timestamp,
            completeness=Completeness.COMPLETE,
        ),
        payload_type=PayloadType.QUOTE,
        payload=payload,
        provenance=Provenance(
            provider="fixture",
            ingestion_method=IngestionMethod.LOADED_FIXTURE,
            origin_kind=ObservationKind.SYNTHETIC,
            normalized=True,
            normalization_version="phase1i-test",
            entitlement_state=EntitlementState.NOT_APPLICABLE,
        ),
    )


def test_trade_size_can_be_missing_without_becoming_zero():
    missing = TradePayload(price=Decimal("10.25"))
    zero = TradePayload(price=Decimal("10.25"), size=0)
    assert missing.size is None
    assert zero.size == 0
    assert canonical_json_bytes(missing) != canonical_json_bytes(zero)


@pytest.mark.parametrize("size", [-1, Decimal("1.5")])
def test_trade_size_still_rejects_negative_and_fractional_values(size):
    with pytest.raises(ValidationError):
        TradePayload(price=Decimal("10.25"), size=size)


def test_crossed_quote_is_objective_structure_not_forced_invalid_quality():
    observation = _quote_observation(
        QuotePayload(
            bid_price=Decimal("10.02"),
            bid_size=100,
            ask_price=Decimal("10.01"),
            ask_size=100,
        )
    )
    assert observation.payload.is_crossed is True
    assert observation.quality.state is QualityState.KNOWN_VALUE


def test_existing_trade_serialization_with_integer_size_is_unchanged():
    payload = TradePayload(
        price=Decimal("10.2500"), size=100, exchange="XTEST", conditions=("REGULAR",)
    )
    assert canonical_json_bytes(payload) == (
        b'{"conditions":["REGULAR"],"exchange":"XTEST","price":"10.25","size":100}'
    )
