"""Tests for internship catalyst read-only bridge."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge import internship_client  # noqa: E402
from market_platform_foundation.donor_bridge.projections import (  # noqa: E402
    build_catalyst_attention_items,
    build_explore_catalyst_payload,
    build_workspace_catalyst_payload,
)


class CatalystBridgeTests(unittest.TestCase):
    def test_unavailable_when_state_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_explore_catalyst_payload(state_dir=Path(tmp))
            self.assertFalse(payload["available"])
            self.assertEqual(payload["rows"], [])

    def test_available_with_seeded_demo_state(self) -> None:
        state_dir = internship_client.default_state_dir()
        if not internship_client.is_available(state_dir=state_dir):
            self.skipTest("internship demo state not seeded")
        payload = build_explore_catalyst_payload(state_dir=state_dir)
        self.assertTrue(payload["available"])
        self.assertGreater(payload["row_count"], 0)
        symbols = {row["symbol"] for row in payload["rows"]}
        self.assertIn("BOXL", symbols)

    def test_workspace_symbol_detail(self) -> None:
        state_dir = internship_client.default_state_dir()
        if not internship_client.is_available(state_dir=state_dir):
            self.skipTest("internship demo state not seeded")
        payload = build_workspace_catalyst_payload("BOXL", state_dir=state_dir)
        self.assertTrue(payload["available"])
        self.assertIsNotNone(payload["trade_signal"])
        self.assertTrue(payload["evidence_cards"])

    def test_workspace_unknown_symbol(self) -> None:
        state_dir = internship_client.default_state_dir()
        if not internship_client.is_available(state_dir=state_dir):
            self.skipTest("internship demo state not seeded")
        payload = build_workspace_catalyst_payload("ZZZZ", state_dir=state_dir)
        self.assertFalse(payload["available"])

    def test_attention_items(self) -> None:
        state_dir = internship_client.default_state_dir()
        if not internship_client.is_available(state_dir=state_dir):
            self.skipTest("internship demo state not seeded")
        items = build_catalyst_attention_items(state_dir=state_dir, limit=3)
        self.assertGreaterEqual(len(items), 1)
        self.assertTrue(items[0]["explanation_ref"].startswith("explain:catalyst:"))


if __name__ == "__main__":
    unittest.main()
