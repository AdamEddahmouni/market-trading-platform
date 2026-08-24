import hashlib
import json

import pytest

from src.acquisition import AcquisitionOutcome
from src.ticker_metadata.contract import (
    ALLOWLIST,
    REQUEST_CONTRACT_JSON,
    REQUEST_CONTRACT_SHA256,
    REQUEST_CONTRACT_VERSION,
    classify_exception,
    classify_response,
)


EXPECTED_KEYS = (
    "symbol",
    "shortName",
    "longName",
    "exchange",
    "fullExchangeName",
    "quoteType",
    "currency",
    "sector",
    "industry",
    "country",
    "marketCap",
)


def test_request_contract_is_canonical_complete_and_self_identifying():
    decoded = json.loads(REQUEST_CONTRACT_JSON)
    assert REQUEST_CONTRACT_JSON == json.dumps(
        decoded, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert REQUEST_CONTRACT_SHA256 == hashlib.sha256(
        REQUEST_CONTRACT_JSON.encode("utf-8")
    ).hexdigest()
    assert decoded["version"] == REQUEST_CONTRACT_VERSION
    assert tuple(decoded["allowlisted_provider_keys"]) == EXPECTED_KEYS
    assert ALLOWLIST == EXPECTED_KEYS
    assert decoded["provider"] == "yfinance"
    assert decoded["method"] == "get_info"
    assert decoded["outcome_classification_version"] == "1"
    assert decoded["validators"]["marketCap"]["maximum"] == 2**63 - 1


def test_complete_response_trims_strings_preserves_unicode_and_ignores_unknowns():
    result = classify_response(
        " brk.b ",
        {
            "symbol": "BRK-B",
            "shortName": "  Société Berkshire  ",
            "exchange": " NYQ ",
            "quoteType": " EQUITY ",
            "currency": "USD",
            "marketCap": 0,
            "longBusinessSummary": "must never be retained",
            "website": "https://secret.example/?token=nope",
        },
    )

    assert result.outcome is AcquisitionOutcome.COMPLETE
    assert result.reason_code == "identity_envelope_complete"
    assert result.projected == {
        "provider_symbol": "BRK-B",
        "short_name": "Société Berkshire",
        "exchange_code": "NYQ",
        "quote_type": "EQUITY",
        "currency": "USD",
        "market_cap": 0,
    }
    assert result.observed_fields == (
        "currency",
        "exchange_code",
        "market_cap",
        "provider_symbol",
        "quote_type",
        "short_name",
    )
    assert result.observed_provider_fields == (
        "currency",
        "exchange",
        "marketCap",
        "quoteType",
        "shortName",
        "symbol",
    )
    assert "secret" not in repr(result)


def test_partial_and_no_data_are_distinct():
    partial = classify_response("AAPL", {"sector": "Technology", "unknown": 1})
    assert partial.outcome is AcquisitionOutcome.PARTIAL_RESPONSE
    assert partial.reason_code == "identity_envelope_incomplete"
    assert partial.projected == {"sector": "Technology"}

    assert classify_response("AAPL", {}).outcome is AcquisitionOutcome.NO_DATA
    assert classify_response("AAPL", {"unknown": "value"}).outcome is AcquisitionOutcome.NO_DATA

    observed_null = classify_response("AAPL", {"sector": None, "unknown": "value"})
    assert observed_null.outcome is AcquisitionOutcome.NO_DATA
    assert observed_null.observed_provider_fields == ("sector",)


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ([], "top_level_not_mapping"),
        ({"symbol": "MSFT", "shortName": "Apple", "exchange": "NMS", "quoteType": "EQUITY"}, "provider_symbol_mismatch"),
        ({"symbol": "AAPL", "shortName": True}, "invalid_shortName"),
        ({"symbol": "AAPL", "marketCap": True}, "invalid_marketCap"),
        ({"symbol": "AAPL", "marketCap": -1}, "invalid_marketCap"),
        ({"symbol": "AAPL", "marketCap": 2**63}, "invalid_marketCap"),
        ({"symbol": "AAPL", "sector": "Tech\nInjected"}, "invalid_sector"),
        ({"symbol": "AAPL", "shortName": "x" * 513}, "invalid_shortName"),
    ],
)
def test_invalid_observed_values_fail_closed_as_schema_drift(payload, reason):
    result = classify_response("AAPL", payload)
    assert result.outcome is AcquisitionOutcome.SCHEMA_DRIFT
    assert result.reason_code == reason
    assert result.projected == {}


@pytest.mark.parametrize(
    ("exc", "outcome", "reason"),
    [
        (RuntimeError("HTTP 429 too many requests"), AcquisitionOutcome.THROTTLED, "provider_rate_limited"),
        (ValueError("possibly delisted; no timezone found"), AcquisitionOutcome.INVALID_SYMBOL, "provider_invalid_symbol"),
        (TimeoutError("timed out"), AcquisitionOutcome.TRANSIENT, "provider_timeout"),
        (ConnectionError("connection reset"), AcquisitionOutcome.TRANSIENT, "provider_connection_error"),
        (RuntimeError("temporary provider outage"), AcquisitionOutcome.TRANSIENT, "unknown_exception"),
    ],
)
def test_exception_classification_is_stable_and_does_not_retain_messages(exc, outcome, reason):
    result = classify_exception(exc)
    assert result.outcome is outcome
    assert result.reason_code == reason
    assert result.projected == {}
    assert result.observed_fields == ()
    assert str(exc) not in (result.detail or "")
    assert result.detail == type(exc).__name__
