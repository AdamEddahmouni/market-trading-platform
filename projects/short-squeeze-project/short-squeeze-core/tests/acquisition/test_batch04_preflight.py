"""Batch 04 offline preflight behavior, tooling, and safety-boundary tests."""

import hashlib
import json
from pathlib import Path

import pytest

from squeeze_core.acquisition.historical_data_submission_kit import (
    build_column_mapping_profile,
    build_invalid_scenario_index,
    build_valid_manifest,
    hash_file,
    run_preflight,
    run_preflight_from_bytes,
)
from squeeze_core.acquisition.historical_data_submission_kit.preflight import (
    PREFLIGHT_CONTRACT_VERSION,
    PreflightReport,
    PreflightStatus,
)
from squeeze_core.acquisition.historical_data_submission_kit.synthetic import RAW_CSV
from squeeze_core.acquisition.local_bar_intake.models import IntakeManifest
from squeeze_core.serialization import canonical_json_bytes


REQUIRED_REPORT_FIELDS = (
    "schema_version", "preflight_contract_version", "bundle_id", "artifact_id",
    "profile_id", "status", "reason_codes", "artifact_sha256", "artifact_byte_length",
    "provider_name", "provider_product_or_export_name", "user_entitlement_assertion",
    "retrieval_time", "export_time", "canonical_symbol", "provider_symbol",
    "market_or_venue", "bar_interval", "event_timezone", "timestamp_semantics",
    "session_coverage", "price_adjustment_semantics", "volume_adjustment_semantics",
    "expected_start_time", "expected_end_time", "observed_start_time",
    "observed_end_time", "normalized_bar_count", "rejected_row_count",
    "quarantined_row_count", "diagnostic_count", "ready_for_case_association",
    "case_association_performed", "outcome_capture_performed",
    "phase_3a_records_created", "phase_3b_records_created", "phase_3e_started",
)

CONSTANT_FALSE_FIELDS = (
    "case_association_performed", "outcome_capture_performed",
    "phase_3a_records_created", "phase_3b_records_created", "phase_3e_started",
)


def _bundle(tmp_path: Path) -> Path:
    from squeeze_core.serialization import canonical_json_bytes

    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "synthetic-bars.csv").write_bytes(RAW_CSV)
    (tmp_path / "manifest.json").write_bytes(
        canonical_json_bytes(build_valid_manifest()) + b"\n"
    )
    (tmp_path / "profile.json").write_bytes(
        canonical_json_bytes(build_column_mapping_profile()) + b"\n"
    )
    return tmp_path


def test_synthetic_valid_example_passes_preflight():
    report = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), RAW_CSV
    )
    assert report.status is PreflightStatus.READY_FOR_FUTURE_ASSOCIATION
    assert report.normalized_bar_count == 6
    assert report.ready_for_case_association is True
    assert report.preflight_contract_version == PREFLIGHT_CONTRACT_VERSION


def test_preflight_report_has_all_required_fields():
    report = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), RAW_CSV
    )
    payload = json.loads(
        (Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "acquisition"
         / "batch04" / "synthetic-valid-preflight-report.json").read_text()
    )
    for field in REQUIRED_REPORT_FIELDS:
        assert field in payload, field
    # Model exposes the same fields.
    for field in REQUIRED_REPORT_FIELDS:
        assert hasattr(report, field), field


def test_constant_false_booleans_are_always_false():
    report = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), RAW_CSV
    )
    for field in CONSTANT_FALSE_FIELDS:
        assert getattr(report, field) is False, field


def test_ready_flag_only_true_when_status_ready():
    ready = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), RAW_CSV
    )
    assert ready.ready_for_case_association is True
    missing = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), None
    )
    assert missing.status is PreflightStatus.NOT_READY_REJECTED
    assert missing.ready_for_case_association is False


def test_explicit_nulls_when_no_bars_are_normalized():
    report = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), None
    )
    assert report.observed_start_time is None
    assert report.observed_end_time is None
    assert report.normalized_bar_count == 0


def test_report_contains_no_absolute_path(tmp_path):
    root = _bundle(tmp_path)
    manifest = build_valid_manifest()
    profile = build_column_mapping_profile()
    report = run_preflight(root, manifest, profile)
    blob = canonical_json_bytes(report).decode("utf-8")
    assert str(tmp_path) not in blob
    assert ":\\" not in blob and "/tmp/" not in blob


def test_raw_artifact_is_byte_identical_before_and_after_preflight(tmp_path):
    root = _bundle(tmp_path)
    raw = root / "raw" / "synthetic-bars.csv"
    before = raw.read_bytes()
    run_preflight(root, build_valid_manifest(), build_column_mapping_profile())
    assert raw.read_bytes() == before == RAW_CSV


def test_hash_file_matches_hashlib_and_byte_length(tmp_path):
    target = tmp_path / "sample.csv"
    target.write_bytes(RAW_CSV)
    result = hash_file(target)
    assert result["sha256"] == hashlib.sha256(RAW_CSV).hexdigest()
    assert result["byte_length"] == len(RAW_CSV)
    assert result["file_name"] == "sample.csv"
    assert str(tmp_path) not in json.dumps(result)


