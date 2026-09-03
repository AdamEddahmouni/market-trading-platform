"""Tests for donor pattern reimplementations."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_patterns.catalyst_lane import confidence_score, gate_catalyst, lean_direction
from market_platform_foundation.donor_patterns.cvd_formulas import (
    bvc_buy_sell_volume,
    classify_aggressor,
    cumulative_delta,
    ofi_events,
)
from market_platform_foundation.donor_patterns.edgar_whale import normalize_edgar_filing, WhaleEventType
from market_platform_foundation.donor_patterns.futures_lane import (
    depth_imbalance_signal,
    quarterly_contract_month,
)
from market_platform_foundation.donor_patterns.options_lane import confirmation_score, liquidity_gate
from market_platform_foundation.donor_patterns.order_book_lane import (
    best_bid_ask,
    depth_imbalance,
    direction_from_imbalance,
    snapshot_ofi,
)
from market_platform_foundation.donor_patterns.provenance_gates import (
    FreshnessState,
    apply_missingness,
    provenance_gate,
    readiness_summary,
)


class DonorPatternTests(unittest.TestCase):
    def test_lee_ready_aggressor(self) -> None:
        self.assertEqual(classify_aggressor(10.5, 100, 10.0, 10.5, 10.4), 100.0)
        self.assertEqual(classify_aggressor(10.0, 50, 10.0, 10.5, 10.4), -50.0)

    def test_cvd_cumulative(self) -> None:
        self.assertEqual(cumulative_delta([100, -50, 25]), [100.0, 50.0, 75.0])

    def test_bvc_splits_volume(self) -> None:
        buy, sell = bvc_buy_sell_volume([10.0, 10.5, 11.0], [1000, 1000, 1000], sigma_min_periods=1)
        self.assertEqual(len(buy), 3)
        self.assertAlmostEqual(buy[-1] + sell[-1], 1000.0)

    def test_ofi_events_length(self) -> None:
        events = ofi_events([10.0, 10.1], [10.2, 10.3], [100, 120], [80, 70])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], 0.0)

    def test_provenance_gate_missing(self) -> None:
        ok, reasons = provenance_gate({"symbol": "BIYA"}, required_fields=("symbol", "outcome"))
        self.assertFalse(ok)
        self.assertIn("MISSING_OUTCOME", reasons)

    def test_missingness_unknown_not_zero(self) -> None:
        self.assertEqual(apply_missingness(None), "UNKNOWN")

    def test_edgar_form4_buy(self) -> None:
        event = normalize_edgar_filing(
            form_type="4",
            filer="Officer",
            issuer="NVDA",
            accepted_at="2026-07-01T12:00:00Z",
            source_url="https://data.sec.gov/",
            transaction_code="P",
        )
        self.assertEqual(event["event_type"], WhaleEventType.INSIDER_BUY.value)
        self.assertTrue(event["research_only"])

    def test_catalyst_gate(self) -> None:
        conf = confidence_score(news_score=0.8, social_score=0.6, volume_score=0.5)
        self.assertGreater(conf, 0.5)
        ok, reasons = gate_catalyst(confidence=conf, min_confidence=0.5, lean="BULLISH", liquidity_ok=True)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

    def test_options_liquidity_gate(self) -> None:
        ok, reasons = liquidity_gate(bid=1.0, ask=1.1, open_interest=500)
        self.assertTrue(ok)
        ok_wide, reasons_wide = liquidity_gate(bid=1.0, ask=2.0, open_interest=500)
        self.assertFalse(ok_wide)
        self.assertIn("WIDE_SPREAD", reasons_wide)

    def test_options_confirmation_score_bounds(self) -> None:
        score = confirmation_score(iv_rank=1.0, volume_ratio=1.0, skew_signal=1.0)
        self.assertEqual(score, 100.0)
        low = confirmation_score(iv_rank=0.0, volume_ratio=0.0, skew_signal=0.0)
        self.assertEqual(low, 0.0)
        mid = confirmation_score(iv_rank=0.5, volume_ratio=0.5, skew_signal=0.5)
        self.assertAlmostEqual(mid, 50.0)

    def test_order_book_lane_helpers(self) -> None:
        snapshot = {
            "bids": [{"price": 10.0, "size": 100}, {"price": 9.9, "size": 50}],
            "asks": [{"price": 10.1, "size": 80}, {"price": 10.2, "size": 40}],
        }
        bbo = best_bid_ask(snapshot)
        self.assertIsNotNone(bbo)
        assert bbo is not None
        self.assertEqual(bbo["bid_price"], 10.0)
        self.assertEqual(bbo["ask_price"], 10.1)
        ratio = depth_imbalance(snapshot["bids"], snapshot["asks"])
        self.assertGreater(ratio, 1.0)
        self.assertEqual(direction_from_imbalance(ratio), "supports_long")
        ofi = snapshot_ofi(snapshot, {**snapshot, "bids": [{"price": 10.05, "size": 120}]})
        self.assertIsInstance(ofi, float)

    def test_futures_contract_month(self) -> None:
        value = quarterly_contract_month()
        self.assertEqual(len(value), 6)

    def test_futures_depth_signal(self) -> None:
        bids = [{"size": 150}, {"size": 50}]
        asks = [{"size": 10}, {"size": 10}]
        signal, ratio = depth_imbalance_signal(bids, asks, threshold=1.5)
        self.assertEqual(signal, "supports_short")
        self.assertGreater(ratio, 1.0)

    def test_readiness_summary(self) -> None:
        rows = [{"outcome": {"status": "PASS"}}, {"outcome": {"status": "INCOMPLETE"}}]
        totals = readiness_summary(rows)
        self.assertEqual(totals["PASS"], 1)
        self.assertEqual(totals["INCOMPLETE"], 1)


if __name__ == "__main__":
    unittest.main()
