from datetime import UTC, datetime
from decimal import Decimal

import pytest

from squeeze_core.adapters.trades_quotes import (
    normalize_trade_quote_record,
    normalize_trade_quote_records,
)
from squeeze_core.contracts import Completeness, EventType, QualityState

from .test_models_and_parsing import record_values
from .test_trade_normalizer import context


def quote_values(**updates):
    values = record_values(
        record_type="QUOTE",
        provider_record_id="quote-1",
        price=None,
        size=None,
        trade_conditions=[],
        sale_condition=None,
        bid_price="10.24",
        bid_size=100,
        ask_price="10.26",
        ask_size=200,
        bid_side_id="bid-A",
        ask_side_id="ask-A",
        quote_condition="REGULAR",
        quote_source="VENUE_BOOK",
        market_scope="VENUE",
    )
    values.update(updates)
    return values


def test_complete_quote_preserves_sides_condition_scope_and_time():
    result = normalize_trade_quote_record(quote_values(), context())
    assert result.accepted is True
    observation = result.observations[0]
    assert observation.event_type is EventType.QUOTE
    assert observation.payload.bid_price == Decimal("10.24")
    assert observation.payload.bid_size == 100
    assert observation.payload.ask_price == Decimal("10.26")
    assert observation.payload.ask_size == 200
    metadata = observation.provenance.provider_metadata
    assert metadata["bid_side_id"] == "bid-A"
    assert metadata["ask_side_id"] == "ask-A"
    assert metadata["quote_condition"] == "REGULAR"
    assert metadata["quote_source"] == "VENUE_BOOK"
    assert metadata["market_scope"] == "VENUE"
    assert metadata["quote_market_state"] == "NORMAL"
    assert metadata["event_timestamp"] == datetime(
        2026, 1, 15, 14, 30, 0, 100000, tzinfo=UTC
    )


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"bid_price": None, "bid_size": None}, "QUOTE_ONE_SIDED"),
        ({"ask_price": None, "ask_size": None}, "QUOTE_ONE_SIDED"),
        ({"bid_price": None, "ask_price": None, "bid_size": None, "ask_size": None}, "QUOTE_MISSING_BOTH_SIDES"),
    ],
)
def test_one_sided_quotes_preserve_missing_side_and_both_missing_reject(updates, code):
    result = normalize_trade_quote_record(quote_values(**updates), context())
    if code == "QUOTE_MISSING_BOTH_SIDES":
        assert result.accepted is False
        assert result.rejection.code.value == code
    else:
        assert result.accepted is True
        assert result.observations[0].quality.completeness is Completeness.PARTIAL
        assert code in {item.code.value for item in result.diagnostics}
        assert result.observations[0].provenance.provider_metadata["quote_market_state"] == "UNKNOWN"


@pytest.mark.parametrize(
    "updates",
    [
        {"bid_price": "0"}, {"bid_price": "-1"}, {"bid_price": "bad"},
        {"ask_price": "0"}, {"ask_price": "-1"}, {"ask_price": "bad"},
    ],
)
def test_invalid_present_quote_prices_reject(updates):
    result = normalize_trade_quote_record(quote_values(**updates), context())
    assert result.rejection.code.value == "QUOTE_INVALID_PRICE"


def test_missing_zero_and_size_without_price_are_distinct():
    missing = normalize_trade_quote_record(quote_values(bid_size=None), context())
    zero = normalize_trade_quote_record(quote_values(bid_size=0), context())
    unusual = normalize_trade_quote_record(quote_values(bid_price=None, bid_size=10), context())
    assert missing.observations[0].payload.bid_size is None
    assert zero.observations[0].payload.bid_size == 0
    assert {item.code.value for item in missing.diagnostics} >= {"QUOTE_MISSING_BID_SIZE"}
    assert {item.code.value for item in zero.diagnostics} >= {"QUOTE_ZERO_BID_SIZE"}
    assert unusual.observations[0].payload.bid_price is None
    assert unusual.observations[0].payload.bid_size == 10
    assert "QUOTE_SIZE_WITHOUT_PRICE" in {item.code.value for item in unusual.diagnostics}


@pytest.mark.parametrize("field", ["bid_size", "ask_size"])
@pytest.mark.parametrize("value", [-1, Decimal("1.5")])
def test_negative_and_fractional_quote_sizes_reject(field, value):
    result = normalize_trade_quote_record(quote_values(**{field: value}), context())
    assert result.rejection.code.value == "QUOTE_INVALID_SIZE"


