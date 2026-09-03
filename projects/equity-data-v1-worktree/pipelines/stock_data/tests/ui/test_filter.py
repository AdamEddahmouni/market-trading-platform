"""Tests for `src.ui.filter`.

Covers the pure-logic parts that don't touch the database or
interactive prompts:

  * `FilterSpec` defaults, truthiness, immutability
  * `FilterSpec.describe()`
  * `FilterSpec.to_sql()` for every column combination
  * `_parse_money`, `_split_csv`
  * `parse_filter_args()` for argpass-style + dict-style namespaces
  * `_parse_is_etf`, `_parse_int`
"""

from __future__ import annotations

import pytest

from src.ui.filter import (
    FilterSpec,
    _parse_int,
    _parse_is_etf,
    _parse_money,
    _split_csv,
    parse_filter_args,
)


# ── FilterSpec ──────────────────────────────────────────────


class TestFilterSpec:
    def test_defaults_are_empty(self):
        spec = FilterSpec()
        assert spec.exchanges == ()
        assert spec.sectors == ()
        assert spec.industries == ()
        assert spec.countries == ()
        assert spec.is_etf is None
        assert spec.min_market_cap is None
        assert spec.max_market_cap is None
        assert spec.ticker_regex is None
        assert spec.company_name_regex is None
        assert spec.limit is None
        # Empty spec is `False` (so callers can `if spec: ...`).
        assert bool(spec) is False

    def test_truthiness_any_field_set(self):
        assert bool(FilterSpec(exchanges=("NASDAQ",))) is True
        assert bool(FilterSpec(sectors=("Tech",)))     is True
        assert bool(FilterSpec(industries=("Bank",)))   is True
        assert bool(FilterSpec(countries=("US",)))      is True
        assert bool(FilterSpec(is_etf=True))            is True
        assert bool(FilterSpec(is_etf=False))           is True
        assert bool(FilterSpec(min_market_cap=1.0))     is True
        assert bool(FilterSpec(max_market_cap=1.0))     is True
        assert bool(FilterSpec(ticker_regex="^A"))      is True
        assert bool(FilterSpec(company_name_regex="X")) is True
        assert bool(FilterSpec(limit=10))               is True

    def test_is_frozen(self):
        spec = FilterSpec()
        with pytest.raises((AttributeError, Exception)):
            spec.exchanges = ("NASDAQ",)  # type: ignore[misc]

    def test_describe_empty(self):
        # The empty spec describes itself as no-filter.
        assert "no filter" in FilterSpec().describe()

    def test_describe_full(self, preset_filter):
        desc = preset_filter.describe()
        assert "exchange IN (NASDAQ,NYSE)" in desc
        assert "sector IN (Technology)" in desc
        assert "market_cap>=$1.00B" in desc
        assert "market_cap<=$100.00B" in desc
        assert "ticker~/^A/" in desc
        assert "company~/Apple|Bank/" in desc
        assert "limit=50" in desc


class TestFilterSpecToSql:
    def test_empty_spec_clause(self):
        where, params = FilterSpec().to_sql()
        # Only the is_active guard should be present.
        assert where == "t.is_active = 1"
        assert params == {}

    def test_single_exchange(self):
        where, params = FilterSpec(exchanges=("NASDAQ",)).to_sql()
        assert "t.exchange IN (:ex_0)" in where
        assert params == {"ex_0": "NASDAQ"}

    def test_multi_exchange(self):
        where, params = FilterSpec(exchanges=("NASDAQ", "NYSE")).to_sql()
        assert "t.exchange IN (:ex_0, :ex_1)" in where
        assert params == {"ex_0": "NASDAQ", "ex_1": "NYSE"}

    def test_multi_sector(self):
        where, params = FilterSpec(sectors=("Tech", "Finance")).to_sql()
        assert "t.sector IN (:sec_0, :sec_1)" in where
        assert params == {"sec_0": "Tech", "sec_1": "Finance"}

    def test_is_etf_true(self):
        where, params = FilterSpec(is_etf=True).to_sql()
        assert "t.is_etf = :is_etf" in where
        assert params == {"is_etf": True}

    def test_is_etf_false_still_filters(self):
        where, params = FilterSpec(is_etf=False).to_sql()
        assert "t.is_etf = :is_etf" in where
        assert params == {"is_etf": False}

    def test_market_cap_range(self):
        where, params = FilterSpec(min_market_cap=10, max_market_cap=20).to_sql()
        assert "t.market_cap >= :min_cap" in where
        assert "t.market_cap <= :max_cap" in where
        assert params == {"min_cap": 10, "max_cap": 20}

    def test_ticker_regex(self):
        where, params = FilterSpec(ticker_regex="^A").to_sql()
        assert "t.ticker REGEXP :ticker_re" in where
        assert params["ticker_re"] == "^A"

    def test_company_name_regex_emits_like_fallback(self):
        where, params = FilterSpec(company_name_regex="Apple").to_sql()
        assert "REGEXP :company_re" in where
        assert "LIKE :company_like" in where
        assert params["company_re"] == "Apple"
        assert params["company_like"] == "%Apple%"

    def test_combined_filters_use_AND(self):
        spec = FilterSpec(
            exchanges=("NASDAQ",),
            sectors=("Tech",),
            min_market_cap=1_000_000,
        )
        where, params = spec.to_sql()
        # Each filter clause is ANDed together.
        assert " AND " in where
        assert where.count("AND") == 3  # 1 is_active + 1 exchange + 1 sector + 1 min_cap - wait that's 4 ANDs
        # Actually: 4 clauses so 3 ANDs.
        # Re-check: is_active AND exchange AND sector AND min_cap -> 3 ANDs.
        assert "t.is_active = 1" in where
        assert "t.exchange IN (:ex_0)" in where
        assert "t.sector IN (:sec_0)" in where
        assert "t.market_cap >= :min_cap" in where
        assert params["ex_0"] == "NASDAQ"
        assert params["sec_0"] == "Tech"
        assert params["min_cap"] == 1_000_000


