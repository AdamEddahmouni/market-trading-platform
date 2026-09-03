import sys
from datetime import date, datetime
from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import text

from src import database
from src.pipeline import main
from src.refresh import FetchRange, plan_fetch_range
from src.scrapers.prices import PriceScraper, fetch_ticker_range, store_combined_data


class FakeTicker:
    def __init__(self):
        self.kwargs = None

    def history(self, **kwargs):
        self.kwargs = kwargs
        return pd.DataFrame(
            {
                "Open": [10.0],
                "High": [11.0],
                "Low": [9.0],
                "Close": [10.5],
                "Volume": [100],
                "Dividends": [0.0],
                "Stock Splits": [0.0],
            },
            index=pd.DatetimeIndex(["2026-08-21"]),
        )


@pytest.fixture
def price_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "refresh.sqlite3")
    database._engine = None
    database._metadata = None
    database.init_database()
    try:
        yield
    finally:
        if database._engine is not None:
            database._engine.dispose()
        database._engine = None
        database._metadata = None


def test_new_instrument_requests_full_history():
    assert plan_fetch_range(None, date(2026, 8, 23)) == FetchRange(
        None,
        date(2026, 8, 24),
        True,
    )


def test_existing_instrument_uses_overlap_and_exclusive_end():
    assert plan_fetch_range(date(2026, 8, 21), date(2026, 8, 23)) == FetchRange(
        date(2026, 8, 14),
        date(2026, 8, 24),
        False,
    )


def test_invalid_date_order_fails_closed():
    with pytest.raises(ValueError, match="latest_stored after through"):
        plan_fetch_range(date(2026, 8, 24), date(2026, 8, 23))


def test_fetch_existing_series_uses_bounded_dates():
    fake = FakeTicker()
    planned = plan_fetch_range(date(2026, 8, 21), date(2026, 8, 23))
    with patch("src.scrapers.prices.yf.Ticker", return_value=fake):
        result = fetch_ticker_range("TEST", planned)
    assert not result.empty
    assert fake.kwargs["start"] == "2026-08-14"
    assert fake.kwargs["end"] == "2026-08-24"
    assert "period" not in fake.kwargs


def test_fetch_new_series_requests_full_history():
    fake = FakeTicker()
    planned = plan_fetch_range(None, date(2026, 8, 23))
    with patch("src.scrapers.prices.yf.Ticker", return_value=fake):
        fetch_ticker_range("NEW", planned)
    assert fake.kwargs["period"] == "max"
    assert "start" not in fake.kwargs


def test_store_range_accepts_missing_adjusted_close(price_database):
    fake = FakeTicker()
    frame = fake.history()
    store_combined_data(1, "TEST", frame, replace_existing=True)
    with database.get_connection() as connection:
        row = connection.execute(
            text("SELECT close, adj_close FROM daily_prices WHERE ticker_id = 1")
        ).one()
    assert row[0] == 10.5
    assert row[1] is None


