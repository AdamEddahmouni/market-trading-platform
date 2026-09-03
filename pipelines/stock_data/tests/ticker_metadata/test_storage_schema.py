from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from src.acquisition import AcquisitionOutcome
from src.ticker_metadata.contract import (
    REQUEST_CONTRACT_JSON,
    REQUEST_CONTRACT_SHA256,
    REQUEST_CONTRACT_VERSION,
)
from src.ticker_metadata.models import AttemptRecord, ObservationRecord
from src.ticker_metadata.storage import MetadataBoundaryError, MetadataStore
from src.ui.filter import FilterSpec


REGISTRY_SQL = """
CREATE TABLE tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    company_name VARCHAR(255), exchange VARCHAR(50), sector VARCHAR(100),
    industry VARCHAR(100), country VARCHAR(100), market_cap FLOAT,
    is_etf BOOLEAN, is_active BOOLEAN
)
"""


def make_store(tmp_path, rows=((3, "MSFT", 1), (1, "AAPL", 1), (2, "OLD", 0))):
    path = tmp_path / "market.db"
    with sqlite3.connect(path) as connection:
        connection.execute(REGISTRY_SQL)
        connection.executemany(
            "INSERT INTO tickers (id, ticker, is_active) VALUES (?, ?, ?)", rows
        )
    store = MetadataStore(path)
    store.initialize_schema()
    return path, store


def records(raw_ticker_id=1, symbol="AAPL", outcome=AcquisitionOutcome.COMPLETE):
    now = datetime(2026, 8, 24, 14, 30, tzinfo=timezone.utc)
    attempt = AttemptRecord(
        run_id="run-opaque",
        raw_ticker_id=raw_ticker_id,
        requested_symbol=symbol,
        provider="yfinance",
        method="get_info",
        request_contract_json=REQUEST_CONTRACT_JSON,
        request_contract_version=REQUEST_CONTRACT_VERSION,
        request_contract_sha256=REQUEST_CONTRACT_SHA256,
        retry_ordinal=1,
        started_at_utc=now,
        completed_at_utc=now,
        requested_fields=("currency", "symbol"),
        observed_fields=("provider_symbol", "short_name"),
        outcome=outcome,
        reason_code="test_reason",
        detail=None,
        collector_git_revision="abc123",
        collector_dirty=False,
        python_version="3.11.15",
        provider_library_name="yfinance",
        provider_library_version="1.6.0",
    )
    observation = ObservationRecord(
        run_id=attempt.run_id,
        raw_ticker_id=attempt.raw_ticker_id,
        requested_symbol=attempt.requested_symbol,
        provider=attempt.provider,
        method=attempt.method,
        request_contract_json=attempt.request_contract_json,
        request_contract_version=attempt.request_contract_version,
        request_contract_sha256=attempt.request_contract_sha256,
        provider_observed_at_utc=now,
        projected={"provider_symbol": symbol, "short_name": "Apple"},
        present_fields=("provider_symbol", "short_name"),
        collector_git_revision=attempt.collector_git_revision,
        collector_dirty=attempt.collector_dirty,
        python_version=attempt.python_version,
        provider_library_name=attempt.provider_library_name,
        provider_library_version=attempt.provider_library_version,
    )
    return attempt, observation


def test_schema_is_exact_idempotent_and_foreign_keyed(tmp_path):
    path, store = make_store(tmp_path)
    store.initialize_schema()

    with sqlite3.connect(path) as connection:
        attempts = tuple(connection.execute("PRAGMA table_info('ticker_metadata_attempts')"))
        observations = tuple(connection.execute("PRAGMA table_info('ticker_metadata_observations')"))
        foreign_attempts = tuple(connection.execute("PRAGMA foreign_key_list('ticker_metadata_attempts')"))
        foreign_observations = tuple(connection.execute("PRAGMA foreign_key_list('ticker_metadata_observations')"))
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex%'"
            )
        }
        triggers = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }

    assert attempts[0][1:6] == ("attempt_id", "INTEGER", 0, None, 1)
    assert observations[0][1:6] == ("observation_id", "INTEGER", 0, None, 1)
    assert len(attempts) == 22
    assert len(observations) == 28
    assert {(row[2], row[3], row[4]) for row in foreign_attempts} == {
        ("tickers", "raw_ticker_id", "id")
    }
    assert {(row[2], row[3], row[4]) for row in foreign_observations} == {
        ("ticker_metadata_attempts", "attempt_id", "attempt_id"),
        ("tickers", "raw_ticker_id", "id"),
    }
    assert indexes == {
        "idx_tma_ticker_contract_attempt",
        "idx_tma_outcome",
        "idx_tmo_attempt_id",
    }
    assert triggers == {
        "trg_tma_no_update",
        "trg_tma_no_delete",
        "trg_tmo_no_update",
        "trg_tmo_no_delete",
    }


def test_partial_existing_or_incompatible_schema_fails_closed(tmp_path):
    path = tmp_path / "partial.db"
    with sqlite3.connect(path) as connection:
        connection.execute(REGISTRY_SQL)
        connection.execute("CREATE TABLE ticker_metadata_attempts (attempt_id INTEGER PRIMARY KEY)")

    with pytest.raises(MetadataBoundaryError) as captured:
        MetadataStore(path).initialize_schema()
    assert captured.value.code == "metadata_schema_incompatible"


