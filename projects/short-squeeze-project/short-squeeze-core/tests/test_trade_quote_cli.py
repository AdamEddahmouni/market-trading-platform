import json
from pathlib import Path

from squeeze_core.__main__ import main


ROOT = Path(__file__).parent / "fixtures"
PROVIDER_ROOT = ROOT / "providers" / "trades_quotes"
EVIDENCE_ROOT = ROOT / "evidence"


def test_normalize_trade_quote_provider_command_is_local_and_stable(capsys):
    args = [
        "normalize-provider", "--provider", "trades-quotes",
        "--input", str(PROVIDER_ROOT / "trade_representative_cases.json"),
        "--context", str(PROVIDER_ROOT / "context.json"),
        "--case", "trade-complete-equity",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    document = json.loads(first)
    assert document["accepted"] is True
    assert document["provider"] == "trades-quotes"
    assert document["observations"][0]["event_type"] == "TRADE"


def test_normalize_trade_quote_invalid_document_returns_structured_nonzero(capsys):
    result = main(
        [
            "normalize-provider", "--provider", "trades-quotes",
            "--input", str(PROVIDER_ROOT / "fixture_metadata.json"),
            "--context", str(PROVIDER_ROOT / "context.json"),
        ]
    )
    captured = capsys.readouterr()
    assert result == 1
    document = json.loads(captured.err)
    assert document["accepted"] is False
    assert document["rejection"]["code"] == "TRADE_QUOTE_INVALID_RECORD"


def test_build_trade_quote_series_command_is_objective_and_deterministic(capsys):
    args = [
        "build-trade-quote-series",
        "--input", str(EVIDENCE_ROOT / "normalized_phase_1i_point_in_time.jsonl"),
        "--symbol", "TESTA", "--as-of", "2026-01-31T14:36:01Z",
        "--provider", "REPRESENTATIVE_FEED", "--venue", "XTEST",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    document = json.loads(first)
    assert document["command"] == "build-trade-quote-series"
    assert document["series"]["trades"]
    assert document["series"]["quotes"]
    lowered = first.lower()
    for forbidden in (
        "aggressor_side", "buy_volume", "sell_volume", "imbalance", "cumulative_delta",
        "midpoint", "effective_spread", "realized_spread", "slippage", "liquidity_score",
        "momentum", "squeeze_score", "recommendation", "trading_signal",
    ):
        assert forbidden not in lowered


def test_existing_timeline_command_accepts_trade_quote_timeline(capsys):
    result = main(
        [
            "build-evidence-timeline",
            "--input", str(EVIDENCE_ROOT / "normalized_phase_1i_point_in_time.jsonl"),
            "--symbol", "TESTA",
            "--as-of-file", str(EVIDENCE_ROOT / "trade_quote_availability_timeline.json"),
        ]
    )
    assert result == 0
    document = json.loads(capsys.readouterr().out)
    final = document["bundles"]["final"]
    coverage = {item["domain"]: item for item in final["source_coverage"]}
    assert coverage["TRADES"]["observation_ids"]
    assert coverage["QUOTES"]["observation_ids"]
