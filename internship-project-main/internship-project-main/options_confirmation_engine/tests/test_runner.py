"""Unit tests for options runner output shape."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import options_engine.runner as runner


class RunnerTests(unittest.TestCase):
    """Validate runner returns expected output structure."""

    def test_run_ticker_output_fields(self) -> None:
        settings = {
            "chain": {"expiries_to_scan": 1, "min_open_interest": 1, "min_contract_volume": 1},
            "features": {"atm_strike_band_pct": 0.03, "iv_rank_lookback_days": 60},
            "scoring": {"weights": {"put_call_volume_ratio": 10, "call_volume_vs_avg": 10, "put_volume_vs_avg": 10, "atm_iv_change": 10, "iv_rank": 10, "oi_near_spot_concentration": 10, "volume_to_oi_spike": 10}},
            "runtime": {"state_write_atomic": True},
            "logging": {"save_raw_snapshot": False},
        }
        result = runner.run_ticker("AAPL", settings=settings, as_of="2026-06-07T20:00:00+00:00")
        self.assertIn("ticker", result)
        self.assertIn("options_score", result)
        self.assertIn("options_bias", result)
        self.assertIn("feature_values", result)


if __name__ == "__main__":
    unittest.main()

