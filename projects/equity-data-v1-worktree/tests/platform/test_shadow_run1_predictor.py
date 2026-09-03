import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.predictor import (
    FrozenPredictorConfig,
    eligible_trades,
    evaluate_prediction,
    reference_price,
)

NS = 1_000_000_000
CONFIG = FrozenPredictorConfig()


def _trade(i, event_s, side, qty, price, available_s=None):
    return {
        "admission": "ADMITTED_DISPLAY",
        "aggressor_provenance": "INFERRED",
        "aggressor_side": side,
        "available_time_ns": (available_s if available_s is not None else event_s + 1) * NS,
        "event_time_ns": event_s * NS,
        "price": price,
        "provider": "moomoo",
        "quality": "PASS",
        "quantity": qty,
        "trade_id": f"T{i}",
    }


def _tape(rows):
    return [_trade(i, *row) for i, row in enumerate(rows)]


class EligibilityTests(unittest.TestCase):
    def test_late_arriving_trade_excluded_despite_earlier_event_stamp(self):
        decision_s = 600
        tape = _tape([(590, "BUY", 10, 10.0)])
        tape.append(_trade(99, 595, "BUY", 10, 11.0, available_s=700))
        eligible = eligible_trades(tape, decision_time_ns=decision_s * NS)
        self.assertEqual([t["trade_id"] for t in eligible], ["T0"])


class EvaluationTests(unittest.TestCase):
    def _uniform(self, side, n, start_s=100):
        return [(start_s + i, side, 10, 10.0) for i in range(n)]

    def test_insufficient_trades_abstains(self):
        res = evaluate_prediction(
            eligible_trades(_tape(self._uniform("BUY", 9)), decision_time_ns=112 * NS),
            decision_time_ns=112 * NS, config=CONFIG,
        )
        self.assertEqual(res, {"outcome": "ABSTAINED_MODEL", "reason": "INSUFFICIENT_TRADES"})

    def test_stale_input_abstains_when_newest_trade_too_old(self):
        tape = _tape(self._uniform("BUY", 12, start_s=100))  # newest at 111s
        decision_s = 200  # trades end at 111s; gap 89s exceeds the 60s stale bound
        res = evaluate_prediction(tape, decision_time_ns=decision_s * NS, config=CONFIG)
        self.assertEqual(res, {"outcome": "ABSTAINED_MODEL", "reason": "STALE_INPUT"})

    def test_flat_band_abstains_on_mixed_flow(self):
        rows = [(100 + i, "BUY" if i % 2 == 0 else "SELL", 10, 10.0) for i in range(12)]
        res = evaluate_prediction(_tape(rows), decision_time_ns=115 * NS, config=CONFIG)
        self.assertEqual(res, {"outcome": "ABSTAINED_MODEL", "reason": "FLAT_BAND"})

    def test_buy_skew_maps_to_up_with_clipped_transform(self):
        rows = self._uniform("BUY", 12)
        res = evaluate_prediction(_tape(rows), decision_time_ns=115 * NS, config=CONFIG)
        self.assertEqual(res["outcome"], "PREDICTED")
        self.assertEqual(res["direction"], "UP")
        self.assertAlmostEqual(res["raw_nss"], 1.0)
        self.assertAlmostEqual(res["p_up"], 0.9)
        self.assertAlmostEqual(res["p_selected"], 0.9)

    def test_sell_skew_inverts_selection_confidence(self):
        rows = self._uniform("SELL", 12)
        res = evaluate_prediction(_tape(rows), decision_time_ns=115 * NS, config=CONFIG)
        self.assertEqual(res["direction"], "DOWN")
        self.assertAlmostEqual(res["p_up"], 0.1)
        self.assertAlmostEqual(res["p_selected"], 0.9)

    def test_moderate_skew_unclipped(self):
        rows = [(100 + i, "BUY" if i < 8 else "SELL", 10, 10.0) for i in range(12)]
        res = evaluate_prediction(_tape(rows), decision_time_ns=115 * NS, config=CONFIG)
        self.assertAlmostEqual(res["raw_nss"], 4.0 / 12.0, places=12)
        self.assertAlmostEqual(res["p_up"], 0.5 + 0.5 * (4.0 / 12.0), places=12)

    def test_counts_and_volumes_reported(self):
        rows = [(100 + i, "BUY" if i < 8 else "SELL", 10, 10.0) for i in range(12)]
        res = evaluate_prediction(_tape(rows), decision_time_ns=115 * NS, config=CONFIG)
        self.assertEqual((res["buyer_count"], res["seller_count"], res["unknown_count"]), (8, 4, 0))
        self.assertAlmostEqual(res["total_volume"], 120.0)

    def test_band_edges_are_inclusive(self):
        # nss exactly +0.15 -> UP (>= band); construct 46 buy / 54 sell? No:
        # need nss >= 0.15 with buys>sell. 57.5/42.5 impossible; use 60/40 of 10 qty each
        rows = [(100 + i, "BUY" if i < 6 else "SELL", 10, 10.0) for i in range(10)]  # nss=+0.2
        res = evaluate_prediction(_tape(rows), decision_time_ns=115 * NS, config=CONFIG)
        self.assertEqual(res["outcome"], "PREDICTED")


class ReferencePriceTests(unittest.TestCase):
    def test_last_trade_at_or_before_decision(self):
        tape = _tape([(100, "BUY", 5, 10.0), (150, "SELL", 5, 10.5)])
        ref = reference_price(tape, decision_time_ns=160 * NS)
        self.assertEqual(ref["trade_id"], "T1")
        self.assertEqual(ref["price"], 10.5)
        self.assertIsNone(reference_price(tape, decision_time_ns=50 * NS))


if __name__ == "__main__":
    unittest.main()
