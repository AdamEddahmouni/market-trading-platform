"""Data-quality report for historical development datasets."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from .rth_session import (
    RTH_MINUTES_FULL_SESSION,
    UsEquitySessionDayKind,
    classify_us_equity_session_day,
    count_us_equity_holidays_in_range,
    expected_rth_minute_keys,
    ohlc_row_valid,
    parse_moomoo_time_key_local,
)


def _missing_intervals_for_sessions(
    session_dates: Sequence[str],
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    early_closes: frozenset[str],
) -> list[dict[str, Any]]:
    missing_by_day: list[dict[str, Any]] = []
    for day in session_dates:
        expected = set(expected_rth_minute_keys(day, early_closes=early_closes))
        present: set[str] = set()
        for row in raw_rows:
            key = str(row.get("time_key") or "")
            if key.startswith(day):
                parsed = parse_moomoo_time_key_local(key)
                if parsed is not None:
                    present.add(parsed.strftime("%Y-%m-%d %H:%M:%S"))
        missing = sorted(expected - present)
        if missing:
            kind = classify_us_equity_session_day(day, early_closes=early_closes)
            missing_by_day.append(
                {
                    "session_date": day,
                    "session_kind": kind.value,
                    "expected_minute_count": len(expected),
                    "missing_minute_count": len(missing),
                    "sample_missing_time_keys": missing[:5],
                }
            )
    return missing_by_day


def _session_summaries(
    session_dates: Sequence[str],
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    holidays: frozenset[str],
    early_closes: frozenset[str],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for day in session_dates:
        expected_keys = expected_rth_minute_keys(day, early_closes=early_closes)
        present: set[str] = set()
        for row in raw_rows:
            key = str(row.get("time_key") or "")
            if not key.startswith(day):
                continue
            parsed = parse_moomoo_time_key_local(key)
            if parsed is not None:
                present.add(parsed.strftime("%Y-%m-%d %H:%M:%S"))
        kind = classify_us_equity_session_day(day, holidays=holidays, early_closes=early_closes)
        summaries.append(
            {
                "session_date": day,
                "session_kind": kind.value,
                "expected_minute_count": len(expected_keys),
                "observed_minute_count": len(present),
            }
        )
    return summaries


def _raw_time_key_ordering_violations(raw_rows: Sequence[Mapping[str, Any]]) -> int:
    last_key: str | None = None
    violations = 0
    for row in raw_rows:
        parsed = parse_moomoo_time_key_local(str(row.get("time_key") or ""))
        if parsed is None:
            continue
        key = parsed.strftime("%Y-%m-%d %H:%M:%S")
        if last_key is not None and key < last_key:
            violations += 1
        last_key = key
    return violations


def count_incomplete_final_bars(
    session_dates: Sequence[str],
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    early_closes: frozenset[str] = frozenset(),
) -> int:
    """Count session days missing the expected final RTH 1m bar for that session kind."""

    incomplete = 0
    for day in session_dates:
        expected = expected_rth_minute_keys(day, early_closes=early_closes)
        if not expected:
            continue
        final_key = expected[-1]
        found_final = False
        for row in raw_rows:
            key = str(row.get("time_key") or "")
            if not key.startswith(day):
                continue
            parsed = parse_moomoo_time_key_local(key)
            if parsed is not None and parsed.strftime("%Y-%m-%d %H:%M:%S") == final_key:
                found_final = True
                break
        if not found_final:
            incomplete += 1
    return incomplete


def _derive_quality_status(
    *,
    missing_rows: int,
    duplicate_rows: int,
    out_of_order_rows: int,
    malformed_rows: int,
    invalid_ohlc_rows: int,
    incomplete_rows: int,
    provider_gap_intervals: int,
) -> str:
    if malformed_rows > 0 or invalid_ohlc_rows > 0:
        return "FAIL"
    if (
        missing_rows > 0
        or incomplete_rows > 0
        or duplicate_rows > 0
        or out_of_order_rows > 0
        or provider_gap_intervals > 0
    ):
        return "WARN"
    return "PASS"


def build_quality_report(
    *,
    start_date: str,
    end_date: str,
    session_dates: Sequence[str],
    raw_rows: Sequence[Mapping[str, Any]],
    normalized_bars: Sequence[Mapping[str, Any]],
    duplicate_row_count: int,
    excluded_row_count: int,
    malformed_timestamp_count: int,
    outside_session_count: int,
    incomplete_final_bar_count: int,
    provider_gap_pages: int,
    holidays: Sequence[str],
    early_closes: Sequence[str],
    corporate_action_status: str,
    volume_anomaly_count: int,
) -> dict[str, Any]:
    holiday_set = frozenset(holidays)
    early_close_set = frozenset(early_closes)
    missing_by_day = _missing_intervals_for_sessions(
        session_dates,
        raw_rows,
        early_closes=early_close_set,
    )
    missing_rows = sum(item["missing_minute_count"] for item in missing_by_day)
    expected_rows = sum(
        len(expected_rth_minute_keys(day, early_closes=early_close_set)) for day in session_dates
    )
    observed_rows = len(normalized_bars)
    ordering_violations = 0
    last_ns: int | None = None
    for bar in normalized_bars:
        at = int(bar.get("available_time") or 0)
        if last_ns is not None and at < last_ns:
            ordering_violations += 1
        last_ns = at
    ohlc_invalid = sum(1 for row in raw_rows if not ohlc_row_valid(row))
    short_session_count = sum(
        1
        for day in session_dates
        if classify_us_equity_session_day(day, holidays=holiday_set, early_closes=early_close_set)
        == UsEquitySessionDayKind.EARLY_CLOSE
    )
    holiday_count = count_us_equity_holidays_in_range(
        start_date,
        end_date,
        holidays=holiday_set,
    )
    session_summaries = _session_summaries(
        session_dates,
        raw_rows,
        holidays=holiday_set,
        early_closes=early_close_set,
    )
    raw_ordering_violations = _raw_time_key_ordering_violations(raw_rows)
    quality_status = _derive_quality_status(
        missing_rows=missing_rows,
        duplicate_rows=int(duplicate_row_count),
        out_of_order_rows=ordering_violations + raw_ordering_violations,
        malformed_rows=int(malformed_timestamp_count),
        invalid_ohlc_rows=int(ohlc_invalid),
        incomplete_rows=int(incomplete_final_bar_count),
        provider_gap_intervals=int(provider_gap_pages),
    )
    body: dict[str, Any] = {
        "artifact_kind": "historical_development_quality_report_v1",
        "requested_sessions": len(session_dates),
        "actual_sessions": len(session_dates),
        "expected_rows": int(expected_rows),
        "observed_rows": int(observed_rows),
        "missing_rows": int(missing_rows),
        "duplicate_rows": int(duplicate_row_count),
        "out_of_order_rows": int(ordering_violations),
        "malformed_rows": int(malformed_timestamp_count),
        "outside_session_rows": int(outside_session_count),
        "incomplete_rows": int(incomplete_final_bar_count),
        "invalid_ohlc_rows": int(ohlc_invalid),
        "volume_anomalies": int(volume_anomaly_count),
        "provider_gap_intervals": int(provider_gap_pages),
        "short_session_count": int(short_session_count),
        "holiday_count": int(holiday_count),
        "quality_status": quality_status,
        "row_count": len(normalized_bars),
        "raw_row_count": len(raw_rows),
        "expected_rth_minutes_per_full_session": RTH_MINUTES_FULL_SESSION,
        "session_date_count": len(session_dates),
        "session_dates": list(session_dates),
        "session_summaries": session_summaries,
        "raw_time_key_ordering_violations": int(raw_ordering_violations),
        "missing_intervals": missing_by_day,
        "duplicate_row_count": int(duplicate_row_count),
        "excluded_row_count": int(excluded_row_count),
        "malformed_timestamp_count": int(malformed_timestamp_count),
        "bars_outside_session_count": int(outside_session_count),
        "ohlc_validity_violation_count": int(ohlc_invalid),
        "ordering_violation_count": int(ordering_violations),
        "incomplete_final_bar_count": int(incomplete_final_bar_count),
        "provider_gap_pages": int(provider_gap_pages),
        "volume_anomaly_count": int(volume_anomaly_count),
        "holiday_dates_declared": list(holidays),
        "early_close_dates_declared": list(early_closes),
        "corporate_action_status": corporate_action_status,
        "forward_fill_applied": False,
        "transformations": [
            "provider_fetch",
            "rth_filter",
            "dedupe",
            "normalize_moomoo_kline_row",
        ],
        "exclusions": {
            "outside_session_rows": int(outside_session_count),
            "invalid_ohlc_rows": int(ohlc_invalid),
            "malformed_timestamp_rows": int(malformed_timestamp_count),
        },
    }
    body["quality_fingerprint"] = sha256_bytes(canonical_bytes(body))
    return body


__all__ = ["build_quality_report", "count_incomplete_final_bars"]
