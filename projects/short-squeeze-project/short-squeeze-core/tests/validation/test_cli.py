import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_SPEC = REPO_ROOT / "tests" / "fixtures" / "validation" / "biya_validation_case.json"

# Anything matching these must never appear in CLI output, and especially not in the
# public export, which is published.
FORBIDDEN_IN_OUTPUT = ("C:\\", "/Users/", "auth=", "49dafaaa", "api_key", "@gmail.com")


def _run(args, check=True):
    return subprocess.run(
        [sys.executable, "-m", "squeeze_core", *args],
        cwd=REPO_ROOT, capture_output=True, text=True, check=check,
    )


def test_build_candidate_validation_succeeds_and_emits_canonical_json():
    result = _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC)])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "BIYA"
    assert payload["case_id"] == "case-biya"


def test_build_candidate_validation_writes_the_output_file(tmp_path):
    target = tmp_path / "nested" / "biya-validation.json"
    _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC), "--output", str(target)])
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8"))["symbol"] == "BIYA"


def test_build_candidate_validation_is_byte_identical_across_runs():
    first = _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC)])
    second = _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC)])
    assert first.stdout == second.stdout


def test_missing_case_spec_exits_nonzero_with_a_structured_error(tmp_path):
    result = _run(
        ["build-candidate-validation", "--case-spec", str(tmp_path / "absent.json")], check=False
    )
    assert result.returncode != 0
    payload = json.loads(result.stderr)
    assert payload["valid"] is False
    assert payload["command"] == "build-candidate-validation"
    assert payload["error"]


def test_malformed_case_spec_exits_nonzero(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"case_id": "x"}', encoding="utf-8")  # missing symbol
    result = _run(["build-candidate-validation", "--case-spec", str(bad)], check=False)
    assert result.returncode != 0
    assert json.loads(result.stderr)["valid"] is False


def test_case_spec_that_is_not_an_object_exits_nonzero(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")
    result = _run(["build-candidate-validation", "--case-spec", str(bad)], check=False)
    assert result.returncode != 0


def test_export_validation_demo_round_trips(tmp_path):
    case_path = tmp_path / "case.json"
    demo_path = tmp_path / "demo.json"
    _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC), "--output", str(case_path)])
    result = _run(
        ["export-validation-demo", "--validation-case", str(case_path), "--output", str(demo_path)]
    )
    assert result.returncode == 0
    payload = json.loads(demo_path.read_text(encoding="utf-8"))
    assert payload["symbol"] == "BIYA"
    assert payload["conclusion"] == "INSUFFICIENT_EVIDENCE"


def test_export_validation_demo_is_byte_identical_across_runs(tmp_path):
    case_path = tmp_path / "case.json"
    _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC), "--output", str(case_path)])
    first = _run(["export-validation-demo", "--validation-case", str(case_path)])
    second = _run(["export-validation-demo", "--validation-case", str(case_path)])
    assert first.stdout == second.stdout


def test_export_validation_demo_rejects_a_missing_case(tmp_path):
    result = _run(
        ["export-validation-demo", "--validation-case", str(tmp_path / "absent.json")], check=False
    )
    assert result.returncode != 0
    assert json.loads(result.stderr)["valid"] is False


@pytest.mark.parametrize("forbidden", FORBIDDEN_IN_OUTPUT)
def test_validation_output_contains_no_local_path_or_credential(forbidden):
    result = _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC)])
    assert forbidden not in result.stdout


@pytest.mark.parametrize("forbidden", FORBIDDEN_IN_OUTPUT)
def test_public_export_contains_no_local_path_or_credential(tmp_path, forbidden):
    case_path = tmp_path / "case.json"
    _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC), "--output", str(case_path)])
    result = _run(["export-validation-demo", "--validation-case", str(case_path)])
    assert forbidden not in result.stdout


def test_public_export_omits_every_sensitive_artifact(tmp_path):
    case_path = tmp_path / "case.json"
    _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC), "--output", str(case_path)])
    case = json.loads(case_path.read_text(encoding="utf-8"))
    sensitive_ids = {a["artifact_id"] for a in case["artifacts"] if a.get("sensitive")}
    assert sensitive_ids, "the BIYA case must contain sensitive artifacts for this to be meaningful"

    public = json.loads(_run(["export-validation-demo", "--validation-case", str(case_path)]).stdout)
    summaries = " ".join(public["artifact_summaries"])
    for artifact_id in sensitive_ids:
        assert artifact_id not in summaries


def test_public_export_carries_no_scoring_or_trading_key(tmp_path):
    case_path = tmp_path / "case.json"
    _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC), "--output", str(case_path)])
    public = json.loads(_run(["export-validation-demo", "--validation-case", str(case_path)]).stdout)
    keys = {key.lower() for key in public}
    for forbidden in ("score", "rank", "tier", "recommend", "signal", "buy", "sell", "alert"):
        assert not any(forbidden in key for key in keys), sorted(keys)


def test_public_export_reports_no_outcome_for_biya(tmp_path):
    case_path = tmp_path / "case.json"
    _run(["build-candidate-validation", "--case-spec", str(CASE_SPEC), "--output", str(case_path)])
    public = json.loads(_run(["export-validation-demo", "--validation-case", str(case_path)]).stdout)
    assert public["outcome_available"] is False
    assert public["outcome_limitations"]


def test_prior_cli_commands_still_work():
    """Phase 2V is additive: the Phase 2D readiness command must be unaffected."""

    result = _run(["--help"], check=False)
    assert "build-candidate-validation" in result.stdout
    assert "build-evidence-readiness" in result.stdout
