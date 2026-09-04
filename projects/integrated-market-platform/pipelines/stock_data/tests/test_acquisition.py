from datetime import datetime, timezone

from sqlalchemy import text

from src import database
from src.acquisition import AcquisitionOutcome, classify_failure


def test_failure_classification_is_stable():
    assert classify_failure(None, empty=True) is AcquisitionOutcome.NO_DATA
    assert classify_failure(TimeoutError("timed out")) is AcquisitionOutcome.TRANSIENT
    assert (
        classify_failure(RuntimeError("HTTP 429 too many requests"))
        is AcquisitionOutcome.THROTTLED
    )
    assert (
        classify_failure(ValueError("possibly delisted; no timezone found"))
        is AcquisitionOutcome.INVALID_SYMBOL
    )
    assert classify_failure(KeyError("Adj Close")) is AcquisitionOutcome.SCHEMA_DRIFT
    assert classify_failure(None, partial=True) is AcquisitionOutcome.PARTIAL_RESPONSE


def test_success_is_explicit():
    assert classify_failure(None) is AcquisitionOutcome.COMPLETE


def test_attempts_are_append_only_and_latest_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "attempts.sqlite3")
    database._engine = None
    database._metadata = None
    database.init_database()
    now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    first = database.record_attempt(
        "prices",
        "TEST",
        "transient",
        now,
        now,
        detail="timeout",
    )
    second = database.record_attempt("prices", "TEST", "complete", now, now)
    assert second > first
    with database.get_connection() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM acquisition_attempts")
        ).scalar_one()
    assert count == 2
    assert database.latest_attempt("prices", "TEST")["outcome"] == "complete"
    database.get_engine().dispose()
    database._engine = None
    database._metadata = None
