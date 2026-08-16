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
from market_platform_foundation.donor_patterns.options_lane import confirmation_score, liquidity_gate
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

    def test_readiness_summary(self) -> None:
        rows = [{"outcome": {"status": "PASS"}}, {"outcome": {"status": "INCOMPLETE"}}]
        totals = readiness_summary(rows)
        self.assertEqual(totals["PASS"], 1)
        self.assertEqual(totals["INCOMPLETE"], 1)


if __name__ == "__main__":
    unittest.main()
