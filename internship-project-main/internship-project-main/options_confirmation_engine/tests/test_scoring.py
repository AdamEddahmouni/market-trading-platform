"""Unit tests for options scoring behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from options_engine.scoring import score_options


SETTINGS = {
    "scoring": {
        "weights": {
            "call_volume_share": 25,
            "net_delta_oi": 25,
            "iv_skew": 22,
            "put_call_oi_ratio": 16,
            "put_call_volume_ratio": 12,
        },
        "bullish_threshold": 60,
        "bearish_threshold": 40,
        "min_data_quality_score": 0.6,
        "min_directional_signals": 2,
    }
}


def _features(**overrides) -> dict:
    base = {
        "put_call_volume_ratio": 0.9,
        "call_volume_share": 0.5,
        "put_call_oi_ratio": 1.0,
        "net_delta_oi": 0.0,
        "iv_skew": 0.0,
        "greeks_available": 1.0,
        "iv_skew_available": 1.0,
        "volume_available": 1.0,
        "oi_available": 1.0,
    }
    base.update(overrides)
    return base


class ScoringTests(unittest.TestCase):
    """Validate score range, calibration, and availability handling."""

    def test_neutral_inputs_score_near_50(self) -> None:
        result = score_options("AAPL", _features(), [], SETTINGS)
        self.assertEqual(result["options_bias"], "neutral")
        self.assertAlmostEqual(float(result["options_score"]), 50.0, delta=1.0)
        self.assertGreaterEqual(float(result["options_score"]), 0.0)
        self.assertLessEqual(float(result["options_score"]), 100.0)

    def test_bullish_signals_score_high(self) -> None:
        feats = _features(
            call_volume_share=0.7,
            put_call_volume_ratio=0.6,
            put_call_oi_ratio=0.7,
            net_delta_oi=0.3,
            iv_skew=-0.03,
        )
        result = score_options("AAPL", feats, [], SETTINGS)
        self.assertEqual(result["options_bias"], "bullish")
        self.assertGreater(float(result["options_score"]), 60.0)

    def test_bearish_signals_score_low(self) -> None:
        feats = _features(
            call_volume_share=0.3,
            put_call_volume_ratio=1.4,
            put_call_oi_ratio=1.6,
            net_delta_oi=-0.3,
            iv_skew=0.05,
        )
        result = score_options("AAPL", feats, [], SETTINGS)
        self.assertEqual(result["options_bias"], "bearish")
        self.assertLess(float(result["options_score"]), 40.0)

    def test_too_few_signals_yields_no_data(self) -> None:
        # Only volume-based signals available -> still 2 (share + pcr_vol), so usable;
        # remove volume too and only OI remains (1 signal) -> no_data.
        feats = _features(
            greeks_available=0.0,
            iv_skew_available=0.0,
            volume_available=0.0,
        )
        result = score_options("AAPL", feats, [], SETTINGS)
        self.assertEqual(result["options_bias"], "no_data")

    def test_missing_greeks_renormalizes_without_bias(self) -> None:
        # Strong bullish flow but no greeks; should still read bullish, not neutral.
        feats = _features(
            call_volume_share=0.8,
            put_call_volume_ratio=0.5,
            put_call_oi_ratio=0.6,
            greeks_available=0.0,
            iv_skew_available=0.0,
        )
        result = score_options("AAPL", feats, [], SETTINGS)
        self.assertGreater(float(result["options_score"]), 60.0)


if __name__ == "__main__":
    unittest.main()

