"""Tests for donor-bridge OFI carry and degrade semantics (OF-D10)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.donor_bridge.bridge_depth_state import (
    clear,
    resolve_bridge_ofi,
    update,
)
from market_platform_foundation.order_flow.ofi import OFI_METHOD_MULTILEVEL_CS


def _snapshot(bid_price: float, bid_size: float, ask_price: float, ask_size: float) -> dict:
    return {
        "bids": [{"price": bid_price, "size": bid_size}],
        "asks": [{"price": ask_price, "size": ask_size}],
        "source": "test_bridge",
    }


class FuturesBridgeOfiTests(unittest.TestCase):
    def setUp(self) -> None:
        clear()

    def test_first_fetch_degraded_without_prev(self) -> None:
        snap = _snapshot(6000.0, 50.0, 6000.25, 10.0)
        state = resolve_bridge_ofi("ES", snap)
        self.assertIsNone(state["ofi_value"])
        self.assertTrue(state["ofi_degraded"])
        self.assertEqual(state["ofi_quality_flags"], ["NO_PREV_SNAPSHOT"])
        self.assertFalse(state["book_state_valid"])

    def test_second_fetch_computes_ofi_with_metadata(self) -> None:
        prev = _snapshot(6000.0, 50.0, 6000.25, 10.0)
        curr = _snapshot(6000.25, 45.0, 6000.5, 12.0)
        update("ES", prev)
        state = resolve_bridge_ofi("ES", curr)
        self.assertFalse(state["ofi_degraded"])
        self.assertTrue(state["book_state_valid"])
        self.assertEqual(state["ofi_method"], OFI_METHOD_MULTILEVEL_CS)
        self.assertIsNotNone(state["ofi_version"])
        self.assertIsNotNone(state["ofi_value"])

    def test_degraded_path_never_uses_zero_as_valid_ofi(self) -> None:
        snap = _snapshot(6000.0, 50.0, 6000.25, 10.0)
        state = resolve_bridge_ofi("ES", snap)
        self.assertIsNone(state["ofi_value"])
        self.assertNotEqual(state.get("ofi_value"), 0.0)


if __name__ == "__main__":
    unittest.main()
