#!/usr/bin/env python3
"""Deterministic news intelligence strategy evaluation CLI — fixture/replay only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.news_strategy_evaluation.config import (  # noqa: E402
    EvaluationConfig,
    verify_evaluation_config,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.evaluator import (  # noqa: E402
    NewsStrategyEvaluator,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.fixture_loader import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
    load_fixture_pack,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.replay import (  # noqa: E402
    EvaluationReplayHarness,
)


def _cmd_verify(_: argparse.Namespace) -> int:
    config = EvaluationConfig()
    pack = load_fixture_pack(DEFAULT_FIXTURE_PATH)
    warnings = verify_evaluation_config(config, instrument_ids=pack.instrument_universe)
    payload = {
        "ok": True,
        "config_hash": config.config_hash(),
        "lane_id": config.lane_id,
        "instrument_universe": list(pack.instrument_universe),
        "sample_count": len(pack.samples),
        "warnings": warnings,
    }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    fixture_path = Path(args.fixture) if args.fixture else DEFAULT_FIXTURE_PATH
    pack = load_fixture_pack(fixture_path)
    config = EvaluationConfig()
    verify_evaluation_config(config, instrument_ids=pack.instrument_universe)
    report = NewsStrategyEvaluator(config=config).evaluate_fixture_pack(pack)
    print(json.dumps(report.to_dict(), indent=2))
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    fixture_path = Path(args.fixture) if args.fixture else DEFAULT_FIXTURE_PATH
    harness = EvaluationReplayHarness(fixture_path=fixture_path)
    result = harness.replay(iterations=args.iterations)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.to_dict()["deterministic"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="News intelligence strategy evaluation laboratory")
    sub = parser.add_subparsers(dest="command", required=True)

    verify_parser = sub.add_parser("verify-config", help="Verify evaluation configuration")
    verify_parser.set_defaults(func=_cmd_verify)

    eval_parser = sub.add_parser("evaluate-fixture", help="Run fixture evaluation")
    eval_parser.add_argument("--fixture", default="", help="Path to evaluation fixture pack")
    eval_parser.set_defaults(func=_cmd_evaluate)

    replay_parser = sub.add_parser("replay", help="Deterministic replay harness")
    replay_parser.add_argument("--fixture", default="", help="Path to evaluation fixture pack")
    replay_parser.add_argument("--iterations", type=int, default=2)
    replay_parser.set_defaults(func=_cmd_replay)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
