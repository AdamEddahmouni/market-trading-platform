"""Offline CLI tests for the Batch 04 submission-kit subcommands."""

import hashlib
import json
from pathlib import Path

from squeeze_core.__main__ import main
from squeeze_core.acquisition.historical_data_submission_kit import (
    build_batch04_fixtures,
    build_column_mapping_profile,
    build_submission_kit,
    build_valid_manifest,
)
from squeeze_core.acquisition.historical_data_submission_kit.synthetic import RAW_CSV
from squeeze_core.serialization import canonical_json_bytes


def _bundle(tmp_path: Path) -> Path:
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "synthetic-bars.csv").write_bytes(RAW_CSV)
    (tmp_path / "manifest.json").write_bytes(canonical_json_bytes(build_valid_manifest()) + b"\n")
    (tmp_path / "profile.json").write_bytes(
        canonical_json_bytes(build_column_mapping_profile()) + b"\n"
    )
    return tmp_path


def test_cli_hash_matches_hashlib(tmp_path, capsys):
    target = tmp_path / "sample.csv"
    target.write_bytes(RAW_CSV)
    assert main(["historical-bar-hash", "--file", str(target)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sha256"] == hashlib.sha256(RAW_CSV).hexdigest()
    assert payload["byte_length"] == len(RAW_CSV)


def test_cli_preflight_ready_bundle(tmp_path, capsys):
    root = _bundle(tmp_path)
    code = main([
        "historical-bar-preflight", "--root", str(root),
        "--manifest", str(root / "manifest.json"), "--profile", str(root / "profile.json"),
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "READY_FOR_FUTURE_ASSOCIATION"
    assert payload["ready_for_case_association"] is True
    assert payload["case_association_performed"] is False


def test_cli_preflight_rejects_tampered_artifact(tmp_path, capsys):
    root = _bundle(tmp_path)
    (root / "raw" / "synthetic-bars.csv").write_bytes(RAW_CSV + b"tampered\n")
    code = main([
        "historical-bar-preflight", "--root", str(root),
        "--manifest", str(root / "manifest.json"), "--profile", str(root / "profile.json"),
    ])
    assert code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "NOT_READY_REJECTED"
    assert "ARTIFACT_SHA256_MISMATCH" in payload["reason_codes"]


def test_cli_preflight_report_writes_deterministic_bytes(tmp_path):
    root = _bundle(tmp_path)
    out1, out2 = tmp_path / "r1.json", tmp_path / "r2.json"
    for out in (out1, out2):
        assert main([
            "historical-bar-preflight-report", "--root", str(root),
            "--manifest", str(root / "manifest.json"),
            "--profile", str(root / "profile.json"), "--output", str(out),
        ]) == 0
    assert out1.read_bytes() == out2.read_bytes()
    fixture = (
        Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "acquisition"
        / "batch04" / "synthetic-valid-preflight-report.json"
    )
    assert out1.read_bytes() == fixture.read_bytes()


def test_cli_preflight_never_writes_over_raw(tmp_path):
    root = _bundle(tmp_path)
    raw = root / "raw" / "synthetic-bars.csv"
    before = raw.read_bytes()
    main([
        "historical-bar-preflight-report", "--root", str(root),
        "--manifest", str(root / "manifest.json"), "--profile", str(root / "profile.json"),
        "--output", str(root / "report.json"),
    ])
    assert raw.read_bytes() == before


def test_cli_submission_kit_generate_is_byte_identical(tmp_path):
    kit_dir = tmp_path / "kit"
    fx_dir = tmp_path / "fx"
    assert main([
        "submission-kit-generate", "--output-dir", str(kit_dir), "--fixtures-dir", str(fx_dir),
    ]) == 0
    for name, content in build_submission_kit().items():
        assert kit_dir.joinpath(*name.split("/")).read_bytes() == content, name
    for name, content in build_batch04_fixtures().items():
        assert (fx_dir / name).read_bytes() == content, name
