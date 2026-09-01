from datetime import datetime, timezone
import sqlite3
import sys
from unittest.mock import patch

from src.pipeline import main
from src.ticker_metadata.cli import run_refresh_ticker_metadata
from src.ticker_metadata.models import (
    ClassifiedResult,
    CollectorProvenance,
    ProviderCallResult,
)
from src.acquisition import AcquisitionOutcome
from src.operator_console.filter import FilterSpec


REGISTRY_SQL = """
CREATE TABLE tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    company_name VARCHAR(255), exchange VARCHAR(50), sector VARCHAR(100),
    industry VARCHAR(100), country VARCHAR(100), market_cap FLOAT,
    is_etf BOOLEAN, is_active BOOLEAN
)
"""


def make_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute(REGISTRY_SQL)
        connection.executemany(
            "INSERT INTO tickers (id, ticker, exchange, is_active) VALUES (?, ?, ?, ?)",
            [(2, "SECRETROW", "NYSE", 0), (1, "AAPL", "NASDAQ", 1)],
        )


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def call(self, symbol, ordinal):
        self.calls.append((symbol, ordinal))
        now = datetime(2026, 8, 24, 16, 0, tzinfo=timezone.utc)
        return ProviderCallResult(
            ordinal,
            now,
            now,
            ClassifiedResult(
                AcquisitionOutcome.COMPLETE,
                "identity_envelope_complete",
                projected={
                    "provider_symbol": symbol,
                    "short_name": "DO-NOT-PRINT-ROW-VALUE",
                    "exchange_code": "NMS",
                    "quote_type": "EQUITY",
                },
                observed_fields=(
                    "exchange_code",
                    "provider_symbol",
                    "quote_type",
                    "short_name",
                ),
            ),
        )


def test_metadata_cli_dispatches_before_legacy_database_initialization():
    with (
        patch.object(
            sys,
            "argv",
            [
                "pipeline",
                "refresh-ticker-metadata",
                "--database",
                "C:/selected/market.db",
                "--limit",
                "17",
                "--exchange",
                "NASDAQ",
                "--retry-errored",
            ],
        ),
        patch("src.pipeline.init_database") as legacy_init,
        patch("src.pipeline.ensure_progress_table") as legacy_progress,
        patch("src.ticker_metadata.cli.run_refresh_ticker_metadata", return_value=7) as runner,
    ):
        code = main()

    assert code == 7
    legacy_init.assert_not_called()
    legacy_progress.assert_not_called()
    runner.assert_called_once()
    arguments = runner.call_args.kwargs
    assert arguments["database"] == "C:/selected/market.db"
    assert arguments["limit"] == 17
    assert arguments["retry_errored"] is True
    assert arguments["filter_spec"].exchanges == ("NASDAQ",)


def test_metadata_command_requires_explicit_database_before_provider_construction(capsys):
    with patch("src.ticker_metadata.cli.YFinanceMetadataAdapter") as provider_type:
        code = run_refresh_ticker_metadata(
            database=None,
            filter_spec=FilterSpec(),
            limit=1,
            retry_errored=False,
        )

    assert code != 0
    provider_type.assert_not_called()
    assert "database_required" in capsys.readouterr().err


def test_metadata_command_rejects_nonpositive_limit_before_provider(capsys, tmp_path):
    path = tmp_path / "market.db"
    make_database(path)
    with patch("src.ticker_metadata.cli.YFinanceMetadataAdapter") as provider_type:
        code = run_refresh_ticker_metadata(
            database=path,
            filter_spec=FilterSpec(),
            limit=0,
            retry_errored=False,
        )
    assert code != 0
    provider_type.assert_not_called()
    assert "limit_invalid" in capsys.readouterr().err


def test_real_cli_flow_prints_bounded_summary_without_row_values(tmp_path, capsys):
    path = tmp_path / "market.db"
    make_database(path)
    adapter = FakeAdapter()
    provenance = CollectorProvenance("abc123", False, "3.11.15", "yfinance", "1.6.0")

    code = run_refresh_ticker_metadata(
        database=path,
        filter_spec=FilterSpec(exchanges=("NASDAQ",)),
        limit=None,
        retry_errored=False,
        adapter=adapter,
        provenance=provenance,
        limiter=type("Noop", (), {"wait": lambda self: None})(),
    )

    captured = capsys.readouterr()
    assert code == 0
    assert adapter.calls == [("AAPL", 1)]
    assert str(path.resolve()) in captured.out
    for expected in (
        "contract_sha256=",
        "selected_tickers=1",
        "ticker_limit=unbounded",
        "workers=4",
        "rate_per_second=2",
        "calls=1",
        "committed_attempts=1",
        "committed_observations=1",
        "outcome.complete=1",
        "field.short_name.present=1",
        "field.short_name.missing=0",
        "circuit=closed",
    ):
        assert expected in captured.out
    assert "AAPL" not in captured.out
    assert "SECRETROW" not in captured.out
    assert "DO-NOT-PRINT-ROW-VALUE" not in captured.out
    assert captured.err == ""


def test_preflight_failure_is_stable_nonzero_and_does_not_create_file(tmp_path, capsys):
    missing = tmp_path / "missing.db"
    with patch("src.ticker_metadata.cli.YFinanceMetadataAdapter") as provider_type:
        code = run_refresh_ticker_metadata(
            database=missing,
            filter_spec=FilterSpec(),
            limit=None,
            retry_errored=False,
        )
    assert code == 2
    assert not missing.exists()
    provider_type.assert_not_called()
    assert "database_missing" in capsys.readouterr().err
