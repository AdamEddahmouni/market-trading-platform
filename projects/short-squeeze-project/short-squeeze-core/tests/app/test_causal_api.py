"""Tests for causal API handlers."""

from __future__ import annotations

import unittest

from apps.research_screener.causal_api import evaluate_causal_request


class CausalApiTests(unittest.TestCase):
    def test_evaluate_with_cross_lane_order_flow(self) -> None:
        payload = evaluate_causal_request(
            {
                "row": {
                    "freshness": "CURRENT",
                    "pressure": 55.0,
                    "ignition": 62.0,
                    "adam_classification": "WATCH",
                    "rules": [],
                },
                "cross_lane": {
                    "order_flow_available": True,
                    "order_flow_aggressive_buy": True,
                    "order_flow_cvd_slope": 2.5,
                },
            }
        )
        causal = payload["causal_intelligence"]
        self.assertIn(causal["state"], ("IGNITION_WATCH", "LIVE_CONFIRMATION"))
        codes = {item["code"] for item in causal.get("supporting_evidence", [])}
        self.assertIn("CVD_AGGRESSIVE_BUY", codes)


if __name__ == "__main__":
    unittest.main()
