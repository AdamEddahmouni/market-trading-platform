from datetime import datetime

from squeeze_core.adapters.trades_quotes import normalize_trade_quote_records
from squeeze_core.evidence import (
    TradeQuoteSeriesDiagnosticCode,
    TradeQuoteSeriesPolicy,
    build_trade_quote_series,
)

from tests.adapters.trades_quotes.test_models_and_parsing import record_values
from tests.adapters.trades_quotes.test_quote_normalizer import quote_values
from tests.adapters.trades_quotes.test_trade_normalizer import context


def _observations(records, receipt="2026-01-15T14:35:00Z"):
    return normalize_trade_quote_records(records, context(receipt)).observations


def _policy(**updates):
    values = {
        "symbol": "testa",
        "as_of": datetime.fromisoformat("2026-01-15T14:40:00+00:00"),
    }
    values.update(updates)
    return TradeQuoteSeriesPolicy(**values)


def test_series_filters_symbol_provider_venue_and_scope_without_analytics():
    records = [
        record_values(provider="A", provider_record_id="trade-a"),
        record_values(provider="B", provider_record_id="trade-b"),
        quote_values(provider="A", provider_record_id="quote-a", market_scope="VENUE"),
        quote_values(provider="A", provider_record_id="quote-nbbo", market_scope="NBBO"),
        record_values(provider="A", provider_record_id="other", symbol="TESTB"),
    ]
    series = build_trade_quote_series(
        _observations(records),
        _policy(providers=("A",), venues=("XTEST",), market_scopes=("VENUE",)),
    )
    assert [item.source_record_id for item in series.trades] == ["trade-a"]
    assert [item.source_record_id for item in series.quotes] == ["quote-a"]
    dumped = series.model_dump(mode="json")
    for forbidden in (
        "aggressor_side", "buy_volume", "sell_volume", "imbalance", "delta",
        "spread", "midpoint", "slippage", "liquidity", "momentum", "score",
        "rank", "recommendation", "signal",
    ):
        assert forbidden not in dumped


def test_event_order_and_arrival_order_are_distinct_and_stable():
    records = [
        record_values(
            provider_record_id="arrived-first-event-later",
            sequence_number=102,
            event_timestamp="2026-01-15T09:30:00.300000-05:00",
        ),
        record_values(
            provider_record_id="arrived-second-event-earlier",
            sequence_number=101,
            event_timestamp="2026-01-15T09:30:00.100000-05:00",
        ),
    ]
    series = build_trade_quote_series(_observations(records), _policy())
    assert [item.source_record_id for item in series.trades] == [
        "arrived-second-event-earlier", "arrived-first-event-later"
    ]
    metadata = {item.source_record_id: item.provenance.provider_metadata for item in series.trades}
    assert metadata["arrived-first-event-later"]["arrival_index"] == 0
    assert metadata["arrived-second-event-earlier"]["arrival_index"] == 1
    assert TradeQuoteSeriesDiagnosticCode.OUT_OF_ORDER_SEQUENCE in {item.code for item in series.diagnostics}


def test_sequence_diagnostics_cover_duplicate_conflict_reset_missing_and_unknown_scope():
    records = [
        record_values(provider_record_id="ordered-100", sequence_number=100),
        record_values(provider_record_id="duplicate-100", sequence_number=100),
        record_values(provider_record_id="changed-100", sequence_number=100, price="10.26"),
        record_values(provider_record_id="reset-1", sequence_number=1, sequence_reset=True),
        record_values(provider_record_id="missing", sequence_number=None, sequence_scope="VENUE"),
        quote_values(provider_record_id="unknown-scope", sequence_number=5, sequence_scope="UNKNOWN"),
    ]
    series = build_trade_quote_series(_observations(records), _policy())
    codes = {item.code for item in series.diagnostics}
    assert {
        TradeQuoteSeriesDiagnosticCode.DUPLICATE_SEQUENCE,
        TradeQuoteSeriesDiagnosticCode.SAME_SEQUENCE_CONFLICT,
        TradeQuoteSeriesDiagnosticCode.SEQUENCE_RESET,
        TradeQuoteSeriesDiagnosticCode.MISSING_SEQUENCE,
        TradeQuoteSeriesDiagnosticCode.UNKNOWN_SEQUENCE_SCOPE,
    } <= codes


