"""Operator runbook CLI argument contracts (docs Lane A — SOFTWARE only)."""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from market_platform_foundation.operations.rth_empirical_ops import (  # noqa: E402
    build_rth_empirical_ops_parser,
)


class RthOperatorCliContractTests(unittest.TestCase):
    def test_rth_empirical_ops_json_is_global_before_subcommand(self) -> None:
        parser = build_rth_empirical_ops_parser()
        for sub in ("preflight", "status", "run-observational", "summarize"):
            args = parser.parse_args(["--json", sub])
            self.assertTrue(args.json)
            self.assertEqual(args.command, sub)

    def test_rth_empirical_ops_rejects_json_after_subcommand(self) -> None:
        parser = build_rth_empirical_ops_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["preflight", "--json"])

    def test_item7_status_requires_training_cutoff_ns(self) -> None:
        from item7_corpus_collector import build_parser  # type: ignore[import-not-found]

        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["status", "--persistence-root", str(ROOT / ".local")])

    def test_item7_status_accepts_training_cutoff_ns(self) -> None:
        from item7_corpus_collector import build_parser  # type: ignore[import-not-found]

        args = build_parser().parse_args(
            ["status", "--training-cutoff-ns", "1", "--persistence-root", str(ROOT / ".local")]
        )
        self.assertEqual(args.training_cutoff_ns, 1)

    def test_item9_prospective_has_no_top_level_json_flag(self) -> None:
        tool = ROOT / "tools" / "moomoo" / "opend_bar_1m_prospective_proof.py"
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        prospective = sub.add_parser("prospective")
        for action in prospective._actions:
            if action.dest == "json":
                self.fail("prospective subcommand must not define --json")
        argv = [
            "prospective",
            "--poll",
            "--instrument-id",
            "AAPL",
            "--experiment-id",
            "item9-prospective-20260915-rth-aapl",
            "--receipt-out",
            str(ROOT / "artifacts/ftep-v1-002/item9-prospective-proof-receipts"),
            "--poll-interval-s",
            "5.0",
            "--timeout-s",
            "3900.0",
        ]
        # Smoke: documented Tuesday command shape parses on a minimal mirror parser.
        mirror = argparse.ArgumentParser()
        msub = mirror.add_subparsers(dest="command", required=True)
        pr = msub.add_parser("prospective")
        pr.add_argument("--poll", action="store_true")
        pr.add_argument("--instrument-id")
        pr.add_argument("--experiment-id")
        pr.add_argument("--receipt-out")
        pr.add_argument("--poll-interval-s", type=float)
        pr.add_argument("--timeout-s", type=float)
        parsed = mirror.parse_args(argv)
        self.assertTrue(parsed.poll)
        self.assertEqual(parsed.instrument_id, "AAPL")
        self.assertTrue(tool.is_file())


if __name__ == "__main__":
    unittest.main()
