import json
from pathlib import Path

from squeeze_core.__main__ import main
from squeeze_core.serialization import canonical_json_bytes
from squeeze_core.validation.outcome_normalization import normalize_acquired_market_bars

from .test_outcome_normalization import manifest, payload


def test_normalize_history_cli_writes_stable_structured_output(tmp_path, capsys):
    raw = payload()
    acquisition = manifest(raw)
    raw_path = tmp_path / "raw.json"
    manifest_path = tmp_path / "manifest.json"
    output = tmp_path / "normalized.json"
    raw_path.write_bytes(raw)
    manifest_path.write_bytes(canonical_json_bytes(acquisition))
    assert main(["normalize-biya-history", "--manifest", str(manifest_path),
                 "--raw", str(raw_path), "--output", str(output)]) == 0
    assert output.read_bytes() == canonical_json_bytes(normalize_acquired_market_bars(acquisition, raw))
    assert json.loads(capsys.readouterr().out)["command"] == "normalize-biya-history"


def test_build_amendment_cli_requires_explicit_inputs(tmp_path):
    missing = tmp_path / "missing.json"
    assert main(["build-biya-outcome-amendment", "--validation-case", str(missing),
                 "--market-data", str(missing), "--output", str(tmp_path / "out.json")]) == 1


def test_build_amendment_cli_accepts_documented_biya_case_spec(tmp_path):
    raw = payload([1784298240, 1784307300, 1784307360], opens=[4.0, 4.0, 8.0])
    dataset = normalize_acquired_market_bars(manifest(raw), raw)
    market_path = tmp_path / "market.json"
    output = tmp_path / "amendment.json"
    market_path.write_bytes(canonical_json_bytes(dataset))
    assert main([
        "build-biya-outcome-amendment",
        "--validation-case", "tests/fixtures/validation/biya_validation_case.json",
        "--market-data", str(market_path), "--output", str(output),
    ]) == 0
    rendered = json.loads(output.read_text(encoding="utf-8"))
    assert rendered["original_case_id"] == "case-biya"