def test_incompatible_sequence_scopes_are_not_compared():
    records = [
        record_values(provider_record_id="venue", sequence_number=10, sequence_scope="VENUE"),
        record_values(provider_record_id="symbol", sequence_number=9, sequence_scope="SYMBOL"),
    ]
    series = build_trade_quote_series(_observations(records), _policy())
    codes = {item.code for item in series.diagnostics}
    assert TradeQuoteSeriesDiagnosticCode.INCOMPATIBLE_SEQUENCE_SCOPES in codes
    assert TradeQuoteSeriesDiagnosticCode.OUT_OF_ORDER_SEQUENCE not in codes


def test_quote_states_and_one_sided_structure_are_reported_without_calculation():
    records = [
        quote_values(provider_record_id="normal"),
        quote_values(provider_record_id="locked", bid_price="10.25", ask_price="10.25"),
        quote_values(provider_record_id="crossed", bid_price="10.26", ask_price="10.25"),
        quote_values(provider_record_id="one-sided", ask_price=None, ask_size=None),
    ]
    series = build_trade_quote_series(_observations(records), _policy())
    assert {item.code for item in series.diagnostics} >= {
        TradeQuoteSeriesDiagnosticCode.NORMAL_QUOTE,
        TradeQuoteSeriesDiagnosticCode.LOCKED_QUOTE,
        TradeQuoteSeriesDiagnosticCode.CROSSED_QUOTE,
        TradeQuoteSeriesDiagnosticCode.ONE_SIDED_QUOTE,
    }


def test_series_strictly_gates_publication_receipt_effective_and_future_event():
    records = [
        record_values(provider_record_id="future-publication", publication_timestamp="2026-01-15T10:00:00-05:00"),
        record_values(provider_record_id="future-event", event_timestamp="2026-01-15T10:00:00-05:00"),
    ]
    observations = list(_observations(records, "2026-01-15T14:35:00Z"))
    late_receipt = _observations(
        [record_values(provider_record_id="future-receipt")], "2026-01-15T15:00:00Z"
    )[0]
    series = build_trade_quote_series((*observations, late_receipt), _policy())
    assert series.trades == ()
    assert {item.code for item in series.diagnostics} >= {
        TradeQuoteSeriesDiagnosticCode.NOT_YET_PUBLISHED,
        TradeQuoteSeriesDiagnosticCode.NOT_YET_RECEIVED,
        TradeQuoteSeriesDiagnosticCode.FUTURE_EVENT,
    }


def test_lifecycle_versions_latest_ids_and_hash_are_repeatable():
    records = [
        record_values(provider_record_id="trade-original"),
        record_values(
            provider_record_id="trade-corrected", status="CORRECTED",
            supersedes_provider_record_id="trade-original", price="10.26",
            publication_timestamp="2026-01-15T09:31:00-05:00",
        ),
        quote_values(provider_record_id="quote-original"),
        quote_values(
            provider_record_id="quote-cancelled", status="CANCELLED",
            supersedes_provider_record_id="quote-original",
            publication_timestamp="2026-01-15T09:32:00-05:00",
        ),
    ]
    observations = _observations(records)
    first = build_trade_quote_series(observations, _policy())
    second = build_trade_quote_series(observations, _policy())
    assert first == second
    assert first.latest_trade_observation_id == first.trades[-1].observation_id
    assert first.latest_quote_observation_id == first.quotes[-1].observation_id
    assert len(first.lifecycle_chains) == 2
    assert first.series_hash
