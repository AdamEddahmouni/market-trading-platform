"""Unit tests for options feature calculations."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from options_engine.data_models import ContractRow, Snapshot
from options_engine.features import compute_features


class FeatureTests(unittest.TestCase):
    """Validate feature output shape and key metrics."""

    def _settings(self) -> dict:
        return {
            "features": {
                "atm_strike_band_pct": 0.05,
                "iv_rank_lookback_days": 60,
                "skew_delta_low": 0.15,
                "skew_delta_high": 0.35,
            }
        }

    def test_compute_features_basic(self) -> None:
        snapshot = Snapshot(
            ticker="TEST",
            as_of="2026-06-07T20:00:00+00:00",
            spot_price=100.0,
            contracts=[
                ContractRow("C1", "call", 100, "2026-07-01", 0.3, 100, 200, 1.0, 1.2, 1.1, False),
                ContractRow("P1", "put", 100, "2026-07-01", 0.32, 80, 250, 1.1, 1.3, 1.2, False),
            ],
        )
        history = [{"feature_cache": {"atm_iv": 0.25}}]
        output = compute_features(snapshot, history, self._settings())
        self.assertIn("put_call_volume_ratio", output)
        self.assertIn("call_volume_share", output)
        self.assertIn("net_delta_oi", output)
        self.assertIn("iv_skew", output)
        # call_volume_share = 100 / (100 + 80)
        self.assertAlmostEqual(output["call_volume_share"], 100.0 / 180.0)
        # put/call OI ratio = 250 / 200
        self.assertAlmostEqual(output["put_call_oi_ratio"], 1.25)

    def test_net_delta_oi_uses_greeks(self) -> None:
        # Calls carry +delta, puts -delta; call-heavy OI -> positive net delta.
        snapshot = Snapshot(
            ticker="TEST",
            as_of="2026-06-07T20:00:00+00:00",
            spot_price=100.0,
            contracts=[
                ContractRow("C1", "call", 105, "2026-07-01", 0.30, 100, 1000, 1.0, 1.2, 1.1, False, delta=0.25),
                ContractRow("P1", "put", 95, "2026-07-01", 0.40, 100, 200, 1.0, 1.2, 1.1, False, delta=-0.25),
            ],
        )
        output = compute_features(snapshot, [], self._settings())
        self.assertEqual(output["greeks_available"], 1.0)
        self.assertGreater(output["net_delta_oi"], 0.0)
        # OTM put IV (0.40) > OTM call IV (0.30) -> positive (bearish) skew
        self.assertEqual(output["iv_skew_available"], 1.0)
        self.assertAlmostEqual(output["iv_skew"], 0.10)

    def test_greeks_unavailable_without_delta(self) -> None:
        snapshot = Snapshot(
            ticker="TEST",
            as_of="2026-06-07T20:00:00+00:00",
            spot_price=100.0,
            contracts=[
                ContractRow("C1", "call", 100, "2026-07-01", 0.3, 100, 200, 1.0, 1.2, 1.1, False),
                ContractRow("P1", "put", 100, "2026-07-01", 0.32, 80, 250, 1.1, 1.3, 1.2, False),
            ],
        )
        output = compute_features(snapshot, [], self._settings())
        self.assertEqual(output["greeks_available"], 0.0)
        self.assertEqual(output["net_delta_oi"], 0.0)


if __name__ == "__main__":
    unittest.main()

