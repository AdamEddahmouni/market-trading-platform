import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BARS = REPO_ROOT / "tests" / "fixtures" / "metrics" / "cli_demo_bars.jsonl"
SPEC = REPO_ROOT / "tests" / "fixtures" / "metrics" / "phase_2a_metric_cases.json"

QUALITATIVE_DENY_LIST = (
    "bullish",
    "bearish",
    "strong",
    "weak",
    "breakout",
    "score",
    "rank",
    "recommend",
    " buy ",
    " sell ",
)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "squeeze_core", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_valid_metric_request_exits_zero_with_json_on_stdout():
    result = _run(
        "build-market-metrics",
        "--input", str(BARS),
        "--symbol", "TESTA",
        "--as-of", "2026-01-20T22:00:00Z",
        "--spec", str(SPEC),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"] == "build-market-metrics"
    assert len(payload["results"]) == 6
    names = {item["metric_name"] for item in payload["results"]}
    assert names == {
        "ABSOLUTE_RETURN",
        "PERCENTAGE_RETURN",
        "ABSOLUTE_SESSION_GAP",
        "ABSOLUTE_BAR_RANGE",
        "PERCENTAGE_BAR_RANGE",
        "MEAN_VOLUME_BASELINE",
    }


def test_stable_key_ordering():
    result = _run(
        "build-market-metrics",
        "--input", str(BARS),
        "--symbol", "TESTA",
        "--as-of", "2026-01-20T22:00:00Z",
        "--spec", str(SPEC),
    )
    first_result = json.loads(result.stdout)["results"][0]
    assert list(first_result.keys()) == sorted(first_result.keys())


def test_deterministic_repeated_output():
    first = _run(
        "build-market-metrics",
        "--input", str(BARS),
        "--symbol", "TESTA",
        "--as-of", "2026-01-20T22:00:00Z",
        "--spec", str(SPEC),
    )
    second = _run(
        "build-market-metrics",
        "--input", str(BARS),
        "--symbol", "TESTA",
        "--as-of", "2026-01-20T22:00:00Z",
        "--spec", str(SPEC),
    )
    assert first.stdout == second.stdout


def test_invalid_metric_name_exits_nonzero(tmp_path):
    bad_spec = tmp_path / "bad_spec.json"
    bad_spec.write_text(json.dumps({"cases": [{"metric_name": "NOT_A_METRIC", "source_interval": "1_DAY"}]}))
    result = _run(
        "build-market-metrics",
        "--input", str(BARS),
        "--symbol", "TESTA",
        "--as-of", "2026-01-20T22:00:00Z",
        "--spec", str(bad_spec),
    )
    assert result.returncode == 1
    payload = json.loads(result.stderr)
    assert payload["valid"] is False
    assert "NOT_A_METRIC" in payload["error"]


def test_missing_as_of_is_an_argparse_usage_error():
    result = _run("build-market-metrics", "--input", str(BARS), "--symbol", "TESTA", "--spec", str(SPEC))
    assert result.returncode != 0


def test_missing_symbol_is_an_argparse_usage_error():
    result = _run("build-market-metrics", "--input", str(BARS), "--as-of", "2026-01-20T22:00:00Z", "--spec", str(SPEC))
    assert result.returncode != 0


def test_invalid_input_file_exits_nonzero(tmp_path):
    bad_input = tmp_path / "not_json.jsonl"
    bad_input.write_text("{not valid json")
    result = _run(
        "build-market-metrics",
        "--input", str(bad_input),
        "--symbol", "TESTA",
        "--as-of", "2026-01-20T22:00:00Z",
        "--spec", str(SPEC),
    )
    assert result.returncode == 1


def test_no_eligible_bars_is_not_a_cli_failure(tmp_path):
    empty_input = tmp_path / "empty.jsonl"
    empty_input.write_text("")
    result = _run(
        "build-market-metrics",
        "--input", str(empty_input),
        "--symbol", "TESTA",
        "--as-of", "2026-01-20T22:00:00Z",
        "--spec", str(SPEC),
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert all(item["quality"]["state"] != "KNOWN_VALUE" for item in payload["results"])


def test_output_contains_no_qualitative_trading_language():
    result = _run(
        "build-market-metrics",
        "--input", str(BARS),
        "--symbol", "TESTA",
        "--as-of", "2026-01-20T22:00:00Z",
        "--spec", str(SPEC),
    )
    lowered = result.stdout.lower()
    for needle in QUALITATIVE_DENY_LIST:
        assert needle not in lowered, f"unexpected qualitative language: {needle!r}"


def test_local_only_no_network_module_reachable_from_cli_command():
    # Static check: the CLI handler module itself imports no networking library.
    import ast

    main_module = REPO_ROOT / "src" / "squeeze_core" / "__main__.py"
    tree = ast.parse(main_module.read_text(encoding="utf-8"))
    forbidden = {"socket", "http", "urllib", "requests"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden
