"""Tests for offline win/loss pattern learner."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.pattern_learner import (
    analyze_categorical_patterns,
    backfill_calibration_outcomes,
    build_labeled_panel,
    record_calibration_outcome_for_close,
    run_pattern_learning,
)


class PatternLearnerTests(unittest.TestCase):
    def test_panel_and_patterns_from_near_miss_and_exec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nm = {
                "items": {
                    "a": {
                        "id": "A|t|low_confidence",
                        "ticker": "AAPL",
                        "rejected_at": "2026-07-22T15:00:00+00:00",
                        "reason_code": "low_confidence",
                        "confidence_pct": 55,
                        "options_score": 72,
                        "lean": "BUY",
                        "lean_pct": 62,
                        "signal_source": "expiry",
                        "shadow_outcome": "would_have_won",
                        "first_exit_rule": "take_profit",
                        "entry_quote_status": "ok",
                        "would_be_side": "call",
                    },
                    "b": {
                        "id": "B|t|low_confidence",
                        "ticker": "MSFT",
                        "rejected_at": "2026-07-22T15:10:00+00:00",
                        "reason_code": "low_confidence",
                        "confidence_pct": 40,
                        "options_score": 35,
                        "lean": "WAIT",
                        "lean_pct": 40,
                        "signal_source": "expiry",
                        "shadow_outcome": "would_have_lost",
                        "first_exit_rule": "stop_loss",
                        "entry_quote_status": "ok",
                        "would_be_side": "call",
                    },
                    "c": {
                        "id": "C|t|liquidity_reject",
                        "ticker": "NVDA",
                        "rejected_at": "2026-07-22T15:20:00+00:00",
                        "reason_code": "liquidity_reject",
                        "confidence_pct": 58,
                        "options_score": 68,
                        "lean": "BUY",
                        "lean_pct": 61,
                        "signal_source": "news",
                        "shadow_outcome": "would_have_won",
                        "first_exit_rule": "take_profit",
                        "entry_quote_status": "ok",
                        "would_be_side": "call",
                    },
                    "d": {
                        "id": "D|t|low_confidence",
                        "ticker": "AMD",
                        "rejected_at": "2026-07-22T15:30:00+00:00",
                        "reason_code": "low_confidence",
                        "confidence_pct": 42,
                        "options_score": 30,
                        "lean": "WAIT",
                        "lean_pct": 38,
                        "signal_source": "expiry",
                        "shadow_outcome": "would_have_lost",
                        "first_exit_rule": "stop_loss",
                        "entry_quote_status": "ok",
                        "would_be_side": "put",
                    },
                }
            }
            (root / "near_miss_tracker_2026-07-22.json").write_text(
                json.dumps(nm), encoding="utf-8"
            )
            executions = [
                {
                    "timestamp": "2026-07-22T14:00:00+00:00",
                    "ticker": "TSLA",
                    "action": "open",
                    "side": "call",
                    "contract_symbol": "TSLA260722C00300000",
                    "realized_pnl": 0.0,
                },
                {
                    "timestamp": "2026-07-22T14:30:00+00:00",
                    "ticker": "TSLA",
                    "action": "close",
                    "side": "call",
                    "contract_symbol": "TSLA260722C00300000",
                    "realized_pnl": -200.0,
                    "reason": "stop_loss",
                },
            ]
            (root / "executions.json").write_text(json.dumps(executions), encoding="utf-8")
            (root / "trade_log.json").write_text(
                json.dumps(
                    [
                        {
                            "timestamp": "2026-07-22T13:59:00+00:00",
                            "ticker": "TSLA",
                            "decision": "BUY",
                            "confidence_pct": 80,
                            "options_score": 75,
                            "lean": "BUY",
                            "lean_pct": 70,
                            "signal_source": "expiry",
                            "decision_reason_code": "path_b",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            panel = build_labeled_panel(root)
            self.assertEqual(len(panel), 5)
            self.assertEqual(sum(1 for r in panel if r["outcome"] == "win"), 2)
            self.assertEqual(sum(1 for r in panel if r["outcome"] == "loss"), 3)

            report = run_pattern_learning(root, min_group_n=2, persist=True)
            self.assertEqual(report["status"], "ok")
            self.assertGreaterEqual(report["n_win_loss"], 5)
            self.assertTrue((root / "learning" / "learned_patterns.json").exists())
            self.assertTrue((root / "learning" / "labeled_panel.json").exists())

            cats = analyze_categorical_patterns(panel, min_group_n=2)
            self.assertTrue(any(p["feature"] == "lean" for p in cats))
            self.assertFalse(any(p["feature"] == "first_exit_rule" for p in cats))

    def test_calibration_backfill_and_live_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cal_path = root / "calibration_log.json"
            ex_path = root / "executions.json"
            cal_path.write_text(
                json.dumps(
                    [
                        {
                            "timestamp": "2026-07-22T14:00:00+00:00",
                            "ticker": "QQQ",
                            "decision": "SELL",
                            "predicted_confidence_pct": 70,
                            "outcome": None,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            ex_path.write_text(
                json.dumps(
                    [
                        {
                            "timestamp": "2026-07-22T14:01:00+00:00",
                            "ticker": "QQQ",
                            "action": "open",
                            "contract_symbol": "QQQ260722P00700000",
                            "realized_pnl": 0,
                        },
                        {
                            "timestamp": "2026-07-22T14:20:00+00:00",
                            "ticker": "QQQ",
                            "action": "close",
                            "contract_symbol": "QQQ260722P00700000",
                            "realized_pnl": -100,
                            "reason": "stop_loss",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            result = backfill_calibration_outcomes(
                calibration_path=cal_path, executions_path=ex_path
            )
            self.assertEqual(result["updated"], 1)
            rows = json.loads(cal_path.read_text(encoding="utf-8"))
            self.assertEqual(rows[0]["outcome"]["label"], "loss")

            # New unlabeled row + live close helper
            rows.append(
                {
                    "timestamp": "2026-07-23T14:00:00+00:00",
                    "ticker": "IWM",
                    "decision": "SELL",
                    "outcome": None,
                }
            )
            cal_path.write_text(json.dumps(rows), encoding="utf-8")
            ok = record_calibration_outcome_for_close(
                ticker="IWM",
                realized_pnl=50.0,
                exit_reason="take_profit",
                contract_symbol="IWM260723P00200000",
                calibration_path=cal_path,
            )
            self.assertTrue(ok)
            rows2 = json.loads(cal_path.read_text(encoding="utf-8"))
            self.assertEqual(rows2[-1]["outcome"]["label"], "win")


if __name__ == "__main__":
    unittest.main()