def test_line_ending_change_produces_a_different_hash():
    crlf = RAW_CSV.replace(b"\n", b"\r\n")
    assert crlf != RAW_CSV
    assert hashlib.sha256(crlf).hexdigest() != hashlib.sha256(RAW_CSV).hexdigest()
    # A CRLF copy no longer matches the declared LF hash, so preflight rejects it.
    report = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), crlf
    )
    assert report.status is PreflightStatus.NOT_READY_REJECTED


def test_preflight_report_is_deterministic():
    a = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), RAW_CSV
    )
    b = run_preflight_from_bytes(
        build_valid_manifest(), build_column_mapping_profile(), RAW_CSV
    )
    assert a.deterministic_id == b.deterministic_id


def test_preflight_accepts_no_case_registry_inputs():
    # The preflight functions take only (root/bytes, manifest, profile): there is no
    # parameter through which a case id, boundary id, or outcome could be supplied.
    import inspect

    params = set(inspect.signature(run_preflight).parameters)
    assert params == {"root", "manifest", "profile"}
    from_bytes = set(inspect.signature(run_preflight_from_bytes).parameters)
    assert from_bytes == {"manifest", "profile", "content"}


@pytest.mark.parametrize(
    "scenario",
    [s["scenario"] for s in build_invalid_scenario_index()["executed_scenarios"]],
)
def test_every_executed_invalid_scenario_is_not_ready(scenario):
    index = {s["scenario"]: s for s in build_invalid_scenario_index()["executed_scenarios"]}
    entry = index[scenario]
    assert entry["preflight_status"] in {
        PreflightStatus.NOT_READY_REJECTED.value,
        PreflightStatus.NOT_READY_QUARANTINED.value,
    }


def test_key_invalid_scenarios_map_to_expected_reason_codes():
    index = {s["scenario"]: s for s in build_invalid_scenario_index()["executed_scenarios"]}
    expected = {
        "missing_raw_artifact": "ARTIFACT_MISSING",
        "incorrect_byte_length": "ARTIFACT_BYTE_LENGTH_MISMATCH",
        "incorrect_sha256": "ARTIFACT_SHA256_MISMATCH",
        "unsupported_encoding": "UNSUPPORTED_ENCODING",
        "unsupported_format": "UNSUPPORTED_FORMAT",
        "unknown_timezone": "UNKNOWN_TIMEZONE",
        "unsupported_interval": "UNSUPPORTED_INTERVAL",
        "missing_timestamp_semantics": "MISSING_TIMESTAMP_SEMANTICS",
        "missing_adjustment_semantics": "MISSING_ADJUSTMENT_SEMANTICS",
        "contradictory_adjustment_semantics": "CONTRADICTORY_ADJUSTMENT_SEMANTICS",
        "current_value_as_historical": "CURRENT_VALUE_AS_HISTORICAL",
        "synthetic_value_as_historical": "SYNTHETIC_VALUE_AS_HISTORICAL",
        "symbol_mismatch": "SYMBOL_MISMATCH",
        "venue_mismatch": "MARKET_VENUE_MISMATCH",
        "malformed_decimal": "MALFORMED_DECIMAL",
        "nan_or_infinity": "NAN_OR_INFINITY",
        "missing_ohlc_value": "MISSING_OHLC_VALUE",
        "negative_volume": "NEGATIVE_VOLUME",
        "negative_trade_count": "NEGATIVE_TRADE_COUNT",
        "invalid_ohlc_relationship": "INVALID_OHLC_RELATIONSHIP",
        "event_time_outside_coverage": "EVENT_TIME_OUTSIDE_COVERAGE",
        "conflicting_duplicate_bar": "CONFLICTING_DUPLICATE_BAR",
        "overlapping_bars": "OVERLAPPING_BARS",
        "non_monotonic_order": "NON_MONOTONIC_ORDER",
        "coverage_gap": "COVERAGE_GAP",
    }
    for scenario, code in expected.items():
        assert scenario in index, scenario
        assert code in index[scenario]["reason_codes"], scenario


def test_documented_scenarios_cover_environment_limited_and_load_time_barriers():
    documented = {
        s["scenario"]: s
        for s in build_invalid_scenario_index()["documented_scenarios"]
    }
    for scenario in (
        "malformed_manifest", "missing_interval", "ambiguous_timezone",
        "nonexistent_local_time", "absolute_path_in_identity",
        "attempted_case_association_in_batch_04",
    ):
        assert scenario in documented, scenario
        assert documented[scenario]["evaluation"] == "DOCUMENTED_ONLY"
        assert documented[scenario]["expected_reason_code"]


def test_absolute_path_is_rejected_at_manifest_load():
    manifest = build_valid_manifest()
    data = json.loads(canonical_json_bytes(manifest).decode("utf-8"))
    data["artifact_relative_path"] = "C:\\Users\\someone\\raw.csv"
    data["deterministic_id"] = None
    with pytest.raises(Exception):
        IntakeManifest.model_validate(data)
