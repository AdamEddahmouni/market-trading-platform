"""Radar feed HTTP contracts: UNREADY next_action, Live fail-closed acks."""

from __future__ import annotations

import unittest

from market_platform_foundation.ui_api.opportunity_projections import (
    apply_opportunity_ack,
    build_opportunity_detail_payload,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT


class OpportunityRadarFeedTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_operator_acks()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()

    def test_unready_feed_points_to_control_without_ranking_items(self) -> None:
        bar = self.store.current_bar()
        bar["quality_state"] = "STALE"
        payload = build_opportunities_summary_payload(self.store)
        self.assertEqual(payload["feed_status"], "UNREADY")
        self.assertEqual(payload["unready_reason"], "QUALITY_SUMMARY_NOT_HEALTHY")
        self.assertEqual(payload["next_action"], "/control")
        for item in payload["items"]:
            self.assertNotIn("rank_score", item)
            self.assertNotIn("universal_score", item)
            self.assertNotIn("order_id", item)

    def test_live_ack_fail_closed(self) -> None:
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        with self.assertRaises(PermissionError) as ack_ctx:
            apply_opportunity_ack(self.store, row_id="any-id", action="DISMISSED")
        self.assertEqual(str(ack_ctx.exception), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")

    def test_live_detail_read_missing_id_is_not_found(self) -> None:
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        with self.assertRaises(KeyError) as detail_ctx:
            build_opportunity_detail_payload(self.store, "any-id")
        self.assertEqual(str(detail_ctx.exception), "'any-id'")
        self.assertNotIn("LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE", str(detail_ctx.exception))


if __name__ == "__main__":
    unittest.main()
