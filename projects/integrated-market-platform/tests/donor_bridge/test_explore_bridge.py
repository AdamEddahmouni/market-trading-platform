"""Tests for short-squeeze explore bridge."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge.projections import build_explore_squeeze_payload
from market_platform_foundation.donor_patterns.cvd_formulas import classify_aggressor


class ExploreBridgeTests(unittest.TestCase):
    def test_unavailable_when_server_down(self) -> None:
        payload = build_explore_squeeze_payload(base_url="http://127.0.0.1:59999")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["rows"], [])

    def test_available_when_server_up(self) -> None:
        payload = build_explore_squeeze_payload(base_url="http://127.0.0.1:8787")
        if not payload["available"]:
            self.skipTest("squeeze FROZEN_DEMO server not running on :8787")
        self.assertEqual(payload["row_count"], 13)
        self.assertTrue(payload["rows"][0]["symbol"])

    def test_cvd_pattern_still_stdlib(self) -> None:
        self.assertEqual(classify_aggressor(2.0, 10, 1.0, 2.0, 1.5), 10.0)


if __name__ == "__main__":
    unittest.main()
