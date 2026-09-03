"""Offline CLI tests for the batch 03 local bar-intake subcommands."""

import json
from pathlib import Path

from squeeze_core.__main__ import main
from squeeze_core.acquisition.batch03 import (
    _RAW_CSV,
    build_case_association_mapping,
    build_column_mapping_profile,
    build_valid_manifest,
)
from squeeze_core.serialization import canonical_json_bytes


def _bundle(tmp_path: Path) -> Path:
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "valid-bars.csv").write_bytes(_RAW_CSV)
    (tmp_path / "manifest.json").write_bytes(canonical_json_bytes(build_valid_manifest()) + b"\n")
    (tmp_path / "profile.json").write_bytes(
        canonical_json_bytes(build_column_mapping_profile()) + b"\n"
    )
    (tmp_path / "mapping.json").write_bytes(
        canonical_json_bytes(build_case_association_mapping()) + b"\n"
    )
    return tmp_path


def test_cli_validate_bundle_accepts_valid_bundle(tmp_path, capsys):
    root = _bundle(tmp_path)
    code = main([
        "intake-validate-bundle", "--root", str(root),
        "--manifest", str(root / "manifest.json"),
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ACCEPTED"


def test_cli_validate_bundle_rejects_tampered_artifact(tmp_path, capsys):
    root = _bundle(tmp_path)
    (root / "raw" / "valid-bars.csv").write_bytes(_RAW_CSV + b"tampered\n")
    code = main([
        "intake-validate-bundle", "--root", str(root),
        "--manifest", str(root / "manifest.json"),
    ])
    assert code == 1
    payload = json.loads(capsys.readouterr().err)
    assert "ARTIFACT_SHA256_MISMATCH" in payload["reason_codes"]


def test_cli_inspect_artifact_reports_hashes(tmp_path, capsys):
    root = _bundle(tmp_path)
    code = main([
        "intake-inspect-artifact", "--root", str(root),
        "--manifest", str(root / "manifest.json"),
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["actual_sha256"] == payload["expected_sha256"]
    assert payload["relative_path"] == "raw/valid-bars.csv"


def test_cli_normalize_bars_writes_deterministic_outputs(tmp_path):
    root = _bundle(tmp_path)
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    for out in (out1, out2):
        assert main([
            "intake-normalize-bars", "--root", str(root),
            "--manifest", str(root / "manifest.json"),
            "--profile", str(root / "profile.json"), "--output", str(out),
        ]) == 0
    for name in ("normalized-bars.jsonl", "normalized-bars.csv", "normalization-diagnostics.json"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes(), name
    # Byte-identical to the committed fixtures.
    fixtures = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "acquisition" / "batch03"
    for name in ("normalized-bars.jsonl", "normalized-bars.csv"):
        assert (out1 / name).read_bytes() == (fixtures / name).read_bytes(), name


def test_cli_summary_outputs_event_and_retrieval_times(tmp_path, capsys):
    root = _bundle(tmp_path)
    code = main([
        "intake-summary", "--root", str(root),
        "--manifest", str(root / "manifest.json"), "--profile", str(root / "profile.json"),
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["normalized_bar_count"] == 6
    assert payload["event_start_min"] != payload["retrieval_time"]


def test_cli_case_association_valid_and_invalid(tmp_path, capsys):
    root = _bundle(tmp_path)
    assert main([
        "intake-validate-case-association", "--mapping", str(root / "mapping.json"),
        "--manifest", str(root / "manifest.json"),
        "--known-case-id", "DEMO_CASE_ZZAA_5M",
        "--known-boundary-id", "DEMO_BOUNDARY_ZZAA_5M",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True and payload["outcome_computed"] is False

    # Unknown references -> invalid, non-zero exit.
    assert main([
        "intake-validate-case-association", "--mapping", str(root / "mapping.json"),
    ]) == 1
    err = json.loads(capsys.readouterr().err)
    assert "UNKNOWN_CASE_ID" in err["reason_codes"]


def test_cli_malformed_manifest_returns_error(tmp_path, capsys):
    root = _bundle(tmp_path)
    (root / "bad.json").write_text('{"bundle_id": "x"}', encoding="utf-8")
    code = main([
        "intake-validate-bundle", "--root", str(root), "--manifest", str(root / "bad.json"),
    ])
    assert code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["valid"] is False
