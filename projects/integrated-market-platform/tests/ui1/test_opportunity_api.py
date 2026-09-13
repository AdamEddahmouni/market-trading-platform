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

    def test_decision_support_does_not_reorder_or_include_order_id(self) -> None:
        from market_platform_foundation.ui_api.opportunity_projections import decision_support_overlay

        payload = build_opportunities_summary_payload(self.store)
        orders = [item.get("rank_order") for item in payload["items"]]
        ids = [item.get("summary_id") for item in payload["items"]]
        overlay = decision_support_overlay()
        overlay["concentration"] = {"status": "WORSE"}
        self.assertNotIn("order_id", overlay)
        again = build_opportunities_summary_payload(self.store)
        self.assertEqual([item.get("rank_order") for item in again["items"]], orders)
        self.assertEqual([item.get("summary_id") for item in again["items"]], ids)
        for item in payload["items"]:
            support = item.get("decision_support") or {}
            self.assertEqual(support.get("authority"), "DOWNSTREAM_RISK_NOT_RANKING")
            self.assertNotIn("order_id", support)
            self.assertNotIn("rank_score", item)

    def test_explain_unknown_id_fail_closed_and_evidence_is_lineage_only(self) -> None:
        from market_platform_foundation.ui_api.projections import build_explain_payload, build_inspect_payload

        with self.assertRaises(ValueError):
            build_explain_payload(self.store, "explain:opportunity:missing-id")
        summary = build_opportunities_summary_payload(self.store)
        if not summary["items"]:
            self.skipTest("no adapter rows in replay fixture")
        item = summary["items"][0]
        ref = item.get("explanation_ref") or f"explain:summary:{item['summary_id']}"
        explain = build_explain_payload(self.store, ref)
        if item.get("identity_kind") == "NOT_OPPORTUNITY_V1":
            self.assertEqual(explain["explanation"]["why"], "not OpportunityV1")
        inspect = build_inspect_payload(self.store, ref.replace("explain:", "inspect:", 1))
        self.assertEqual(inspect["tabs"]["EVIDENCE"]["items"], item.get("lineage_refs") or [])
        evidence = build_opportunity_evidence_payload(self.store, item["summary_id"])
        self.assertEqual(evidence["items"], item.get("lineage_refs") or [])

    def test_unknown_id_fail_closed(self) -> None:
        with self.assertRaises(KeyError):
            build_opportunity_detail_payload(self.store, "missing-id")


if __name__ == "__main__":
    unittest.main()
