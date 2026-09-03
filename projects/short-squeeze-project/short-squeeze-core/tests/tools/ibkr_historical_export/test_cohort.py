"""Frozen cohort, boundary, and request-parameter invariants."""

from __future__ import annotations

from datetime import UTC, datetime

from tools.ibkr_historical_export import cohort
from tools.ibkr_historical_export.statuses import (
    REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND,
)

EXPECTED_ORDER = (
    "XNCR", "PESI", "SLS", "ZNTL", "GPRE", "SSPC", "LBGJ",
    "TRVI", "LMNX", "MGNX", "BHVN", "OBE", "AVTX",
    "KLRS", "SG",
)


def test_frozen_source_order_exact():
    assert cohort.FROZEN_SYMBOLS == EXPECTED_ORDER


def test_case_ids_exact():
    for symbol in EXPECTED_ORDER:
        assert cohort.CASE_IDS[symbol] == f"BATCH01_{symbol}_20260718"
    assert len(cohort.CASE_IDS) == 15


def test_frozen_boundary_values():
    assert cohort.FROZEN_BOUNDARY == datetime(2026, 7, 18, 13, 37, 55, 17661, tzinfo=UTC)
    assert cohort.FROZEN_FORWARD_END == datetime(2026, 7, 19, 13, 37, 55, 17661, tzinfo=UTC)


def test_request_a_parameters():
    a = cohort.REQUEST_A
    assert a.request_name == "DETECTION_CONTEXT_PRECEDING_24H"
    assert a.end_datetime == "20260718 13:37:55 UTC"
    assert a.duration_str == "86400 S"
    assert a.bar_size_setting == "1 min"
    assert a.what_to_show == "TRADES"
    assert a.use_rth == 0
    assert a.format_date == 2
    assert a.keep_up_to_date is False
    assert a.chart_options == []


def test_request_b_parameters():
    b = cohort.REQUEST_B
    assert b.request_name == "FROZEN_FORWARD_24H"
    assert b.end_datetime == "20260719 13:37:55 UTC"
    assert b.duration_str == "86400 S"
    assert b.what_to_show == "TRADES"
    assert b.use_rth == 0


def test_whole_second_truncation_recorded_and_applied():
    # The frozen boundary carries fractional seconds; the request uses whole seconds.
    assert cohort.FROZEN_BOUNDARY.microsecond == 17661
    assert cohort.REQUEST_A.end_datetime.endswith("13:37:55 UTC")
    assert REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND == "REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND"


def test_expected_windows_are_24h():
    a = cohort.REQUEST_A
    assert (a.expected_window_end - a.expected_window_start).total_seconds() == 86400
    b = cohort.REQUEST_B
    assert (b.expected_window_end - b.expected_window_start).total_seconds() == 86400
    # Request A ends at the boundary; Request B starts at the boundary.
    assert a.expected_window_end == cohort.FROZEN_BOUNDARY
    assert b.expected_window_start == cohort.FROZEN_BOUNDARY
