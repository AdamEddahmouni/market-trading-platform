"""HTTP contract tests for Opportunity Engine operator routes."""

from __future__ import annotations

import unittest

from market_platform_foundation.ui_api.opportunity_projections import (
    apply_opportunity_ack,
    build_opportunity_detail_payload,
    build_opportunity_evidence_payload,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT


class OpportunityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_operator_acks()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()

    def test_summary_has_no_universal_score_and_no_live_leak(self) -> None:
        payload = build_opportunities_summary_payload(self.store)
        self.assertIn(payload["feed_status"], {"READY", "EMPTY", "UNREADY"})
        for item in payload["items"]:
            self.assertNotIn("rank_score", item)
            self.assertNotIn("universal_score", item)
            self.assertNotIn("order_id", item)
            self.assertIn("ranking_vector", item)
            self.assertIn("identity_kind", item)

    def test_live_mode_returns_unavailable_empty_queue(self) -> None:
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        payload = build_opportunities_summary_payload(self.store)
        self.assertEqual(payload["feed_status"], "UNAVAILABLE")
        self.assertEqual(payload["reason"], "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
        self.assertEqual(payload["items"], [])

    def test_demo_cannot_dismiss(self) -> None:
        summary = build_opportunities_summary_payload(self.store)
        if not summary["items"]:
            self.skipTest("no adapter rows in replay fixture")
        row_id = summary["items"][0]["summary_id"]
        with self.assertRaises(PermissionError):
            apply_opportunity_ack(self.store, row_id=row_id, action="DISMISSED")

    def test_paper_dismiss_round_trip_does_not_fabricate_evidence(self) -> None:
        self.store.execution_mode = "INTERNAL_SIMULATION"
        summary = build_opportunities_summary_payload(self.store)
        if not summary["items"]:
            self.skipTest("no adapter rows in replay fixture")
        row_id = summary["items"][0]["summary_id"]
        ack = apply_opportunity_ack(self.store, row_id=row_id, action="DISMISSED")
        self.assertEqual(ack["action"], "DISMISSED")
        after = build_opportunities_summary_payload(self.store)
        ids = {item["summary_id"] for item in after["items"]}
        self.assertNotIn(row_id, ids)
        detail = build_opportunity_detail_payload(self.store, row_id)
        self.assertEqual(detail["lifecycle_state"], "DISMISSED")
        evidence = build_opportunity_evidence_payload(self.store, row_id)
        self.assertIsInstance(evidence["items"], list)

    def test_unknown_id_fail_closed(self) -> None:
        with self.assertRaises(KeyError):
            build_opportunity_detail_payload(self.store, "missing-id")

    def test_detail_overlay_is_decision_support_not_ranking(self) -> None:
        self.store.execution_mode = "INTERNAL_SIMULATION"
        summary = build_opportunities_summary_payload(self.store)
        if not summary["items"]:
            self.skipTest("no adapter rows in replay fixture")
        first = summary["items"][0]
        orders = [item.get("rank_order") for item in summary["items"]]
        detail = build_opportunity_detail_payload(self.store, first["summary_id"])
        overlay = detail["decision_support"]
        self.assertEqual(overlay["authority"], "DOWNSTREAM_RISK_NOT_RANKING")
        self.assertNotIn("order_id", overlay)
        after = build_opportunities_summary_payload(self.store)
        self.assertEqual([item.get("rank_order") for item in after["items"]], orders)

    def test_evidence_is_lineage_only(self) -> None:
        summary = build_opportunities_summary_payload(self.store)
        if not summary["items"]:
            self.skipTest("no adapter rows in replay fixture")
        evidence = build_opportunity_evidence_payload(self.store, summary["items"][0]["summary_id"])
        self.assertIsInstance(evidence["items"], list)
        self.assertNotIn("fabricated", str(evidence).lower())


if __name__ == "__main__":
    unittest.main()
