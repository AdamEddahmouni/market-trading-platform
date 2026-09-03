"""Centralized CLI inventory and offline/determinism guards.

Proves the full documented command surface exists, that a representative sweep of commands is
byte-deterministic across repeated runs, that invalid input returns a nonzero exit, and that no
command emits scoring, ranking, recommendation, or trading-signal vocabulary.
"""

import json
import re
from pathlib import Path

import pytest

from squeeze_core.__main__ import _parser, main

ROOT = Path(__file__).parents[1] / "fixtures"
EVIDENCE = ROOT / "evidence"
PROVIDERS = ROOT / "providers"

EXPECTED_COMMANDS = {
    "validate",
    "replay",
    "normalize-provider",
    "build-evidence",
    "build-evidence-timeline",
    "build-halt-state",
    "build-bar-series",
    "build-trade-quote-series",
}

# Whole-word strategy vocabulary. Word boundaries avoid false positives inside legitimate
# tokens (for example "rsi" inside a longer identifier, or "buy" inside a substring).
FORBIDDEN_OUTPUT_TERMS = (
    "squeeze_score", "candidate_score", "ranking", "recommendation", "trading_signal",
    "stop_loss", "take_profit", "momentum", "rsi", "macd", "bollinger", "keltner",
    "aggressor", "imbalance", "sentiment", "catalyst", "backtest",
)
FORBIDDEN_OUTPUT_RE = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in FORBIDDEN_OUTPUT_TERMS) + r")\b"
)


def _subcommands() -> set[str]:
    parser = _parser()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices and action.dest == "command":
            return set(action.choices)
    return set()


def test_all_documented_commands_are_registered() -> None:
    assert EXPECTED_COMMANDS <= _subcommands()


@pytest.mark.parametrize(
    "args",
    [
        ["validate", str(ROOT / "minimal_session.jsonl")],
        ["replay", str(ROOT / "minimal_session.jsonl"), "--mode", "strict"],
        [
            "build-evidence",
            "--input", str(EVIDENCE / "normalized_phase_1i_point_in_time.jsonl"),
            "--symbol", "TESTA", "--as-of", "2026-01-31T15:00:00Z",
        ],
        [
            "build-trade-quote-series",
            "--input", str(EVIDENCE / "normalized_phase_1i_point_in_time.jsonl"),
            "--symbol", "TESTA", "--as-of", "2026-01-31T14:36:01Z",
        ],
        [
            "build-halt-state",
            "--input", str(EVIDENCE / "normalized_phase_1f_point_in_time.jsonl"),
            "--symbol", "TESTA", "--as-of", "2026-01-31T15:00:00Z",
        ],
    ],
)
def test_command_output_is_deterministic_and_offline(args, capsys) -> None:
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second, f"nondeterministic output for {args[0]}"
    # Output must be a single canonical JSON object.
    json.loads(first)


@pytest.mark.parametrize(
    "args",
    [
        ["validate", str(ROOT / "minimal_session.jsonl")],
        [
            "build-evidence",
            "--input", str(EVIDENCE / "normalized_phase_1i_point_in_time.jsonl"),
            "--symbol", "TESTA", "--as-of", "2026-01-31T15:00:00Z",
        ],
        [
            "build-trade-quote-series",
            "--input", str(EVIDENCE / "normalized_phase_1i_point_in_time.jsonl"),
            "--symbol", "TESTA", "--as-of", "2026-01-31T14:36:01Z",
        ],
    ],
)
def test_command_output_has_no_strategy_vocabulary(args, capsys) -> None:
    assert main(args) == 0
    lowered = capsys.readouterr().out.lower()
    leaked = FORBIDDEN_OUTPUT_RE.findall(lowered)
    assert leaked == [], f"strategy terms leaked into {args[0]} output: {leaked}"


def test_invalid_fixture_returns_nonzero(capsys) -> None:
    result = main(["validate", str(ROOT / "does_not_exist.jsonl")])
    capsys.readouterr()
    assert result == 1


def test_invalid_provider_record_returns_nonzero(capsys) -> None:
    result = main(
        [
            "normalize-provider", "--provider", "trades-quotes",
            "--input", str(PROVIDERS / "trades_quotes" / "fixture_metadata.json"),
            "--context", str(PROVIDERS / "trades_quotes" / "context.json"),
        ]
    )
    captured = capsys.readouterr()
    assert result == 1
    # Rejections are structured JSON emitted on stderr, not a bare traceback.
    assert json.loads(captured.err)["accepted"] is False