def test_latest_daily_price_dates_uses_one_latest_date_per_instrument(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "prices.sqlite3")
    database._engine = None
    database._metadata = None
    try:
        database.init_database()
        with database.get_connection() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO daily_prices (ticker_id, date, open, high, low, close, volume)
                    VALUES
                        (1, '2026-08-20', 10, 11, 9, 10.5, 100),
                        (1, '2026-08-21', 11, 12, 10, 11.5, 200),
                        (2, '2026-08-19', 20, 21, 19, 20.5, 300)
                    """
                )
            )
        assert database.latest_daily_price_dates() == {
            1: date(2026, 8, 21),
            2: date(2026, 8, 19),
        }
    finally:
        if database._engine is not None:
            database._engine.dispose()
        database._engine = None
        database._metadata = None


def test_refresh_upserts_overlap_actions_and_attempt(price_database):
    with database.get_connection() as connection:
        connection.execute(
            text("INSERT INTO tickers (id, ticker, is_active) VALUES (1, 'TEST', 1)")
        )
        connection.execute(
            text(
                "INSERT INTO daily_prices "
                "(ticker_id, date, open, high, low, close, volume, adj_close) "
                "VALUES (1, '2026-08-21', 10, 11, 9, 10.0, 100, 10.0)"
            )
        )

    fake = FakeTicker()
    fake.history = lambda **kwargs: pd.DataFrame(
        {
            "Open": [10.0],
            "High": [12.0],
            "Low": [9.0],
            "Close": [11.5],
            "Adj Close": [11.5],
            "Volume": [250],
            "Dividends": [0.25],
            "Stock Splits": [2.0],
        },
        index=pd.DatetimeIndex(["2026-08-21"]),
    )
    with patch("src.scrapers.prices.yf.Ticker", return_value=fake):
        PriceScraper().refresh(date(2026, 8, 23), max_items=1)

    with database.get_connection() as connection:
        close = connection.execute(
            text(
                "SELECT close FROM daily_prices "
                "WHERE ticker_id = 1 AND date = '2026-08-21'"
            )
        ).scalar_one()
        dividends = connection.execute(text("SELECT COUNT(*) FROM dividends")).scalar_one()
        splits = connection.execute(text("SELECT COUNT(*) FROM splits")).scalar_one()
    attempt = database.latest_attempt("price_refresh", "TEST")
    assert close == 11.5
    assert dividends == 1
    assert splits == 1
    assert attempt["outcome"] == "complete"
    assert str(attempt["requested_start"]) == "2026-08-14"
    assert str(attempt["requested_end"]) == "2026-08-24"


def test_refresh_skips_terminal_outcome_until_explicit_retry(price_database):
    with database.get_connection() as connection:
        connection.execute(
            text("INSERT INTO tickers (id, ticker, is_active) VALUES (1, 'BAD', 1)")
        )
    now = datetime(2026, 8, 23)
    database.record_attempt(
        "price_refresh",
        "BAD",
        "invalid_symbol",
        now,
        now,
    )

    with patch("src.scrapers.prices.yf.Ticker") as ticker_factory:
        outcomes = PriceScraper().refresh(date(2026, 8, 23), retry_errored=False)

    ticker_factory.assert_not_called()
    assert outcomes == {"skipped_terminal": 1}


def test_throttled_refresh_preserves_rows_and_redacts_attempt_detail(price_database):
    with database.get_connection() as connection:
        connection.execute(
            text("INSERT INTO tickers (id, ticker, is_active) VALUES (1, 'TEST', 1)")
        )
        connection.execute(
            text(
                "INSERT INTO daily_prices "
                "(ticker_id, date, open, high, low, close, volume, adj_close) "
                "VALUES (1, '2026-08-21', 10, 11, 9, 10.0, 100, 10.0)"
            )
        )

    class ThrottledTicker:
        def history(self, **kwargs):
            raise RuntimeError("HTTP 429 Authorization: Bearer secret-token")

    with (
        patch("src.scrapers.prices.yf.Ticker", return_value=ThrottledTicker()),
        patch("src.scrapers.prices.time.sleep"),
    ):
        outcomes = PriceScraper().refresh(date(2026, 8, 23), max_items=1)

    with database.get_connection() as connection:
        close = connection.execute(
            text("SELECT close FROM daily_prices WHERE ticker_id = 1")
        ).scalar_one()
    attempt = database.latest_attempt("price_refresh", "TEST")
    assert outcomes == {"throttled": 1}
    assert close == 10.0
    assert attempt["outcome"] == "throttled"
    assert "secret-token" not in attempt["detail"]
    assert "[REDACTED]" in attempt["detail"]


def test_refresh_cli_dispatches_strict_through_date_and_limit():
    with (
        patch.object(
            sys,
            "argv",
            [
                "pipeline",
                "refresh-prices",
                "17",
                "--through",
                "2026-08-23",
                "--retry-errored",
            ],
        ),
        patch("src.pipeline.init_database"),
        patch("src.pipeline.ensure_progress_table"),
        patch("src.scrapers.prices.PriceScraper") as scraper_type,
    ):
        main()
    scraper_type.return_value.refresh.assert_called_once_with(
        date(2026, 8, 23),
        retry_errored=True,
        max_items=17,
    )
    scraper_type.return_value.cleanup.assert_called_once_with()
