import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_INPUT = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2c_cli_demo_observations.jsonl"
CLI_SPEC = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2c_metric_cases.json"


def _run(spec_path: Path, *, symbol="TESTC", as_of="2026-03-15T12:00:00Z", input_path=CLI_INPUT):
    return subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-market-metrics",
            "--input", str(input_path), "--symbol", symbol, "--as-of", as_of, "--spec", str(spec_path),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def _single_case_spec(metric_name: str) -> dict:
    document = json.loads(CLI_SPEC.read_text(encoding="utf-8"))
    return {**document, "cases": [c for c in document["cases"] if c["metric_name"] == metric_name]}


def _run_single(metric_name: str, tmp_name: str):
    single_case = _single_case_spec(metric_name)
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / tmp_name
    tmp.write_text(json.dumps(single_case), encoding="utf-8")
    try:
        return _run(tmp)
    finally:
        tmp.unlink()


def test_valid_short_interest_change_request():
    completed = _run_single("PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE", "_tmp_si_change.json")
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["results"][0]["metric_name"] == "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    assert payload["results"][0]["quality"]["state"] == "KNOWN_VALUE"


def test_valid_percentage_change_request():
    completed = _run_single("PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE", "_tmp_si_pct.json")
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["results"][0]["unit"] == "PERCENT"


def test_valid_days_to_cover_request():
    completed = _run_single("DAYS_TO_COVER", "_tmp_dtc.json")
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["results"][0]["unit"] == "DAYS"
    assert payload["results"][0]["quality"]["state"] == "KNOWN_VALUE"


def test_valid_borrow_fee_change_request():
    completed = _run_single("BORROW_FEE_ABSOLUTE_CHANGE", "_tmp_fee.json")
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["results"][0]["unit"] == "PERCENTAGE_POINTS"


def test_valid_borrow_availability_change_request():
    completed = _run_single("BORROW_AVAILABILITY_ABSOLUTE_CHANGE", "_tmp_avail.json")
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["results"][0]["unit"] == "SHARES"


def test_full_spec_all_five_metrics_succeed():
    completed = _run(CLI_SPEC)
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    names = {r["metric_name"] for r in payload["results"]}
    assert names == {
        "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
        "PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE",
        "DAYS_TO_COVER",
        "BORROW_FEE_ABSOLUTE_CHANGE",
        "BORROW_AVAILABILITY_ABSOLUTE_CHANGE",
    }
    for result in payload["results"]:
        assert result["quality"]["state"] == "KNOWN_VALUE"


def test_invalid_metric_name_nonzero_exit():
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_invalid_name_2c.json"
    tmp.write_text(json.dumps({"cases": [{"metric_name": "NOT_A_REAL_METRIC"}]}), encoding="utf-8")
    try:
        completed = _run(tmp)
        assert completed.returncode != 0
    finally:
        tmp.unlink()


def test_missing_as_of_nonzero_exit():
    completed = subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-market-metrics",
            "--input", str(CLI_INPUT), "--symbol", "TESTC", "--spec", str(CLI_SPEC),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert completed.returncode != 0


def test_missing_provider_nonzero_exit():
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_missing_provider.json"
    tmp.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "metric_name": "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
                        "starting_reporting_period": "2026-01-15",
                        "ending_reporting_period": "2026-01-31",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    try:
        completed = _run(tmp)
        assert completed.returncode != 0
    finally:
        tmp.unlink()


def test_missing_reporting_period_nonzero_exit():
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_missing_period.json"
    tmp.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "metric_name": "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
                        "provider": "FINRA-PROVIDER",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    try:
        completed = _run(tmp)
        assert completed.returncode != 0
    finally:
        tmp.unlink()


def test_missing_input_file_nonzero_exit():
    completed = _run(CLI_SPEC, input_path=REPO_ROOT / "tests" / "fixtures" / "metrics" / "does_not_exist.jsonl")
    assert completed.returncode != 0


def test_zero_denominator_reports_invalid_not_nonzero_exit():
    document = json.loads(CLI_SPEC.read_text(encoding="utf-8"))
    case = next(c for c in document["cases"] if c["metric_name"] == "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE").copy()
    case["metric_name"] = "PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE"
    case["starting_reporting_period"] = case["ending_reporting_period"]
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_identical_period.json"
    tmp.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
    try:
        completed = _run(tmp)
        assert completed.returncode == 0
        payload = json.loads(completed.stdout)
        assert payload["results"][0]["quality"]["state"] in ("INVALID", "UNAVAILABLE")
    finally:
        tmp.unlink()


def test_missing_value_reports_unavailable_not_nonzero_exit():
    tmp = REPO_ROOT / "tests" / "fixtures" / "metrics" / "_tmp_missing_dtc.json"
    tmp.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "metric_name": "DAYS_TO_COVER",
                        "short_interest_provider": "FINRA-PROVIDER",
                        "short_interest_reporting_period": "2099-01-01",
                        "volume_provider": "SIM-VOLUME-PROVIDER",
                        "volume_interval": "1_DAY",
                        "volume_window": {"requested_count": 3, "minimum_samples": 3},
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
    for needle in (
        "strong", "weak", "bullish", "bearish", "unusual", "breakout", "squeeze",
        "pressure", "tight", "loose", "hard to borrow", "prime", "subprime",
    ):
        assert needle not in lowered


def test_local_only_no_network_strings_in_output():
    completed = _run(CLI_SPEC)
    for needle in ("http://", "https://", "ftp://", "mongodb://", "postgres://"):
        assert needle not in completed.stdout
