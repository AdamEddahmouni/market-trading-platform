"""Tests for FuturesX explore bridge."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge.futures_projections import build_explore_futures_payload


class FuturesBridgeTests(unittest.TestCase):
    def test_unavailable_when_server_down(self) -> None:
        payload = build_explore_futures_payload(as_of_context={"mode": "REPLAY"})
        if payload["available"]:
            self.skipTest("futures bridge running on :8788")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["symbol"], "ES")
        self.assertIn("bridge", str(payload.get("reason", "")).lower())

    def test_available_when_server_up(self) -> None:
        payload = build_explore_futures_payload(as_of_context={"mode": "REPLAY"})
        if not payload["available"]:
            self.skipTest("futures bridge not running on :8788")
        self.assertEqual(payload["symbol"], "ES")
        self.assertTrue(payload.get("bridge_url"))


if __name__ == "__main__":
    unittest.main()
