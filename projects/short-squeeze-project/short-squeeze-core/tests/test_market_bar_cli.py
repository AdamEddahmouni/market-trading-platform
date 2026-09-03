import json
from pathlib import Path

import pytest

from squeeze_core.__main__ import main


ROOT = Path(__file__).parent / "fixtures"
BAR_ROOT = ROOT / "providers" / "market_bars"
EVIDENCE_ROOT = ROOT / "evidence"


def test_normalize_market_bar_provider_command_is_local_and_stable(capsys):
    args = [
        "normalize-provider",
        "--provider",
        "market-bars",
        "--input",
        str(BAR_ROOT / "representative_cases.json"),
        "--context",
        str(BAR_ROOT / "context.json"),
        "--case",
        "bar-complete-one-minute",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    document = json.loads(first)
    assert document["accepted"] is True
    assert document["provider"] == "market-bars"
    assert document["observations"][0]["event_type"] == "BAR"


def test_normalize_market_bar_rejection_returns_nonzero_structured_json(capsys):
    result = main(
        [
            "normalize-provider",
            "--provider",
            "market-bars",
            "--input",
            str(BAR_ROOT / "edge_cases.json"),
            "--context",
            str(BAR_ROOT / "context.json"),
            "--case",
            "bar-invalid-ohlc",
        ]
    )
    captured = capsys.readouterr()
    assert result == 1
    document = json.loads(captured.err)
    assert document["accepted"] is False
    assert document["rejection"]["code"] == "BAR_INVALID_OHLC"


def test_build_bar_series_command_is_objective_and_deterministic(capsys):
    args = [
        "build-bar-series",
        "--input",
        str(EVIDENCE_ROOT / "normalized_phase_1h_point_in_time.jsonl"),
        "--symbol",
        "TESTA",
        "--interval",
        "1_MINUTE",
        "--as-of",
        "2026-01-31T14:35:01Z",
        "--session",
        "REGULAR",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    document = json.loads(first)
    assert document["command"] == "build-bar-series"
    assert len(document["series"]["observations"]) == 3
    lowered = first.lower()
    for forbidden in (
        "relative_volume",
        "momentum",
        "breakout",
        "indicator",
        "squeeze_score",
        "recommendation",
        "trading_signal",
    ):
        assert forbidden not in lowered


def test_build_bar_series_rejects_unsupported_interval(capsys):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "build-bar-series",
                "--input",
                str(EVIDENCE_ROOT / "normalized_phase_1h_point_in_time.jsonl"),
                "--symbol",
                "TESTA",
                "--interval",
                "2_HOURS",
                "--as-of",
                "2026-01-31T14:35:01Z",
            ]
        )
    assert error.value.code != 0
    assert "invalid choice" in capsys.readouterr().err.lower()


def test_existing_evidence_timeline_accepts_market_bars(capsys):
    result = main(
        [
            "build-evidence-timeline",
            "--input",
            str(EVIDENCE_ROOT / "normalized_phase_1h_point_in_time.jsonl"),
            "--symbol",
            "TESTA",
            "--as-of-file",
            str(EVIDENCE_ROOT / "market_bar_availability_timeline.json"),
        ]
    )
    assert result == 0
    document = json.loads(capsys.readouterr().out)
    final = document["bundles"]["after_correction_receipt"]
    coverage = {item["domain"]: item for item in final["source_coverage"]}
    assert coverage["MARKET_BARS"]["state"] == "PRESENT"
