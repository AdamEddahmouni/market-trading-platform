"""Unit tests for SPY/QQQ research pipeline (fixtures only — no network)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.historical_chain_adapter import (  # noqa: E402
    normalize_option_row,
    rows_to_snapshot,
    schema_mapping_report,
)
from evaluation.ivolatility_client import estimate_pull_cost_usd  # noqa: E402
from evaluation.pattern_miner import (  # noqa: E402
    chronological_split,
    mine_buckets,
    run_pattern_pipeline,
    validate_patterns,
)
from evaluation.proposals import build_proposals, update_proposal_status, write_proposals  # noqa: E402
from evaluation.research_panel import build_spy_qqq_research_panel  # noqa: E402
from evaluation.spy_qqq_replay import label_replay_outcome  # noqa: E402


def _opt_row(**kwargs):
    base = {
        "tradeDate": "2026-01-15",
        "stock_symbol": "SPY",
        "expiration_date": "2026-01-15",
        "strike": 500.0,
        "call_put": "C",
        "bid": 1.0,
        "ask": 1.2,
        "last": 1.1,
        "volume": 100,
        "open_interest": 500,
        "iv": 0.2,
        "underlying_price": 500.0,
        "option_symbol": "SPY260115C00500000",
    }
    base.update(kwargs)
    return base


class AdapterTests(unittest.TestCase):
    def test_schema_mapping_ok(self) -> None:
        rows = [_opt_row(), _opt_row(call_put="P", strike=495)]
        report = schema_mapping_report(rows)
        self.assertTrue(report["ok"], report)
        snap = rows_to_snapshot("SPY", "2026-01-15", rows, spot=500.0)
        self.assertEqual(snap.ticker, "SPY")
        self.assertEqual(len(snap.contracts), 2)
        self.assertIn("2026-01-15", snap.expirations)

    def test_normalize_call_put_variants(self) -> None:
        self.assertEqual(normalize_option_row({"call_put": "P", "strike": 1})["call_put"], "put")
        self.assertEqual(normalize_option_row({"type": "call", "strike": 1})["call_put"], "call")


class CostEstimateTests(unittest.TestCase):
    def test_cost_units(self) -> None:
        est = estimate_pull_cost_usd(
            tickers=["SPY", "QQQ"],
            trading_days=10,
            datasets=["stock_prices", "options_eod"],
            unit_cost=0.05,
        )
        self.assertEqual(est["units"], 40)
        self.assertEqual(est["estimated_usd"], 2.0)


class OutcomeLabelTests(unittest.TestCase):
    def test_tp_sl_eod(self) -> None:
        self.assertEqual(label_replay_outcome(1.0, [1.4])[0], "win")
        self.assertEqual(label_replay_outcome(1.0, [0.6])[0], "loss")
        self.assertEqual(label_replay_outcome(1.0, [1.01])[0], "flat")


class MinerTests(unittest.TestCase):
    def _rows(self, n_win: int, n_loss: int, **feat) -> list:
        rows = []
        for i in range(n_win):
            rows.append(
                {
                    "ticker": "SPY",
                    "session_date": f"2026-01-{(i % 20) + 1:02d}",
                    "timestamp": f"2026-01-{(i % 20) + 1:02d}T20:00:00+00:00",
                    "outcome": "win",
                    "confidence_pct": feat.get("confidence_pct", 40),
                    "options_score": feat.get("options_score", 70),
                    "lean_pct": feat.get("lean_pct", 65),
                    "would_be_side": feat.get("would_be_side", "call"),
                    "source_kind": "backtest_replay",
                    "signal_source": "expiry",
                    "decision": "BUY",
                    "lean": "BUY",
                    "n_dir": 2,
                }
            )
        for i in range(n_loss):
            rows.append(
                {
                    "ticker": "QQQ",
                    "session_date": f"2026-02-{(i % 20) + 1:02d}",
                    "timestamp": f"2026-02-{(i % 20) + 1:02d}T20:00:00+00:00",
                    "outcome": "loss",
                    "confidence_pct": feat.get("loss_confidence_pct", 75),
                    "options_score": 35,
                    "lean_pct": 40,
                    "would_be_side": "put",
                    "source_kind": "backtest_replay",
                    "signal_source": "expiry",
                    "decision": "SELL",
                    "lean": "SELL",
                    "n_dir": 1,
                }
            )
        return rows

    def test_hard_n_floor_excludes_small_buckets(self) -> None:
        rows = self._rows(5, 5)
        patterns = mine_buckets(rows, min_n=30)
        self.assertEqual(patterns, [])

    def test_n_floor_includes_large_buckets(self) -> None:
        rows = self._rows(40, 40)
        patterns = mine_buckets(rows, min_n=30)
        self.assertTrue(any(p["n"] >= 30 for p in patterns))
        for p in patterns:
            self.assertGreaterEqual(p["n"], 30)
            self.assertIn("win_rate_se", p)
            self.assertIn("wilson_lo", p)

    def test_chrono_split_not_random(self) -> None:
        rows = self._rows(40, 40)
        disc, val, disc_days, val_days = chronological_split(rows, discovery_frac=0.7)
        self.assertTrue(disc_days)
        self.assertTrue(val_days)
        self.assertLess(max(disc_days), min(val_days))
        self.assertTrue(disc and val)

    def test_oos_validation_logs_failures(self) -> None:
        # Discovery: call strongly wins, put loses. Validation reverses.
        discovery = []
        for i in range(35):
            discovery.append(
                {
                    "session_date": f"2026-01-{(i % 28) + 1:02d}",
                    "timestamp": f"2026-01-{(i % 28) + 1:02d}T15:00:00+00:00",
                    "outcome": "win",
                    "would_be_side": "call",
                    "confidence_pct": 40,
                    "options_score": 70,
                    "lean_pct": 65,
                    "source_kind": "backtest_replay",
                    "signal_source": "expiry",
                    "decision": "BUY",
                    "lean": "BUY",
                    "n_dir": 2,
                }
            )
        for i in range(35):
            discovery.append(
                {
                    "session_date": f"2026-01-{(i % 28) + 1:02d}",
                    "timestamp": f"2026-01-{(i % 28) + 1:02d}T16:00:00+00:00",
                    "outcome": "loss",
                    "would_be_side": "put",
                    "confidence_pct": 75,
                    "options_score": 30,
                    "lean_pct": 40,
                    "source_kind": "backtest_replay",
                    "signal_source": "expiry",
                    "decision": "SELL",
                    "lean": "SELL",
                    "n_dir": 1,
                }
            )
        validation = []
        for i in range(35):
            validation.append(
                {
                    "session_date": f"2026-06-{(i % 28) + 1:02d}",
                    "timestamp": f"2026-06-{(i % 28) + 1:02d}T15:00:00+00:00",
                    "outcome": "loss",
                    "would_be_side": "call",
                    "confidence_pct": 40,
                    "options_score": 70,
                    "lean_pct": 65,
                    "source_kind": "backtest_replay",
                    "signal_source": "expiry",
                    "decision": "BUY",
                    "lean": "BUY",
                    "n_dir": 2,
                }
            )
        for i in range(35):
            validation.append(
                {
                    "session_date": f"2026-06-{(i % 28) + 1:02d}",
                    "timestamp": f"2026-06-{(i % 28) + 1:02d}T16:00:00+00:00",
                    "outcome": "win",
                    "would_be_side": "put",
                    "confidence_pct": 75,
                    "options_score": 30,
                    "lean_pct": 40,
                    "source_kind": "backtest_replay",
                    "signal_source": "expiry",
                    "decision": "SELL",
                    "lean": "SELL",
                    "n_dir": 1,
                }
            )
        disc_pats = mine_buckets(discovery, min_n=30)
        result = validate_patterns(disc_pats, validation, min_n=30)
        failed_features = {f["feature"] for f in result["found_but_did_not_replicate"]}
        self.assertIn("would_be_side", failed_features)


class PanelAndProposalTests(unittest.TestCase):
    def test_panel_filters_non_spy_qqq_and_tags_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # empty near miss / executions
            (root / "executions.json").write_text("[]", encoding="utf-8")
            (root / "trade_log.json").write_text("[]", encoding="utf-8")
            replay = [
                {
                    "ticker": "SPY",
                    "outcome": "win",
                    "session_date": "2026-01-02",
                    "source_kind": "backtest_replay",
                },
                {
                    "ticker": "AAPL",
                    "outcome": "win",
                    "session_date": "2026-01-02",
                    "source_kind": "backtest_replay",
                },
            ]
            panel = build_spy_qqq_research_panel(replay_rows=replay, state_dir=root)
            tickers = {r["ticker"] for r in panel["rows"]}
            self.assertEqual(tickers, {"SPY"})
            self.assertIn("Path A", panel["generated_note"])

    def test_proposals_write_and_status_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            miner = {
                "min_n": 30,
                "discovery_days": ["2026-01-01"],
                "validation_days": ["2026-06-01"],
                "survivors": [
                    {
                        "feature": "confidence_band",
                        "value": "0-44",
                        "n": 40,
                        "win_rate": 0.6,
                        "wilson_lo": 0.4,
                        "wilson_hi": 0.7,
                        "lift": 1.3,
                        "kind": "favorable",
                        "summary": "when confidence_band=0-44: win_rate=60% (N=40)",
                        "validation": {
                            "n": 35,
                            "win_rate": 0.55,
                            "wilson_lo": 0.4,
                            "wilson_hi": 0.7,
                            "lift": 1.2,
                        },
                    }
                ],
                "found_but_did_not_replicate": [],
            }
            props = build_proposals(miner)
            paths = write_proposals(props, proposals_dir=root)
            self.assertTrue(paths["json"].exists())
            self.assertTrue(paths["md"].exists())
            update_proposal_status(
                props["proposals"][0]["id"],
                "rejected",
                proposals_path=paths["latest_json"],
                note="not enough live evidence",
            )
            loaded = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
            self.assertEqual(loaded["proposals"][0]["status"], "rejected")


class AuthGateTests(unittest.TestCase):
    def test_missing_key_raises(self) -> None:
        from evaluation.ivolatility_client import IVolatilityAuthError, resolve_api_key
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            # clear IVOL keys specifically
            env = {k: v for k, v in os.environ.items() if not k.startswith("IVOL")}
            with patch.dict(os.environ, env, clear=True):
                with patch("evaluation.ivolatility_client.load_project_dotenv", lambda: None):
                    with self.assertRaises(IVolatilityAuthError):
                        resolve_api_key()


if __name__ == "__main__":
    unittest.main()
