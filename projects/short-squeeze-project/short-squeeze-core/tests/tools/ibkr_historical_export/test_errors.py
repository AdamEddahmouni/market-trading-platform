"""IBKR error-code classification."""

from __future__ import annotations

from tools.ibkr_historical_export.errors import (
    classify_historical_error,
    is_disconnect,
    is_no_data_empty,
    is_request_ending,
    is_transient,
)
from tools.ibkr_historical_export.statuses import HistoricalStatus


def test_farm_notifications_do_not_end_requests():
    for code in (2104, 2106, 2107, 2158, 1102):
        assert is_request_ending(code) is False


def test_real_errors_end_requests():
    for code in (162, 200, 354, 321, 10197):
        assert is_request_ending(code) is True


def test_permission_denied_classification():
    assert classify_historical_error(354, "not subscribed") is HistoricalStatus.HISTORICAL_PERMISSION_DENIED
    assert classify_historical_error(10197, "no market data") is HistoricalStatus.HISTORICAL_PERMISSION_DENIED


def test_data_unavailable_classification():
    assert classify_historical_error(200, "No security definition") is HistoricalStatus.HISTORICAL_DATA_UNAVAILABLE
    assert classify_historical_error(321, "bad query") is HistoricalStatus.HISTORICAL_DATA_UNAVAILABLE


def test_no_data_162_is_empty_not_error():
    assert is_no_data_empty(162, "HMDS query returned no data") is True
    assert classify_historical_error(162, "HMDS query returned no data") is HistoricalStatus.SUCCESS_EMPTY


def test_162_with_other_message_is_unavailable():
    assert is_no_data_empty(162, "pacing violation") is False
    assert classify_historical_error(162, "some other problem") is HistoricalStatus.HISTORICAL_DATA_UNAVAILABLE


def test_unknown_code_is_generic_error():
    assert classify_historical_error(99999, "weird") is HistoricalStatus.HISTORICAL_REQUEST_ERROR


def test_transient_codes():
    assert is_transient(1100) is True
    assert is_transient(354) is False


def test_disconnect_codes():
    assert is_disconnect(1100) is True
    assert is_disconnect(1102) is False
