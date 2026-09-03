import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_BARS = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2b_cli_demo_bars.jsonl"
CLI_SPEC = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2b_normalized_metric_cases.json"


def _run(spec_path: Path, *, symbol="TESTB", as_of="2026-02-01T22:00:00Z", input_path=CLI_BARS):
    return subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-market-metrics",
            "--input", str(input_path), "--symbol", symbol, "--as-of", as_of, "--spec", str(spec_path),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def test_valid_relative_volume_request():
    document = json.loads(CLI_SPEC.read_text(encoding="utf-8"))
    single_case = {**document, "cases": [c for c in document["cases"] if c["metric_name"] == "RELATIVE_VOLUME"]}
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_rv_case.json"
    tmp.write_text(json.dumps(single_case), encoding="utf-8")
    try:
        completed = _run(tmp)
        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["results"][0]["metric_name"] == "RELATIVE_VOLUME"
        assert payload["results"][0]["quality"]["state"] == "KNOWN_VALUE"
    finally:
        tmp.unlink()


def test_valid_volume_z_score_request():
    document = json.loads(CLI_SPEC.read_text(encoding="utf-8"))
    single_case = {**document, "cases": [c for c in document["cases"] if c["metric_name"] == "VOLUME_Z_SCORE"]}
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_vz_case.json"
    tmp.write_text(json.dumps(single_case), encoding="utf-8")
    try:
        completed = _run(tmp)
        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["results"][0]["unit"] == "STANDARD_DEVIATIONS"
    finally:
        tmp.unlink()


def test_valid_return_z_score_request():
    document = json.loads(CLI_SPEC.read_text(encoding="utf-8"))
    single_case = {
        **document, "cases": [c for c in document["cases"] if c["metric_name"] == "PERCENTAGE_RETURN_Z_SCORE"]
    }
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_rz_case.json"
    tmp.write_text(json.dumps(single_case), encoding="utf-8")
    try:
        completed = _run(tmp)
        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["results"][0]["metric_name"] == "PERCENTAGE_RETURN_Z_SCORE"
    finally:
        tmp.unlink()


def test_full_spec_all_six_metrics_succeed():
    completed = _run(CLI_SPEC)
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    names = {r["metric_name"] for r in payload["results"]}
    assert names == {
        "RELATIVE_VOLUME",
        "VOLUME_PERCENT_DEVIATION",
        "VOLUME_Z_SCORE",
        "MEAN_PERCENTAGE_RETURN_BASELINE",
        "PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE",
        "PERCENTAGE_RETURN_Z_SCORE",
    }
    for result in payload["results"]:
        assert result["quality"]["state"] == "KNOWN_VALUE"


def test_invalid_metric_name_nonzero_exit():
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_invalid_name.json"
    tmp.write_text(json.dumps({"cases": [{"metric_name": "NOT_A_REAL_METRIC", "source_interval": "1_DAY"}]}), encoding="utf-8")
    try:
        completed = _run(tmp)
        assert completed.returncode != 0
    finally:
        tmp.unlink()


def test_missing_as_of_nonzero_exit():
    completed = subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-market-metrics",
            "--input", str(CLI_BARS), "--symbol", "TESTB", "--spec", str(CLI_SPEC),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert completed.returncode != 0


def test_invalid_input_file_nonzero_exit():
    completed = _run(CLI_SPEC, input_path=REPO_ROOT / "tests" / "fixtures" / "metrics" / "does_not_exist.jsonl")
    assert completed.returncode != 0


def test_insufficient_history_reports_unavailable_not_nonzero_exit():
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_insufficient.json"
    tmp.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "metric_name": "RELATIVE_VOLUME",
                        "symbol": "TESTB",
                        "source_interval": "1_DAY",
                        "target_bar_start": "2026-01-20T05:00:00Z",
                        "target_bar_end": "2026-01-21T05:00:00Z",
                        "window": {"requested_count": 50, "minimum_samples": 40},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    try:
        completed = _run(tmp)
        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["results"][0]["quality"]["state"] == "UNAVAILABLE"
    finally:
        tmp.unlink()


def test_deterministic_repeated_output():
    first = _run(CLI_SPEC)
    second = _run(CLI_SPEC)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout


def test_no_qualitative_language_in_output():
    completed = _run(CLI_SPEC)
    lowered = completed.stdout.lower()
    for needle in ("strong", "weak", "bullish", "bearish", "unusual", "breakout", "squeeze"):
        assert needle not in lowered


def test_local_only_no_network_strings_in_output():
    completed = _run(CLI_SPEC)
    for needle in ("http://", "https://", "ftp://", "mongodb://", "postgres://"):
        assert needle not in completed.stdout
