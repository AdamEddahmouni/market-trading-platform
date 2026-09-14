"""STALE order-flow must not rank fusion liquidity or fall back to leftover flags."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.extractors import extract_liquidity_input  # noqa: E402
from market_platform_foundation.cross_lane.fusion import fuse_opportunity_v1  # noqa: E402
from market_platform_foundation.cross_lane.opportunity import (  # noqa: E402
    CostInput,
    OpportunityQualityFlag,
    PayoffInput,
    ProbabilityInput,
)


def _stale_ofi_payload() -> dict:
    return {
        "available": True,
        "cvd_summary": {"cvd_confidence": 0.9},
        "ofi_value": 0.42,
        "provenance": {"freshness_state": "STALE"},
        "reason": "STALE_BOOK",
        "state": "STALE",
    }


class StaleOrderFlowFailClosedTests(unittest.TestCase):
    def test_stale_payload_does_not_admit_cvd_or_imbalance(self) -> None:
        liquidity = extract_liquidity_input(
            cross_lane_snapshot={
                "order_flow_aggressive_buy": True,
                "order_flow_cvd_confidence": 0.8,
            },
            order_flow_payload=_stale_ofi_payload(),
        )
        self.assertFalse(liquidity.available)
        self.assertFalse(liquidity.gates_passed)
        self.assertIsNone(liquidity.cvd_confidence)
        self.assertFalse(liquidity.book_imbalance_supports_trade)
        self.assertEqual(liquidity.reason, "STALE_ORDER_FLOW")
        self.assertIn(OpportunityQualityFlag.FUSION_INPUTS_INCOMPLETE.value, liquidity.quality_flags)

    def test_unavailable_stale_state_is_rejected_even_when_available_false(self) -> None:
        liquidity = extract_liquidity_input(
            order_flow_payload={
                "available": False,
                "reason": "STALE_BOOK",
                "state": "STALE",
            }
        )
        self.assertFalse(liquidity.available)
        self.assertEqual(liquidity.reason, "STALE_ORDER_FLOW")

    def test_fusion_does_not_rank_stale_order_flow(self) -> None:
        liquidity = extract_liquidity_input(order_flow_payload=_stale_ofi_payload())
        fused = fuse_opportunity_v1(
            ProbabilityInput(available=True, scenario_win_probability=0.6),
            PayoffInput(available=True, expected_pnl=10.0, template="long_call_atm"),
            CostInput(available=True, friction_cost=0.1),
            liquidity,
        )
        self.assertFalse(fused["available"])
        self.assertEqual(fused["outcome"], "UNAVAILABLE")
        self.assertEqual(fused["reason"], "STALE_ORDER_FLOW")
        self.assertIsNone(fused["fusion"])