def test_altered_existing_trigger_fails_exact_schema_revalidation(tmp_path):
    path, store = make_store(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER trg_tmo_no_delete")
        connection.execute(
            """
            CREATE TRIGGER trg_tmo_no_delete BEFORE DELETE ON ticker_metadata_observations
            BEGIN SELECT RAISE(ABORT, 'different contract'); END
            """
        )

    with pytest.raises(MetadataBoundaryError) as captured:
        store.initialize_schema()
    assert captured.value.code == "metadata_schema_incompatible"


def test_attempt_and_observation_commit_atomically_and_are_immutable(tmp_path):
    path, store = make_store(tmp_path)
    attempt, observation = records()
    receipt = store.record_attempt(attempt, observation)

    assert receipt.attempt_id == 1
    assert receipt.observation_id == 1
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        row = connection.execute(
            "SELECT requested_fields_json, observed_fields_json, outcome FROM ticker_metadata_attempts"
        ).fetchone()
        observed = connection.execute(
            "SELECT attempt_id, provider_symbol, short_name, present_fields_json FROM ticker_metadata_observations"
        ).fetchone()
        assert row == ('["currency","symbol"]', '["provider_symbol","short_name"]', "complete")
        assert observed == (1, "AAPL", "Apple", '["provider_symbol","short_name"]')
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE ticker_metadata_attempts SET detail='changed'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM ticker_metadata_observations")


def test_cardinality_validation_occurs_before_transaction(tmp_path):
    path, store = make_store(tmp_path)
    attempt, observation = records()

    with pytest.raises(ValueError, match="requires exactly one observation"):
        store.record_attempt(attempt, None)
    with pytest.raises(ValueError, match="must not have an observation"):
        store.record_attempt(
            replace(attempt, outcome=AcquisitionOutcome.NO_DATA), observation
        )

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ticker_metadata_attempts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM ticker_metadata_observations").fetchone()[0] == 0


def test_observation_failure_rolls_back_attempt(tmp_path):
    path, store = make_store(tmp_path)
    attempt, observation = records()
    bad_observation = replace(
        observation,
        projected={"market_cap": object()},
        present_fields=("market_cap",),
    )

    with pytest.raises(sqlite3.ProgrammingError, match="type.*not supported"):
        store.record_attempt(attempt, bad_observation)

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ticker_metadata_attempts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM ticker_metadata_observations").fetchone()[0] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"collector_git_revision": "different"},
        {"collector_dirty": True},
        {"python_version": "3.12.0"},
        {"provider_library_version": "different"},
        {"provider_observed_at_utc": datetime(2026, 8, 24, 14, 30, tzinfo=timezone.utc) + timedelta(seconds=1)},
        {"present_fields": ("provider_symbol",)},
    ],
)
def test_observation_must_copy_attempt_provenance_time_and_present_fields(tmp_path, change):
    path, store = make_store(tmp_path)
    attempt, observation = records()

    with pytest.raises(ValueError, match="linked attempt evidence"):
        store.record_attempt(attempt, replace(observation, **change))

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ticker_metadata_attempts").fetchone()[0] == 0


def test_selection_is_raw_id_ordered_includes_inactive_and_resumes_by_contract(tmp_path):
    _, store = make_store(tmp_path)
    initial = store.select_tickers(FilterSpec(), limit=2, retry_errored=False, contract_hash=REQUEST_CONTRACT_SHA256)
    assert tuple((item.raw_ticker_id, item.requested_symbol) for item in initial.tickers) == (
        (1, "AAPL"),
        (2, "OLD"),
    )
    assert initial.skipped_terminal == 0
    assert initial.filter_description == "(no filter — all registry tickers)"

    complete, observation = records(raw_ticker_id=1, symbol="AAPL")
    store.record_attempt(complete, observation)
    transient, _ = records(raw_ticker_id=2, symbol="OLD", outcome=AcquisitionOutcome.TRANSIENT)
    store.record_attempt(transient, None)
    no_data, _ = records(raw_ticker_id=3, symbol="MSFT", outcome=AcquisitionOutcome.NO_DATA)
    store.record_attempt(no_data, None)

    normal = store.select_tickers(FilterSpec(), limit=None, retry_errored=False, contract_hash=REQUEST_CONTRACT_SHA256)
    assert tuple(item.raw_ticker_id for item in normal.tickers) == (2,)
    assert normal.skipped_terminal == 2

    retry = store.select_tickers(FilterSpec(), limit=None, retry_errored=True, contract_hash=REQUEST_CONTRACT_SHA256)
    assert tuple(item.raw_ticker_id for item in retry.tickers) == (2, 3)
    assert retry.skipped_terminal == 1

    changed = store.select_tickers(FilterSpec(), limit=None, retry_errored=False, contract_hash="new-contract")
    assert tuple(item.raw_ticker_id for item in changed.tickers) == (1, 2, 3)


def test_filters_use_prerun_projection_without_forcing_active(tmp_path):
    path, store = make_store(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE tickers SET exchange='NYSE', sector='Legacy' WHERE id=2")
        connection.execute("UPDATE tickers SET exchange='NASDAQ', sector='Technology' WHERE id IN (1,3)")

    selected = store.select_tickers(
        FilterSpec(exchanges=("NYSE",), ticker_regex="^O"),
        limit=None,
        retry_errored=False,
        contract_hash=REQUEST_CONTRACT_SHA256,
    )
    assert tuple(item.requested_symbol for item in selected.tickers) == ("OLD",)
    assert selected.filter_description == "exchange IN (NYSE) AND ticker~/^O/"
