"""HTTP contract tests for Opportunity Engine operator routes."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.evidence_promotion import (
    EVIDENCE_CLASS_CANDIDATE,
    EVIDENCE_CLASS_VERIFIED,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.ui_api.opportunity_projections import (
    apply_opportunity_ack,
    build_opportunity_detail_payload,
    build_opportunity_evidence_payload,
    build_opportunities_summary_payload,
    build_ranked_rows,
)
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_FORBIDDEN_LIFECYCLE = {"MONITORED", "OUTCOME_RECORDED", "PAPER_SUBMITTED"}
_INGEST_TIMESTAMP_KEYS = {"decision_time_ns", "created_at_ns", "opportunity_decision_time_ns"}


class OpportunityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_operator_acks()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()

    def _seed_opportunity(
        self,
        *,
        opportunity_id: str = "opp-api-1",
        instrument_id: str = "AAPL",
        created_at_ns: int = 1_700_000_000_000_000_000,
        expected_return: float | None = 0.12,
        expected_net_edge: float | None = 0.08,
    ) -> OpportunityV1:
        opportunity = OpportunityV1(
            opportunity_id=opportunity_id,
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id="regular"),
            created_at_ns=created_at_ns,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            expected_return=expected_return,
            expected_net_edge=expected_net_edge,
            reason_summary=f"{instrument_id} candidate",
            lineage_refs=(ContractReference(kind="forecast", id="fc-api-1"),),
        )
        repo = InMemoryIntelligenceRepository()
        repo.put_opportunity(opportunity)
        self.store.strategy_repository = repo
        return opportunity

    def _item_by_opportunity(self, payload: dict, opportunity_id: str) -> dict:
        for item in payload.get("items") or []:
            if item.get("opportunity_id") == opportunity_id:
                return item
        self.fail(f"missing minted opportunity {opportunity_id}")
        raise AssertionError

    def test_summary_has_no_universal_score_and_no_live_leak(self) -> None:
        payload = build_opportunities_summary_payload(self.store)
        self.assertIn(payload["feed_status"], {"READY", "EMPTY", "UNREADY"})
        for item in payload["items"]:
            self.assertNotIn("rank_score", item)
            self.assertNotIn("universal_score", item)
            self.assertNotIn("order_id", item)
            self.assertIn("ranking_vector", item)
            self.assertIn("identity_kind", item)
            self.assertNotIn(item.get("lifecycle_state"), _FORBIDDEN_LIFECYCLE)
            metadata = item.get("metadata") or {}
            self.assertTrue(_INGEST_TIMESTAMP_KEYS.isdisjoint(metadata))

    def test_live_mode_observational_read_is_empty_without_repository_rows(self) -> None:
        # P12: request-path must not emit LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE
        # on ranked READ. Empty live book is EMPTY with live provenance.
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        with patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        ):
            payload = build_opportunities_summary_payload(self.store)
        self.assertEqual(payload["feed_status"], "EMPTY")
        self.assertNotEqual(payload.get("reason"), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
        self.assertEqual(payload["items"], [])
        self.assertNotIn("2026-07-21", str(payload["as_of_context"].get("as_of_time")))

    def test_live_mode_mutations_remain_blocked(self) -> None:
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        with self.assertRaises(PermissionError) as ack_ctx:
            apply_opportunity_ack(self.store, row_id="any-id", action="DISMISSED")
        self.assertEqual(str(ack_ctx.exception), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")

    def test_live_observational_read_ranks_repository_not_fixture_attention(self) -> None:
        # P12: a populated repo must be visible after the read/mutation split.
        # EventV1 admission alone is not sufficient; this is the request-path fix.
        # Fixture attention must stay quarantined so July cards are not ranked.
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        opportunity = self._seed_opportunity()
        with patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        ):
            payload = build_opportunities_summary_payload(self.store)
        self.assertEqual(payload["feed_status"], "READY")
        item = self._item_by_opportunity(payload, opportunity.opportunity_id)
        self.assertEqual(item["identity_kind"], "OPPORTUNITY_V1")
        self.assertFalse(
            any(row.get("attention_id") == "att-replay-context" for row in payload["items"])
        )
        detail = build_opportunity_detail_payload(self.store, opportunity.opportunity_id)
        self.assertEqual(detail["opportunity_id"], opportunity.opportunity_id)
        with self.assertRaises(PermissionError) as ack_ctx:
            apply_opportunity_ack(self.store, row_id=opportunity.opportunity_id, action="WATCHED")
        self.assertEqual(str(ack_ctx.exception), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")

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

    def test_minted_row_projects_contract_and_evidence_fields(self) -> None:
        opportunity = self._seed_opportunity()
        payload = build_opportunities_summary_payload(self.store)
        item = self._item_by_opportunity(payload, opportunity.opportunity_id)
        self.assertEqual(item["identity_kind"], "OPPORTUNITY_V1")
        self.assertEqual(item["instrument_key"], item["instrument_id"])
        self.assertEqual(item["created_at_ns"], opportunity.created_at_ns)
        self.assertEqual(item["expected_return"], opportunity.expected_return)
        self.assertEqual(item["expected_net_edge"], opportunity.expected_net_edge)
        self.assertEqual(item["evidence_class"], EVIDENCE_CLASS_CANDIDATE)
        self.assertNotEqual(item["evidence_class"], EVIDENCE_CLASS_VERIFIED)
        self.assertIn(item["family_admission_status"], {"UNAVAILABLE", "DENIED", "ADMITTED"})
        self.assertIn("evidence_promotion_reason", item)
        self.assertNotIn(item.get("lifecycle_state"), _FORBIDDEN_LIFECYCLE)
        self.assertTrue(_INGEST_TIMESTAMP_KEYS.isdisjoint(item.get("metadata") or {}))
        self.assertNotIn("decision_time_ns", item)
        self.assertNotIn("rank_score", item)

    def test_api_projection_does_not_stamp_review_row_decision_time(self) -> None:
        opportunity = self._seed_opportunity(created_at_ns=1_800_000_000_000_000_000)
        ranked = build_ranked_rows(self.store)
        minted = [row for row in ranked if row.opportunity_id == opportunity.opportunity_id]
        self.assertEqual(len(minted), 1)
        metadata = minted[0].metadata or {}
        self.assertTrue(_INGEST_TIMESTAMP_KEYS.isdisjoint(metadata))
        payload = build_opportunities_summary_payload(self.store)
        item = self._item_by_opportunity(payload, opportunity.opportunity_id)
        self.assertEqual(item["created_at_ns"], 1_800_000_000_000_000_000)
        self.assertTrue(_INGEST_TIMESTAMP_KEYS.isdisjoint(item.get("metadata") or {}))

    def test_evidence_endpoint_projects_review_row_evidence_without_fabricating_verified(self) -> None:
        opportunity = self._seed_opportunity()
        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        self.assertEqual(evidence["identity_kind"], "OPPORTUNITY_V1")
        self.assertEqual(evidence["evidence_class"], EVIDENCE_CLASS_CANDIDATE)
        self.assertNotEqual(evidence["evidence_class"], EVIDENCE_CLASS_VERIFIED)
        self.assertEqual(evidence["created_at_ns"], opportunity.created_at_ns)
        self.assertEqual(evidence["items"], [{"kind": "forecast", "id": "fc-api-1"}])
        self.assertEqual(evidence["lineage_refs"], evidence["items"])
        self.assertIn("evidence_promotion_reason", evidence)
        self.assertIn("family_admission_status", evidence)
        self.assertIn("data_quality", evidence)
        self.assertNotIn("rank_score", evidence)
        self.assertNotIn("order_id", evidence)
        self.assertNotIn("MONITORED", str(evidence.get("evidence_class")))
        self.assertIsNone(evidence.get("copy"))

    def test_attention_evidence_stays_not_opportunity_v1(self) -> None:
        payload = build_opportunities_summary_payload(self.store)
        attention = [
            item for item in payload["items"] if item.get("identity_kind") == "NOT_OPPORTUNITY_V1"
        ]
        if not attention:
            self.skipTest("no adapter rows in replay fixture")
        item = attention[0]
        self.assertEqual(item.get("instrument_key"), item.get("instrument_id"))
        self.assertIsNone(item.get("created_at_ns"))
        self.assertIsNone(item.get("evidence_class"))
        evidence = build_opportunity_evidence_payload(self.store, item["summary_id"])
        self.assertEqual(evidence["copy"], "not OpportunityV1")
        self.assertIsNone(evidence["evidence_class"])
        self.assertEqual(evidence["items"], item.get("lineage_refs") or [])


if __name__ == "__main__":
    unittest.main()
