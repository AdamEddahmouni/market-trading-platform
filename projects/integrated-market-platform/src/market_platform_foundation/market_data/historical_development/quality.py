"""Data-quality report for historical development datasets."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from .rth_session import (
    RTH_MINUTES_FULL_SESSION,
    expected_rth_minute_keys,
    ohlc_row_valid,
    parse_moomoo_time_key_local,
)


def count_incomplete_final_bars(
    session_dates: Sequence[str],
    raw_rows: Sequence[Mapping[str, Any]],
) -> int:
    """Count session days missing the expected final RTH 1m bar (15:59 ET start)."""

    incomplete = 0
    for day in session_dates:
        expected = expected_rth_minute_keys(day)
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


def build_quality_report(
    *,
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
    missing_by_day: list[dict[str, Any]] = []
    for day in session_dates:
        expected = set(expected_rth_minute_keys(day))
        present: set[str] = set()
        for row in raw_rows:
            key = str(row.get("time_key") or "")
            if key.startswith(day):
                parsed = parse_moomoo_time_key_local(key)
                if parsed is not None:
                    present.add(parsed.strftime("%Y-%m-%d %H:%M:%S"))
        missing = sorted(expected - present)
        if missing:
            missing_by_day.append(
                {
                    "session_date": day,
                    "missing_minute_count": len(missing),
                    "sample_missing_time_keys": missing[:5],
                }
            )
    ordering_violations = 0
    last_ns: int | None = None
    for bar in normalized_bars:
        at = int(bar.get("available_time") or 0)
        if last_ns is not None and at < last_ns:
            ordering_violations += 1
        last_ns = at
    ohlc_invalid = sum(1 for row in raw_rows if not ohlc_row_valid(row))
    body: dict[str, Any] = {
        "artifact_kind": "historical_development_quality_report_v1",
        "row_count": len(normalized_bars),
        "raw_row_count": len(raw_rows),
        "expected_rth_minutes_per_full_session": RTH_MINUTES_FULL_SESSION,
        "session_date_count": len(session_dates),
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
    }
    body["quality_fingerprint"] = sha256_bytes(canonical_bytes(body))
    return body


__all__ = ["build_quality_report", "count_incomplete_final_bars"]
