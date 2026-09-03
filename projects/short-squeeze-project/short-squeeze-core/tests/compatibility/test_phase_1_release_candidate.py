"""Phase 1 release-candidate compatibility checks.

Two families of guarantees are proven here:

1. Canonical compatibility -- schema `1.0.0` is stable, old serialized observations still
   validate, hashes are unchanged across repeated serialization, and the Phase 1I relaxations
   (nullable trade size distinct from zero; crossed quotes representable without forcing
   `INVALID`) hold and remain distinct from their neighbours.
2. Cross-domain point-in-time consistency -- every domain enforces the same availability gates:
   a record received after `as_of` is excluded, an effective time after `as_of` is excluded,
   the publication-gated domains additionally exclude records published after `as_of`, and event
   time alone never creates eligibility.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from squeeze_core.contracts import (
    AssetClass,
    BarPayload,
    BorrowAvailabilityPayload,
    BorrowFeePayload,
    DataFreshness,
    EventType,
    IngestionMethod,
    MarketSession,
    MarketSnapshotPayload,
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
    TradePayload,
    TradingHaltPayload,
)
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence
from squeeze_core.replay import load_fixture
from squeeze_core.serialization import (
    canonical_hash,
    deserialize_observation,
    serialize_observation,
)
from pathlib import Path

ROOT = Path(__file__).parents[1] / "fixtures"
AS_OF = datetime(2026, 1, 31, 15, 0, tzinfo=UTC)


def _payload_and_type(event_type: EventType):
    if event_type is EventType.MARKET_SNAPSHOT:
        return MarketSnapshotPayload(last_price=Decimal("10.00")), PayloadType.MARKET_SNAPSHOT
    if event_type is EventType.BORROW_FEE:
        return BorrowFeePayload(annualized_fee_percent=Decimal("1.5")), PayloadType.BORROW_FEE
    if event_type is EventType.BORROW_AVAILABILITY:
        return BorrowAvailabilityPayload(available_shares=1000), PayloadType.BORROW_AVAILABILITY
    if event_type is EventType.PUBLISHED_SHORT_INTEREST:
        return (
            PublishedShortInterestPayload(short_shares=1000, settlement_date=date(2026, 1, 15)),
            PayloadType.PUBLISHED_SHORT_INTEREST,
        )
    if event_type is EventType.SEC_FILING:
        return (
            SecFilingPayload(
                form_type="8-K",
                accession_number="0000000000-00-000000",
                filed_at=AS_OF - timedelta(days=2),
            ),
            PayloadType.SEC_FILING,
        )
    if event_type is EventType.TRADING_HALT:
        return TradingHaltPayload(halt_status="HALT_ACTIVE"), PayloadType.TRADING_HALT
    if event_type is EventType.NEWS_ITEM:
        return (
            NewsItemPayload(headline="Objective headline", associated_symbols=("TESTA",)),
            PayloadType.NEWS_ITEM,
        )
    if event_type is EventType.BAR:
        return (
            BarPayload(
                timeframe="1m",
                open=Decimal("10"),
                high=Decimal("11"),
                low=Decimal("9"),
                close=Decimal("10"),
            ),
            PayloadType.BAR,
        )
    if event_type is EventType.TRADE:
        return TradePayload(price=Decimal("10.00")), PayloadType.TRADE
    if event_type is EventType.QUOTE:
        return (
            QuotePayload(bid_price=Decimal("10.00"), ask_price=Decimal("10.05")),
            PayloadType.QUOTE,
        )
    raise AssertionError(event_type)


def _observation(
    event_type: EventType,
    *,
    source_timestamp: datetime,
    received_timestamp: datetime,
    effective_timestamp: datetime,
    record_id: str = "rc-audit-1",
    provider_metadata: dict | None = None,
) -> Observation:
    payload, payload_type = _payload_and_type(event_type)
    return Observation.model_validate(
        {
            "schema_version": "1.0.0",
            "event_type": event_type,
            "symbol": None if event_type is EventType.NEWS_ITEM else "TESTA",
            "asset_class": AssetClass.EQUITY,
            "source": "rc-audit-source",
            "source_record_id": record_id,
            "source_timestamp": source_timestamp,
            "received_timestamp": received_timestamp,
            "effective_timestamp": effective_timestamp,
            "market_session": MarketSession.REGULAR,
            "data_freshness": DataFreshness.HISTORICAL,
            "observation_kind": ObservationKind.PROVIDER_PUBLISHED,
            "quality": Quality(state=QualityState.KNOWN_VALUE),
            "payload_type": payload_type,
            "payload": payload,
            "provenance": Provenance(
                provider="rc-audit-source",
                ingestion_method=IngestionMethod.LOADED_FIXTURE,
                origin_kind=ObservationKind.PROVIDER_PUBLISHED,
                normalized=False,
                provider_metadata=provider_metadata or {},
            ),
        }
    )


ALL_DOMAINS = [
    EventType.MARKET_SNAPSHOT,
    EventType.BORROW_FEE,
    EventType.BORROW_AVAILABILITY,
    EventType.PUBLISHED_SHORT_INTEREST,
    EventType.SEC_FILING,
    EventType.TRADING_HALT,
    EventType.NEWS_ITEM,
    EventType.BAR,
    EventType.TRADE,
    EventType.QUOTE,
]
# Domains that additionally gate provider publication (source_timestamp) against as_of.
PUBLICATION_GATED = [
    EventType.PUBLISHED_SHORT_INTEREST,
    EventType.SEC_FILING,
    EventType.TRADING_HALT,
    EventType.NEWS_ITEM,
    EventType.BAR,
    EventType.TRADE,
    EventType.QUOTE,
]


def _bundle(observation: Observation):
    return build_point_in_time_evidence(
        "TESTA",
        [observation],
        PointInTimeEvidencePolicy(
            as_of=AS_OF,
            allow_stale=True,
            allow_delayed=True,
            allow_unknown_freshness=True,
        ),
    )


def _included_ids(bundle) -> set[str]:
    return {item.observation_id for item in bundle.observations}


# --------------------------------------------------------------------------- #
# Canonical compatibility
# --------------------------------------------------------------------------- #

def test_schema_version_is_pinned_to_1_0_0() -> None:
    obs = _observation(
        EventType.TRADE,
        source_timestamp=AS_OF,
        received_timestamp=AS_OF,
        effective_timestamp=AS_OF,
    )
    assert obs.schema_version == "1.0.0"
    with pytest.raises(Exception):
        Observation.model_validate({**obs.model_dump(mode="python"), "schema_version": "1.1.0"})


def test_missing_trade_size_is_distinct_from_zero() -> None:
    missing = TradePayload(price=Decimal("10.00"))
    zero = TradePayload(price=Decimal("10.00"), size=0)
    assert missing.size is None
    assert zero.size == 0
    assert serialize_observation_payload(missing) != serialize_observation_payload(zero)


def serialize_observation_payload(payload) -> bytes:
    from squeeze_core.serialization import canonical_json_bytes

    return canonical_json_bytes(payload)


def test_crossed_quote_is_representable_without_forcing_invalid() -> None:
    crossed = QuotePayload(bid_price=Decimal("10.10"), ask_price=Decimal("10.00"))
    assert crossed.is_crossed is True
    obs = _observation(
        EventType.QUOTE,
        source_timestamp=AS_OF,
        received_timestamp=AS_OF,
        effective_timestamp=AS_OF,
    )
    obs = Observation.model_validate({**obs.model_dump(mode="python"), "payload": crossed.model_dump(mode="python")})
    # A crossed quote is objective structure; quality is not forced to INVALID.
    assert obs.quality.state is QualityState.KNOWN_VALUE
    assert obs.payload.is_crossed is True


def test_serialize_deserialize_round_trip_is_stable() -> None:
    for event_type in ALL_DOMAINS:
        obs = _observation(
            event_type,
            source_timestamp=AS_OF,
            received_timestamp=AS_OF,
            effective_timestamp=AS_OF,
        )
        blob = serialize_observation(obs)
        restored = deserialize_observation(blob)
        assert restored == obs
        assert serialize_observation(obs) == serialize_observation(obs)
        assert canonical_hash(obs) == canonical_hash(restored)


def test_old_serialized_observations_still_validate() -> None:
    for name in ("minimal_session.jsonl", "quality_edge_cases.jsonl"):
        observations = load_fixture(ROOT / name)
        assert observations
        assert all(item.schema_version == "1.0.0" for item in observations)


# --------------------------------------------------------------------------- #
# Cross-domain point-in-time consistency
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("event_type", ALL_DOMAINS)
def test_eligible_when_all_gates_before_as_of(event_type) -> None:
    obs = _observation(
        event_type,
        source_timestamp=AS_OF - timedelta(hours=2),
        received_timestamp=AS_OF - timedelta(hours=1),
        effective_timestamp=AS_OF - timedelta(hours=1),
    )
    assert obs.observation_id in _included_ids(_bundle(obs))


@pytest.mark.parametrize("event_type", ALL_DOMAINS)
def test_receipt_after_as_of_excludes_every_domain(event_type) -> None:
    obs = _observation(
        event_type,
        source_timestamp=AS_OF - timedelta(hours=2),
        received_timestamp=AS_OF + timedelta(hours=1),
        effective_timestamp=AS_OF - timedelta(hours=1),
    )
    assert obs.observation_id not in _included_ids(_bundle(obs))


@pytest.mark.parametrize("event_type", ALL_DOMAINS)
def test_effective_after_as_of_excludes_every_domain(event_type) -> None:
    obs = _observation(
        event_type,
        source_timestamp=AS_OF - timedelta(hours=2),
        received_timestamp=AS_OF - timedelta(hours=1),
        effective_timestamp=AS_OF + timedelta(hours=1),
    )
    assert obs.observation_id not in _included_ids(_bundle(obs))


@pytest.mark.parametrize("event_type", PUBLICATION_GATED)
def test_publication_after_as_of_excludes_publication_gated_domains(event_type) -> None:
    obs = _observation(
        event_type,
        source_timestamp=AS_OF + timedelta(hours=1),
        received_timestamp=AS_OF - timedelta(hours=1),
        effective_timestamp=AS_OF - timedelta(hours=1),
    )
    assert obs.observation_id not in _included_ids(_bundle(obs))


@pytest.mark.parametrize("event_type", [EventType.TRADE, EventType.QUOTE])
def test_future_event_time_alone_does_not_create_eligibility(event_type) -> None:
    # All availability gates are before as_of, but the provider event time is in the future.
    obs = _observation(
        event_type,
        source_timestamp=AS_OF - timedelta(hours=1),
        received_timestamp=AS_OF - timedelta(hours=1),
        effective_timestamp=AS_OF - timedelta(hours=1),
        provider_metadata={"event_timestamp": (AS_OF + timedelta(hours=1)).isoformat()},
    )
    assert obs.observation_id not in _included_ids(_bundle(obs))
