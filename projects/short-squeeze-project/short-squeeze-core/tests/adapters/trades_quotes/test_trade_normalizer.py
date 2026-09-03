from datetime import UTC, datetime
from decimal import Decimal

import pytest

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.trades_quotes import (
    normalize_trade_quote_record,
    normalize_trade_quote_records,
)
from squeeze_core.contracts import (
    Completeness,
    EntitlementState,
    EventType,
    IngestionMethod,
    QualityState,
)

from .test_models_and_parsing import record_values


def context(ingested_at="2026-01-15T14:30:00.300000Z"):
    return AdapterContext(
        ingested_at=datetime.fromisoformat(ingested_at.replace("Z", "+00:00")),
        source_timezone="-05:00",
        provider="REPRESENTATIVE_FEED",
        adapter_version="1.0.0",
        normalization_version="phase1i-1.0.0",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="local-trade-quote-fixture",
    )


def test_complete_trade_preserves_objective_semantics_and_times():
    result = normalize_trade_quote_record(record_values(), context())
    assert result.accepted is True
    observation = result.observations[0]
    assert observation.event_type is EventType.TRADE
    assert observation.payload.price == Decimal("10.25")
    assert observation.payload.size == 100
    assert observation.payload.conditions == ("REGULAR", "ODD_LOT")
    assert observation.sequence_number == 100
    assert observation.exchange == "XTEST"
    assert observation.source_timestamp == datetime(2026, 1, 15, 14, 30, 0, 200000, tzinfo=UTC)
    assert observation.received_timestamp == datetime(2026, 1, 15, 14, 30, 0, 300000, tzinfo=UTC)
    assert observation.effective_timestamp == observation.received_timestamp
    metadata = observation.provenance.provider_metadata
    assert metadata["event_timestamp"] == datetime(2026, 1, 15, 14, 30, 0, 100000, tzinfo=UTC)
    assert metadata["capture_timestamp"] == datetime(2026, 1, 15, 14, 30, 0, 250000, tzinfo=UTC)
    assert metadata["venue"] == "XTEST"
    assert metadata["sequence_scope"] == "VENUE"
    assert metadata["size_unit"] == "SHARES"
    assert metadata["sale_condition"] == "REGULAR"


@pytest.mark.parametrize("price", [None, "0", "-1", "bad", "NaN"])
def test_missing_zero_negative_and_invalid_trade_price_reject(price):
    result = normalize_trade_quote_record(record_values(price=price), context())
    assert result.accepted is False
    assert result.rejection.code.value == "TRADE_INVALID_PRICE"


def test_missing_trade_size_remains_missing_and_partial():
    result = normalize_trade_quote_record(record_values(size=None), context())
    observation = result.observations[0]
    assert observation.payload.size is None
    assert observation.quality.completeness is Completeness.PARTIAL
    assert "TRADE_MISSING_SIZE" in {item.code.value for item in result.diagnostics}


def test_zero_trade_size_remains_known_zero():
    result = normalize_trade_quote_record(record_values(size=0), context())
    assert result.observations[0].payload.size == 0
    assert "TRADE_ZERO_SIZE" in {item.code.value for item in result.diagnostics}


@pytest.mark.parametrize("size", [-1, Decimal("1.5")])
def test_negative_and_fractional_trade_size_reject(size):
    result = normalize_trade_quote_record(record_values(size=size), context())
    assert result.accepted is False
    assert result.rejection.code.value == "TRADE_INVALID_SIZE"


def test_unknown_conditions_and_venue_are_preserved_not_interpreted():
    result = normalize_trade_quote_record(
        record_values(trade_conditions=["PROVIDER_X"], sale_condition=None, venue=None),
        context(),
    )
    observation = result.observations[0]
    assert observation.payload.conditions == ("PROVIDER_X",)
    assert observation.provenance.provider_metadata["venue"] is None
    assert {item.code.value for item in result.diagnostics} >= {
        "TRADE_UNKNOWN_CONDITION", "TRADE_MISSING_VENUE"
    }


def test_missing_publication_strict_rejects_and_placeholders_remain_uncertain():
    strict = normalize_trade_quote_record(record_values(publication_timestamp=None), context())
    assert strict.rejection.code.value == "TRADE_QUOTE_UNKNOWN_AVAILABILITY"

    capture = normalize_trade_quote_record(
        record_values(
            publication_timestamp=None,
            unknown_availability_policy="CAPTURE_AS_UNCERTAIN_PLACEHOLDER",
        ),
        context(),
    )
    assert capture.accepted is True
    assert capture.observations[0].source_timestamp == datetime(
        2026, 1, 15, 14, 30, 0, 250000, tzinfo=UTC
    )
    assert capture.observations[0].provenance.provider_metadata["publication_timestamp"] is None
    assert "TRADE_QUOTE_CAPTURE_PLACEHOLDER" in {item.code.value for item in capture.diagnostics}

    receipt = normalize_trade_quote_record(
        record_values(
            publication_timestamp=None,
            unknown_availability_policy="RECEIPT_AS_UNCERTAIN_PLACEHOLDER",
        ),
        context(),
    )
    assert receipt.observations[0].source_timestamp == context().ingested_at
    assert "TRADE_QUOTE_RECEIPT_PLACEHOLDER" in {item.code.value for item in receipt.diagnostics}


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("ORIGINAL", "TRADE_ORIGINAL_RECORD"),
        ("CORRECTED", "TRADE_CORRECTED_RECORD"),
        ("CANCELLED", "TRADE_CANCELLED_RECORD"),
        ("DELETED", "TRADE_DELETED_RECORD"),
        ("UNKNOWN", "TRADE_UNKNOWN_STATUS"),
    ],
)
def test_trade_lifecycle_status_is_objective(status, code):
    result = normalize_trade_quote_record(record_values(status=status), context())
    assert code in {item.code.value for item in result.diagnostics}


def test_exact_duplicate_suppressed_same_id_conflict_preserved_and_revision_linked():
    original = record_values(provider_record_id="trade-original")
    correction = record_values(
        provider_record_id="trade-correction",
        status="CORRECTED",
        revision_number=1,
        supersedes_provider_record_id="trade-original",
        price="10.26",
        publication_timestamp="2026-01-15T09:31:00-05:00",
    )
    conflict = record_values(provider_record_id="trade-original", price="10.27")
    result = normalize_trade_quote_records(
        [original, dict(original), conflict, correction], context("2026-01-15T14:31:01Z")
    )
    assert len(result.observations) == 3
    assert "TRADE_QUOTE_DUPLICATE_RECORD" in {item.code.value for item in result.diagnostics}
    assert "TRADE_QUOTE_CONFLICTING_RECORD" in {item.code.value for item in result.diagnostics}
    corrected = next(item for item in result.observations if item.source_record_id == "trade-correction")
    assert corrected.parent_observation_ids
    assert corrected.quality.state is QualityState.KNOWN_VALUE
    conflicts = [item for item in result.observations if item.source_record_id == "trade-original"]
    assert all(item.quality.state is QualityState.CONFLICTED for item in conflicts)


def test_same_event_from_two_providers_remains_independent_and_repeatable():
    first = record_values(provider="PROVIDER_A", provider_record_id="a")
    second = record_values(provider="PROVIDER_B", provider_record_id="b")
    one = normalize_trade_quote_records([second, first], context())
    two = normalize_trade_quote_records([second, first], context())
    assert one == two
    assert len(one.observations) == 2
    assert {item.provenance.provider_metadata["provider"] for item in one.observations} == {
        "PROVIDER_A", "PROVIDER_B"
    }
