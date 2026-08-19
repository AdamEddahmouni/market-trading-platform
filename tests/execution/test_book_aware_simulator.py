"""Book-aware L2 simulator tests — Order Flow OF9."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.execution.book_aware import BookAwareL2Simulator
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY

DEFAULT_POLICY = DEFAULT_RISK_POLICY


class BookAwareL2SimulatorTests(unittest.TestCase):
    def _bars(self, volume: int = 10000) -> list[dict]:
        return [
            {
                "available_time": 1000,
                "normalized_event_id": "bar-1",
                "bar_payload": {
                    "high": "101.0000",
                    "low": "99.0000",
                    "volume": volume,
                },
            },
            {
                "available_time": 2000,
                "normalized_event_id": "bar-2",
                "bar_payload": {
                    "high": "101.0000",
                    "low": "99.0000",
                    "volume": volume,
                },
            },
        ]

    def test_partial_fill_when_order_exceeds_touch_depth(self) -> None:
        sim = BookAwareL2Simulator(policy=DEFAULT_POLICY)
        intent = {
            "created_time": 500,
            "direction": "long",
            "instrument_id": "NVDA",
            "intent_id": "intent-1",
            "quantity": 500,
            "book_snapshot": {
                "best_bid": 100.0,
                "best_ask": 100.04,
                "bid_size": 200.0,
                "ask_size": 50.0,
            },
        }
        risk_decision = {
            "decision": "APPROVE",
            "approved_quantity": 500,
        }
        order, fill = sim.simulate(intent=intent, risk_decision=risk_decision, bars=self._bars())
        assert fill is not None
        self.assertEqual(fill["fill_quantity"], 50)
        self.assertEqual(fill["unfilled_quantity"], 450)
        self.assertIn("BOOK_DEPTH_PARTIAL", fill.get("fill_reason_codes", []))
        self.assertEqual(order["state"], "PARTIALLY_FILLED")

    def test_no_book_snapshot_degrades_without_crash(self) -> None:
        sim = BookAwareL2Simulator(policy=DEFAULT_POLICY)
        intent = {
            "created_time": 500,
            "direction": "long",
            "instrument_id": "NVDA",
            "intent_id": "intent-2",
            "quantity": 100,
        }
        risk_decision = {
            "decision": "APPROVE",
            "approved_quantity": 100,
        }
        order, fill = sim.simulate(intent=intent, risk_decision=risk_decision, bars=self._bars())
        assert fill is not None
        self.assertIn("NO_BOOK_SNAPSHOT", fill.get("fill_reason_codes", []))


if __name__ == "__main__":
    unittest.main()