# ── Money / numeric parsers ─────────────────────────────────


class TestParseMoney:
    @pytest.mark.parametrize("raw,expected", [
        ("1B",   1_000_000_000),
        ("$1B",  1_000_000_000),
        ("500M", 500_000_000),
        ("$500M", 500_000_000),
        ("100K", 100_000),
        ("2.5T", 2_500_000_000_000),
        ("123",  123.0),
        ("1,000", 1000.0),
        ("",     None),
        (None,   None),
        ("abc",  None),
    ])
    def test_parse_money(self, raw, expected):
        assert _parse_money(raw) == expected

    def test_case_insensitive(self):
        assert _parse_money("1b") == _parse_money("1B")
        assert _parse_money("5m") == _parse_money("5M")


class TestSplitCsv:
    def test_empty(self):
        assert _split_csv("") == []
        assert _split_csv(None) == []

    def test_single(self):
        assert _split_csv("NASDAQ") == ["NASDAQ"]

    def test_multi(self):
        assert _split_csv("NASDAQ,NYSE") == ["NASDAQ", "NYSE"]

    def test_strips_whitespace(self):
        assert _split_csv("  NASDAQ , NYSE , IEX  ") == [
            "NASDAQ", "NYSE", "IEX",
        ]

    def test_drops_empty_tokens(self):
        assert _split_csv("NASDAQ,,NYSE") == ["NASDAQ", "NYSE"]


# ── parse_filter_args (CLI flags) ────────────────────────────


class TestParseFilterArgs:
    def test_empty_namespace(self, dummy_args):
        spec = parse_filter_args(dummy_args())
        assert spec.exchanges == ()
        assert spec.sectors == ()
        assert spec.limit is None
        assert bool(spec) is False

    def test_namespace_with_values(self, dummy_args):
        ns = dummy_args(
            exchange="NASDAQ,NYSE",
            sector="Technology",
            is_etf="yes",
            min_cap="1B",
            max_cap="100B",
            ticker_regex="^[A-C]",
            company_regex="Apple",
            limit="50",
        )
        spec = parse_filter_args(ns)
        assert spec.exchanges == ("NASDAQ", "NYSE")
        assert spec.sectors == ("Technology",)
        assert spec.is_etf is True
        assert spec.min_market_cap == 1_000_000_000
        assert spec.max_market_cap == 100_000_000_000
        assert spec.ticker_regex == "^[A-C]"
        assert spec.company_name_regex == "Apple"
        assert spec.limit == 50

    def test_is_etf_no(self, dummy_args):
        spec = parse_filter_args(dummy_args(is_etf="no"))
        assert spec.is_etf is False

    def test_is_etf_blank_keeps_none(self, dummy_args):
        spec = parse_filter_args(dummy_args(is_etf=""))
        assert spec.is_etf is None

    def test_dictionary_input(self):
        spec = parse_filter_args({
            "exchange": "NASDAQ",
            "sector": "Technology",
            "limit": 5,
        })
        assert spec.exchanges == ("NASDAQ",)
        assert spec.sectors == ("Technology",)
        assert spec.limit == 5

    def test_invalid_money_yields_none(self, dummy_args):
        spec = parse_filter_args(dummy_args(min_cap="not-a-number"))
        assert spec.min_market_cap is None

    def test_invalid_limit_yields_none(self, dummy_args):
        spec = parse_filter_args(dummy_args(limit="not-a-number"))
        assert spec.limit is None


# ── Internal role parsers ───────────────────────────────────


class TestParseIsEtf:
    @pytest.mark.parametrize("raw,expected", [
        ("yes", True), ("y", True), ("true", True), ("1", True),
        ("no", False), ("n", False), ("false", False), ("0", False),
        (None, None), ("", None), ("maybe", None),
        (True, True), (False, False),
    ])
    def test_parse_is_etf(self, raw, expected):
        assert _parse_is_etf(raw) == expected


class TestParseInt:
    @pytest.mark.parametrize("raw,expected", [
        ("123", 123), ("0", 0), ("", None), (None, None),
        ("abc", None), ("5.5", None),  # strict int
        (456, 456),
    ])
    def test_parse_int(self, raw, expected):
        assert _parse_int(raw) == expected
