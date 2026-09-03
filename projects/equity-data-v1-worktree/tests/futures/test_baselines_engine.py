"""Tests for futures trend + carry baselines engine (F5)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.futures_quality import FuturesQualityFlag
from market_platform_foundation.futures.baselines import (
    BASELINES_VERSION,
    MIN_BARS_FOR_BASELINES,
    TrendRegime,
    baselines_payload,
    compute_carry_percentile,
    compute_vol_scaled_trend,
    filter_pit_bars,
    trend_regime,
)
from market_platform_foundation.futures.carry import carry_payload
from market_platform_foundation.futures.curve import build_curve_snapshot_from_chain
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.fixture_futures_bars import (
    DEFAULT_BARS_FIXTURE,
    FixtureFuturesBarsProvider,
)
from market_platform_foundation.providers.adapters.fixture_futures_chain import FixtureFuturesChainProvider
from market_platform_foundation.donor_bridge.cross_lane_adapter import build_cross_lane_snapshot_from_futures


class BaselinesEngineTests(unittest.TestCase):
    def test_filter_pit_bars_excludes_future_bar(self) -> None:
        bars = [
            {"event_time": "2025-06-02T14:40:00.000000000Z", "close": 6001.75},
            {"event_time": "2025-06-03T20:00:00.000000000Z", "close": 6010.0},
        ]
        pit, flags = filter_pit_bars(bars, "2025-06-02T14:41:07.000000000Z")
        self.assertEqual(len(pit), 1)
        self.assertEqual(pit[0]["close"], 6001.75)

    def test_filter_pit_bars_insufficient_history_flag(self) -> None:
        bars = [{"event_time": "2025-06-01T20:00:00Z", "close": 5990.0}]
        _, flags = filter_pit_bars(bars, "2025-06-02T14:41:07.000000000Z")
        self.assertIn(FuturesQualityFlag.TREND_HISTORY_INSUFFICIENT.value, flags)

    def test_compute_vol_scaled_trend(self) -> None:
        closes = [100.0] * 70 + [110.0]
        trend = compute_vol_scaled_trend(closes, 63, 0.01)
        assert trend is not None
        self.assertGreater(trend, 0)

    def test_trend_regime_thresholds(self) -> None:
        self.assertEqual(trend_regime({"trend_3m": 0.6}), TrendRegime.TREND_UP)
        self.assertEqual(trend_regime({"trend_3m": -0.6}), TrendRegime.TREND_DOWN)
        self.assertEqual(trend_regime({"trend_3m": 0.1}), TrendRegime.NEUTRAL)

    def test_compute_carry_percentile(self) -> None:
        history = [0.01, 0.02, 0.03, 0.04]
        self.assertEqual(compute_carry_percentile(0.04, history), 1.0)
        self.assertEqual(compute_carry_percentile(0.01, history), 0.25)

    def test_es_baselines_golden_fixture_regression(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "futures" / "es_baselines_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(str(expected["cutoff"]))
        bars_result = FixtureFuturesBarsProvider().fetch_bars(
            expected["symbol"],
            as_of_time_ns=cutoff,
        )
        chain_result = FixtureFuturesChainProvider().fetch_chain(
            expected["symbol"],
            as_of_time_ns=cutoff,
        )
        curve = build_curve_snapshot_from_chain(chain_result)
        carry = carry_payload(curve, spot_reference=5995.0) if curve else {"available": False}
        payload = baselines_payload(
            bars_result,
            curve,
            carry,
            decision_time=cutoff,
        )
        exp = expected["expected"]
        self.assertEqual(payload["available"], exp["available"])
        self.assertEqual(payload["futures_baselines_available"], exp["futures_baselines_available"])
        self.assertEqual(payload["trend_regime"], exp["trend_regime"])
        self.assertEqual(payload["baselines_version"], BASELINES_VERSION)

        trend = payload["trend_baseline_snapshot"]
        exp_trend = exp["trend_baseline_snapshot"]
        self.assertEqual(trend["trend_1m"], exp_trend["trend_1m"])
        self.assertEqual(trend["trend_3m"], exp_trend["trend_3m"])
        self.assertEqual(trend["trend_6m"], exp_trend["trend_6m"])
        self.assertEqual(trend["trend_12m"], exp_trend["trend_12m"])
        self.assertEqual(trend["vol_estimate"], exp_trend["vol_estimate"])
        self.assertEqual(trend["observation_time"], exp_trend["observation_time"])

        carry_baseline = payload["carry_baseline"]
        exp_carry = exp["carry_baseline"]
        self.assertEqual(carry_baseline["carry_percentile"], exp_carry["carry_percentile"])
        self.assertEqual(carry_baseline["formula_tag"], exp_carry["formula_tag"])

        momentum = payload["curve_momentum"]
        exp_momentum = exp["curve_momentum"]
        self.assertEqual(momentum["calendar_spread_momentum"], exp_momentum["calendar_spread_momentum"])
        self.assertEqual(momentum["regime"], exp_momentum["regime"])

    def test_cross_lane_emits_trend_up_from_baselines(self) -> None:
        futures_payload = {
            "available": True,
            "snapshot_count": 1,
            "futures_baselines_available": True,
            "trend_regime": "TREND_UP",
            "trend_baseline_snapshot": {
                "trend_3m": 3.3,
                "vol_estimate": 0.005,
            },
        }
        snapshot, evidence = build_cross_lane_snapshot_from_futures(futures_payload)
        assert snapshot is not None
        self.assertTrue(snapshot.get("futures_baselines_available"))
        signals = [row["signal"] for row in evidence]
        self.assertIn("FUTURES_TREND_UP", signals)

    def test_bars_fixture_lookahead_not_in_adapter_at_cutoff(self) -> None:
        cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
        result = FixtureFuturesBarsProvider(fixture_path=DEFAULT_BARS_FIXTURE).fetch_bars(
            "ES",
            as_of_time_ns=cutoff,
        )
        self.assertEqual(result.status, "available")
        closes = [
            row.get("close")
            for row in result.events
            if isinstance(row, dict) and not row.get("_meta")
        ]
        self.assertIn(6001.75, closes)
        self.assertNotIn(6010.0, closes)
        self.assertGreaterEqual(len(closes), MIN_BARS_FOR_BASELINES)


if __name__ == "__main__":
    unittest.main()
