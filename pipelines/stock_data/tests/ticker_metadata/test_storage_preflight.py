import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.ticker_metadata.locking import MetadataRefreshLock
from src.ticker_metadata.storage import (
    MetadataBoundaryError,
    MetadataStore,
    resolve_existing_database,
)


REGISTRY_SQL = """
CREATE TABLE tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    company_name VARCHAR(255),
    exchange VARCHAR(50),
    sector VARCHAR(100),
    industry VARCHAR(100),
    country VARCHAR(100),
    market_cap FLOAT,
    is_etf BOOLEAN,
    is_active BOOLEAN
)
"""


def make_registry(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(REGISTRY_SQL)
        connection.executemany(
            "INSERT INTO tickers (ticker, is_active) VALUES (?, ?)",
            [("AAPL", 1), ("OLD", 0)],
        )


@pytest.mark.parametrize("kind", ["missing", "directory", "empty", "malformed"])
def test_preflight_refuses_invalid_targets_without_creating_database(tmp_path, kind):
    target = tmp_path / "market.db"
    if kind == "directory":
        target.mkdir()
    elif kind == "empty":
        target.touch()
    elif kind == "malformed":
        target.write_bytes(b"not a sqlite database")

    with pytest.raises(MetadataBoundaryError) as captured:
        MetadataStore.preflight(target)

    assert captured.value.code == {
        "missing": "database_missing",
        "directory": "database_not_regular_file",
        "empty": "database_empty",
        "malformed": "database_header_invalid",
    }[kind]
    if kind == "missing":
        assert not target.exists()


def test_resolve_existing_database_returns_absolute_canonical_path(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "market.db"
    target.parent.mkdir()
    make_registry(target)
    monkeypatch.chdir(tmp_path)

    assert resolve_existing_database(Path("nested") / "market.db") == target.resolve()


def test_preflight_uses_rw_uri_and_reports_bounded_registry_summary(tmp_path):
    target = tmp_path / "market data.db"
    make_registry(target)
    real_connect = sqlite3.connect
    calls = []
    connections = []

    class TrackingConnection(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def recording_connect(database, *args, **kwargs):
        calls.append((database, kwargs.copy()))
        connection = real_connect(
            database, *args, **kwargs, factory=TrackingConnection
        )
        connections.append(connection)
        return connection

    with patch("src.ticker_metadata.storage.sqlite3.connect", side_effect=recording_connect):
        summary = MetadataStore.preflight(target)

    assert calls
    assert all(str(database).startswith("file:") for database, _ in calls)
    assert all("mode=rw" in str(database) for database, _ in calls)
    assert all(options["uri"] is True for _, options in calls)
    assert all(connection.closed for connection in connections)
    assert summary.database_path == target.resolve()
    assert summary.quick_check == "ok"
    assert summary.ticker_count == 2
    assert summary.registry_columns == (
        "id",
        "ticker",
        "company_name",
        "exchange",
        "sector",
        "industry",
        "country",
        "market_cap",
        "is_etf",
        "is_active",
    )


@pytest.mark.parametrize(
    ("schema", "code"),
    [
        ("CREATE TABLE other (id INTEGER PRIMARY KEY)", "registry_missing"),
        ("CREATE TABLE tickers (id INTEGER, ticker TEXT)", "registry_primary_key_invalid"),
        ("CREATE TABLE tickers (id INTEGER PRIMARY KEY)", "registry_symbol_missing"),
        ("CREATE TABLE tickers (id INTEGER PRIMARY KEY, ticker TEXT)", "registry_symbol_nullable"),
    ],
)
def test_preflight_refuses_wrong_registry_before_provider_work(tmp_path, schema, code):
    target = tmp_path / "wrong.db"
    with sqlite3.connect(target) as connection:
        connection.execute(schema)

    with patch("yfinance.Ticker") as provider_factory:
        with pytest.raises(MetadataBoundaryError) as captured:
            MetadataStore.preflight(target)

    assert captured.value.code == code
    provider_factory.assert_not_called()


def test_preflight_surfaces_quick_check_failure_with_stable_code(tmp_path):
    target = tmp_path / "corrupt.db"
    make_registry(target)
    data = bytearray(target.read_bytes())
    data[4096:4104] = b"CORRUPT!"
    target.write_bytes(data)

    try:
        MetadataStore.preflight(target)
    except MetadataBoundaryError as exc:
        assert exc.code in {"database_corrupt", "database_quick_check_failed"}
    else:
        pytest.skip("This SQLite build did not read the damaged page during quick_check")


def test_same_database_lock_is_exclusive_and_different_database_is_independent(tmp_path):
    first_db = tmp_path / "first.db"
    second_db = tmp_path / "second.db"
    make_registry(first_db)
    make_registry(second_db)

    with MetadataRefreshLock(first_db):
        with pytest.raises(MetadataBoundaryError) as captured:
            with MetadataRefreshLock(first_db):
                pass
        assert captured.value.code == "metadata_refresh_locked"
        with MetadataRefreshLock(second_db):
            pass

    with MetadataRefreshLock(first_db):
        pass