@pytest.mark.parametrize(
    ("bid", "ask", "expected", "code"),
    [
        ("10.24", "10.26", "NORMAL", "QUOTE_NORMAL_MARKET"),
        ("10.25", "10.25", "LOCKED", "QUOTE_LOCKED_MARKET"),
        ("10.26", "10.25", "CROSSED", "QUOTE_CROSSED_MARKET"),
        (None, "10.25", "UNKNOWN", "QUOTE_UNKNOWN_MARKET_STATE"),
    ],
)
def test_quote_market_state_is_objective_and_diagnostic(bid, ask, expected, code):
    result = normalize_trade_quote_record(
        quote_values(bid_price=bid, bid_size=None if bid is None else 100, ask_price=ask),
        context(),
    )
    observation = result.observations[0]
    assert observation.provenance.provider_metadata["quote_market_state"] == expected
    assert code in {item.code.value for item in result.diagnostics}
    assert "spread" not in observation.provenance.provider_metadata
    assert "midpoint" not in observation.provenance.provider_metadata


@pytest.mark.parametrize(
    "scope", ["VENUE", "NBBO", "CONSOLIDATED", "PROVIDER_AGGREGATED", "UNKNOWN"]
)
def test_quote_market_scope_is_preserved_without_synthesis(scope):
    result = normalize_trade_quote_record(quote_values(market_scope=scope), context())
    assert result.observations[0].provenance.provider_metadata["market_scope"] == scope
    if scope == "UNKNOWN":
        assert "QUOTE_UNKNOWN_MARKET_SCOPE" in {item.code.value for item in result.diagnostics}


def test_unknown_condition_source_and_venue_are_preserved():
    result = normalize_trade_quote_record(
        quote_values(quote_condition="PROVIDER_X", quote_source=None, venue=None), context()
    )
    metadata = result.observations[0].provenance.provider_metadata
    assert metadata["quote_condition"] == "PROVIDER_X"
    assert metadata["quote_source"] is None
    assert metadata["venue"] is None
    assert {item.code.value for item in result.diagnostics} >= {
        "QUOTE_UNKNOWN_CONDITION", "QUOTE_MISSING_SOURCE", "QUOTE_MISSING_VENUE"
    }


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("ORIGINAL", "QUOTE_ORIGINAL_RECORD"),
        ("CORRECTED", "QUOTE_CORRECTED_RECORD"),
        ("CANCELLED", "QUOTE_CANCELLED_RECORD"),
        ("DELETED", "QUOTE_DELETED_RECORD"),
        ("UNKNOWN", "QUOTE_UNKNOWN_STATUS"),
    ],
)
def test_quote_lifecycle_is_immutable(status, code):
    result = normalize_trade_quote_record(quote_values(status=status), context())
    assert code in {item.code.value for item in result.diagnostics}


def test_quote_duplicates_conflicts_revisions_and_cross_provider_rows_are_deterministic():
    original = quote_values(provider_record_id="quote-original")
    changed = quote_values(provider_record_id="quote-original", ask_price="10.27")
    cancelled = quote_values(
        provider_record_id="quote-cancel",
        status="CANCELLED",
        revision_number=1,
        supersedes_provider_record_id="quote-original",
        publication_timestamp="2026-01-15T09:31:00-05:00",
    )
    other_provider = quote_values(provider="PROVIDER_B", provider_record_id="quote-b")
    first = normalize_trade_quote_records(
        [original, dict(original), changed, cancelled, other_provider],
        context("2026-01-15T14:31:01Z"),
    )
    second = normalize_trade_quote_records(
        [original, dict(original), changed, cancelled, other_provider],
        context("2026-01-15T14:31:01Z"),
    )
    assert first == second
    assert len(first.observations) == 4
    assert "TRADE_QUOTE_DUPLICATE_RECORD" in {item.code.value for item in first.diagnostics}
    conflicts = [item for item in first.observations if item.source_record_id == "quote-original"]
    assert all(item.quality.state is QualityState.CONFLICTED for item in conflicts)
    cancellation = next(item for item in first.observations if item.source_record_id == "quote-cancel")
    assert cancellation.parent_observation_ids
    assert any(item.provenance.provider_metadata["provider"] == "PROVIDER_B" for item in first.observations)
