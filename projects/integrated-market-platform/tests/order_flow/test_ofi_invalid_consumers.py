"""Negative tests: invalid-book OFI 0.0 is not a usable OFI."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.extractors import extract_liquidity_input  # noqa: E402
from market_platform_foundation.donor_bridge.bridge_depth_state import (  # noqa: E402
    clear,
    resolve_bridge_ofi,
    update,
)
from market_platform_foundation.order_flow.evidence import build_order_flow_evidence  # noqa: E402
from market_platform_foundation.order_flow.lob_features import build_lob_feature_vector  # noqa: E402
from market_platform_foundation.order_flow.ofi import compute_multilevel_ofi, usable_ofi_value  # noqa: E402


class InvalidOfiConsumerTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear()

    def test_usable_ofi_none_when_book_invalid(self) -> None:
        valid = {"bids": [{"price": 10.0, "size": 100}], "asks": [{"price": 10.1, "size": 80}]}
        invalid = {"bids": [], "asks": [{"price": 10.1, "size": 80}]}
        result = compute_multilevel_ofi(valid, invalid)
        self.assertFalse(result.book_state_valid)
        self.assertEqual(result.value, 0.0)
        self.assertIsNone(usable_ofi_value(result))

    def test_lob_vector_does_not_treat_invalid_zero_as_signal(self) -> None:
        snapshot = {"bids": [], "asks": []}
        vector = build_lob_feature_vector(snapshot, ofi_value=0.0, book_state_valid=False)
        self.assertFalse(vector.book_state_valid)
        self.assertEqual(vector.ofi_signal, 0.0)
        self.assertIn("BOOK_STATE_INVALID", vector.quality_flags)

    def test_bridge_omits_numeric_ofi_when_invalid(self) -> None:
        update("ES", {"bids": [{"price": 10.0, "size": 1}], "asks": [{"price": 10.1, "size": 1}]})
        state = resolve_bridge_ofi(
            "ES",
            {"bids": [], "asks": [{"price": 10.1, "size": 1}]},
        )
        self.assertFalse(state["book_state_valid"])
        self.assertIsNone(state["ofi_value"])

    def test_fusion_extractor_ignores_invalid_book_imbalance_flags(self) -> None:
        liquidity = extract_liquidity_input(
            cross_lane_snapshot={
                "order_flow_aggressive_buy": True,
                "order_flow_aggressive_sell": True,
            },
            order_flow_payload={
                "available": True,
                "latest_ofi_value": 0.0,
                "latest_book_state_valid": False,
            },
        )
        self.assertFalse(liquidity.book_imbalance_supports_trade)
        self.assertFalse(liquidity.book_imbalance_opposes_trade)

    def test_order_flow_evidence_ofi_none_when_invalid(self) -> None:
        prev = {
            "bids": [{"price": 10.0, "size": 100}],
            "asks": [{"price": 10.1, "size": 80}],
            "book_sequence": 1,
        }
        curr = {
            "bids": [{"price": 10.0, "size": 110}],
            "asks": [{"price": 10.1, "size": 70}],
            "book_sequence": 4,
        }
        evidence = build_order_flow_evidence(
            instrument="NVDA",
            venue="TEST",
            event_time="2026-07-21T19:45:00.000000000Z",
            available_time="2026-07-21T19:45:00.000000000Z",
            snapshot=curr,
            prev_snapshot=prev,
        )
        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertIsNone(evidence.ofi_value)
        self.assertIn("BOOK_STATE_INVALID", evidence.quality_flags)


if __name__ == "__main__":
    unittest.main()
