from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.acquisition import AcquisitionOutcome, safe_error_detail
from src.ticker_metadata.provenance import collect_provenance
from src.ticker_metadata.provider import YFinanceMetadataAdapter


class SequenceClock:
    def __init__(self):
        self.current = datetime(2026, 8, 24, 14, 0, tzinfo=timezone.utc)

    def __call__(self):
        value = self.current
        self.current += timedelta(seconds=1)
        return value


class GuardedTicker:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_info(self):
        self.calls.append("get_info")
        return self.payload

    def __getattr__(self, name):
        raise AssertionError(f"forbidden yfinance access: {name}")


def test_adapter_constructs_one_ticker_and_calls_only_get_info_once():
    ticker = GuardedTicker(
        {"symbol": "AAPL", "shortName": "Apple", "exchange": "NMS", "quoteType": "EQUITY"}
    )
    constructed = []

    def factory(symbol):
        constructed.append(symbol)
        return ticker

    result = YFinanceMetadataAdapter(ticker_factory=factory, utcnow=SequenceClock()).call(
        "AAPL", ordinal=2
    )

    assert constructed == ["AAPL"]
    assert ticker.calls == ["get_info"]
    assert result.ordinal == 2
    assert result.started_at_utc.isoformat() == "2026-08-24T14:00:00+00:00"
    assert result.completed_at_utc.isoformat() == "2026-08-24T14:00:01+00:00"
    assert result.classified.outcome is AcquisitionOutcome.COMPLETE
    assert not hasattr(result, "payload")
    assert "longBusinessSummary" not in repr(result)


def test_adapter_classifies_exception_without_retaining_arbitrary_message():
    class FailingTicker:
        def get_info(self):
            raise RuntimeError("HTTP 429 Authorization: Bearer super-secret")

    result = YFinanceMetadataAdapter(
        ticker_factory=lambda symbol: FailingTicker(), utcnow=SequenceClock()
    ).call("BAD", ordinal=1)

    assert result.classified.outcome is AcquisitionOutcome.THROTTLED
    assert result.classified.reason_code == "provider_rate_limited"
    assert result.classified.detail == "RuntimeError"
    assert "super-secret" not in repr(result)


def test_adapter_does_not_swallow_process_interrupts():
    class InterruptedTicker:
        def get_info(self):
            raise KeyboardInterrupt

    adapter = YFinanceMetadataAdapter(
        ticker_factory=lambda symbol: InterruptedTicker(), utcnow=SequenceClock()
    )
    with pytest.raises(KeyboardInterrupt):
        adapter.call("AAPL", ordinal=1)


def test_default_factory_is_late_and_uses_yfinance_ticker():
    ticker = GuardedTicker({})
    with patch("yfinance.Ticker", return_value=ticker) as factory:
        result = YFinanceMetadataAdapter(utcnow=SequenceClock()).call("NONE", ordinal=1)
    factory.assert_called_once_with("NONE")
    assert result.classified.outcome is AcquisitionOutcome.NO_DATA


def test_provenance_is_bounded_to_declared_fields(tmp_path):
    completed = {
        ("rev-parse", "HEAD"): "abc123\n",
        ("status", "--porcelain"): " M src/file.py\n",
    }

    def git(args, cwd):
        assert cwd == tmp_path
        return completed[tuple(args)]

    with patch("src.ticker_metadata.provenance.metadata.version", return_value="1.6.0"):
        provenance = collect_provenance(tmp_path, git_runner=git)

    assert provenance.collector_git_revision == "abc123"
    assert provenance.collector_dirty is True
    assert provenance.python_version
    assert provenance.provider_library_name == "yfinance"
    assert provenance.provider_library_version == "1.6.0"


def test_provenance_fails_closed_to_unknown_without_leaking_command_errors(tmp_path):
    def fail(args, cwd):
        raise RuntimeError("C:/Users/alice/token=secret")

    with patch("src.ticker_metadata.provenance.metadata.version", side_effect=LookupError):
        provenance = collect_provenance(tmp_path, git_runner=fail)
    assert provenance.collector_git_revision == "unknown"
    assert provenance.collector_dirty is True
    assert provenance.provider_library_version == "unknown"
    assert "alice" not in repr(provenance)


def test_safe_error_detail_removes_secrets_urls_profiles_controls_and_bounds():
    exc = RuntimeError(
        "Authorization: Bearer abc123 cookie=session-secret "
        "https://example.test/path?token=query-secret "
        "C:\\Users\\alice\\project\\file.py api_key=key-secret\n" + "x" * 1000
    )
    detail = safe_error_detail(exc)

    for forbidden in (
        "abc123",
        "session-secret",
        "query-secret",
        "alice",
        "key-secret",
        "\n",
    ):
        assert forbidden not in detail
    assert "[REDACTED]" in detail
    assert len(detail) <= 500
