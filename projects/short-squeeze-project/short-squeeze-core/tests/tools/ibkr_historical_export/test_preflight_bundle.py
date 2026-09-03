"""Honest Batch 04 preflight integration for IBKR bars."""

from __future__ import annotations

from datetime import UTC, datetime

from tools.ibkr_historical_export.cohort import REQUEST_A
from tools.ibkr_historical_export.preflight_bundle import (
    build_manifest,
    build_profile,
    run_bundle_preflight,
)
from tools.ibkr_historical_export.serialization import (
    serialize_bars_csv,
    sha256_and_length,
)
from tools.ibkr_historical_export.statuses import PreflightStatus

from ._fakes import make_bar

_NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def _csv_and_hash():
    bars = [make_bar("XNCR", "DETECTION_CONTEXT_PRECEDING_24H", 111, 1_784_000_000)]
    data = serialize_bars_csv(bars)
    sha, length = sha256_and_length(data)
    return data, sha, length


def test_ibkr_honest_unknowns_pass_preflight():
    data, sha, length = _csv_and_hash()
    outcome = run_bundle_preflight(
        bundle_id="B", symbol="XNCR", csv_bytes=data,
        artifact_relative_path="raw/XNCR-detection-context.csv",
        artifact_sha256=sha, artifact_byte_length=length,
        retrieval_time=_NOW, export_time=_NOW,
        expected_start_time=REQUEST_A.expected_window_start,
        expected_end_time=REQUEST_A.expected_window_end,
    )
    assert outcome.status is PreflightStatus.PREFLIGHT_READY
    assert "MISSING_ADJUSTMENT_SEMANTICS" not in outcome.reason_codes
    assert "MISSING_TIMESTAMP_SEMANTICS" not in outcome.reason_codes


def test_manifest_declares_adr_0066_semantics():
    manifest = build_manifest(
        bundle_id="B", symbol="XNCR",
        artifact_relative_path="raw/XNCR-detection-context.csv",
        artifact_sha256="0" * 64, artifact_byte_length=10,
        retrieval_time=_NOW, export_time=_NOW,
        expected_start_time=REQUEST_A.expected_window_start,
        expected_end_time=REQUEST_A.expected_window_end,
        profile_id="p",
    )
    assert manifest.provider_name == "Interactive Brokers"
    assert manifest.price_adjustment_semantics.value == "SPLIT_ADJUSTED"
    assert manifest.volume_adjustment_semantics.value == "UNKNOWN"
    assert manifest.timestamp_semantics.value == "UNKNOWN"
    assert manifest.value_authenticity.value == "VENDOR_SUPPLIED"
    assert manifest.data_time_basis.value == "HISTORICAL"


def test_profile_columns_match_csv_layout():
    profile = build_profile("B")
    assert profile.timestamp_column == "timestamp_utc"
    assert profile.open_column == "open"
    assert profile.volume_column == "volume"
    assert profile.vwap_column == "wap"
    assert profile.trade_count_column == "bar_count"


def test_report_never_performs_association_or_outcome():
    data, sha, length = _csv_and_hash()
    report = run_bundle_preflight(
        bundle_id="B", symbol="XNCR", csv_bytes=data,
        artifact_relative_path="raw/XNCR-detection-context.csv",
        artifact_sha256=sha, artifact_byte_length=length,
        retrieval_time=_NOW, export_time=_NOW,
        expected_start_time=REQUEST_A.expected_window_start,
        expected_end_time=REQUEST_A.expected_window_end,
    ).report
    assert report.case_association_performed is False
    assert report.outcome_capture_performed is False
    assert report.phase_3a_records_created is False
    assert report.phase_3b_records_created is False
    assert report.phase_3e_started is False
    assert report.ready_for_case_association is True
