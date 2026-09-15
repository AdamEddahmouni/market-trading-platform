"""Lane F — Edge Stats opportunity research-artifact evidence (non-blocking, evidence-only)."""

from __future__ import annotations

import unittest
from unittest import mock

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.ingest.research_artifact_attachment import (
    ResearchArtifactAttachmentRuntime,
)
from market_platform_foundation.intelligence.opportunity.research_artifact_evidence import (
    EDGE_STATS_OPPORTUNITY_EVIDENCE_PLATFORM_READY,
    EDGE_STATS_OPPORTUNITY_EVIDENCE_READY,
    RESEARCH_ARTIFACT_EVIDENCE_ATTACHED,
    RESEARCH_ARTIFACT_EVIDENCE_NOT_ATTACHED,
    project_historical_statistical_context,
)
from market_platform_foundation.research.edge_stats.precomputed_catalog import (
    runtime_precomputed_catalog_path,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.research.edge_stats.artifact import AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION
from market_platform_foundation.ui_api.opportunity_projections import (
    build_opportunity_detail_payload,
    build_opportunity_evidence_payload,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.research_artifact_evidence import (
    handle_research_artifact_attachment_post,
)
from market_platform_foundation.ui_api.store import ReplayStore

from pathlib import Path

from tests.ui1.test_ui_api import COLLECTION_ROOT

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "research"
    / "edge_stats_golden_artifact.json"
)
_GOLDEN_SHA = "4808F8F9F724FDC3E16B737A1EE33CC96F6EAE431BA6C12D2B7E2575ECA2E62A"
_QUERY_HASH = "11D4AB41B1309ADE04916A06654B6371B0DCAD192D3FE08B32E2F63DE02236D3"


class OpportunityResearchArtifactEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.repo = InMemoryIntelligenceRepository()
        self.opportunity = OpportunityV1(
            opportunity_id="opp-edge-stats-1",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("BIYA",), context_id="regular"),
            created_at_ns=1_700_000_000_000_000_000,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            expected_return=0.1,
            expected_net_edge=0.05,
            reason_summary="BIYA squeeze context",
            lineage_refs=(ContractReference(kind="forecast", id="fc-edge-1"),),
        )
        self.repo.put_opportunity(self.opportunity)
        self.store.strategy_repository = self.repo

    def _attach_default(self) -> None:
        handle_research_artifact_attachment_post(
            self.store,
            {
                "attachment_id": "esa-biya-default",
                "opportunity_id": self.opportunity.opportunity_id,
                "artifact_type": "EDGE_STATS_EVIDENCE_ARTIFACT",
                "content_sha256": _GOLDEN_SHA,
                "query_version_hash": _QUERY_HASH,
                "attached_at": "2026-09-14T22:05:00.000000Z",
            },
        )

    def test_readiness_marker(self) -> None:
        self.assertEqual(
            EDGE_STATS_OPPORTUNITY_EVIDENCE_READY,
            EDGE_STATS_OPPORTUNITY_EVIDENCE_PLATFORM_READY,
        )

    def test_runtime_catalog_is_not_under_tests_fixtures(self) -> None:
        catalog_path = runtime_precomputed_catalog_path()
        self.assertTrue(catalog_path.is_file())
        self.assertIn("artifacts", catalog_path.parts)
        self.assertNotIn("tests", catalog_path.parts)

    def test_evidence_without_attach_marks_platform_ready_not_attached(self) -> None:
        evidence = build_opportunity_evidence_payload(self.store, self.opportunity.opportunity_id)
        block = evidence.get("research_artifact_evidence") or {}
        self.assertEqual(
            block.get("platform_readiness"),
            "MULTI_RESEARCH_ARTIFACT_EVIDENCE_PLATFORM_READY",
        )
        self.assertEqual(block.get("attachment_status"), RESEARCH_ARTIFACT_EVIDENCE_NOT_ATTACHED)

    def test_summary_does_not_block_on_research_artifact_overlay(self) -> None:
        self._attach_default()
        summary = build_opportunities_summary_payload(self.store)
        for item in summary.get("items") or []:
            if item.get("opportunity_id") == self.opportunity.opportunity_id:
                self.assertNotIn("research_artifact_evidence", item)
                self.assertNotIn("historical_statistical_context", item)
                return
        self.fail("minted opportunity missing from summary")

    def test_evidence_payload_includes_historical_context_honestly(self) -> None:
        self._attach_default()
        evidence = build_opportunity_evidence_payload(self.store, self.opportunity.opportunity_id)
        block = evidence.get("research_artifact_evidence") or {}
        self.assertEqual(block.get("readiness"), EDGE_STATS_OPPORTUNITY_EVIDENCE_PLATFORM_READY)
        self.assertEqual(block.get("platform_readiness"), "MULTI_RESEARCH_ARTIFACT_EVIDENCE_PLATFORM_READY")
        self.assertEqual(block.get("attachment_status"), RESEARCH_ARTIFACT_EVIDENCE_ATTACHED)
        self.assertEqual(block.get("authority_class"), AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION)
        attachments = block.get("attachments") or []
        self.assertEqual(len(attachments), 1)
        ctx = attachments[0].get("historical_statistical_context") or {}
        self.assertEqual(ctx.get("sample_n"), 124)
        self.assertEqual(ctx.get("authority_class"), AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION)
        morning = (ctx.get("time_splits") or {}).get("utc_morning_before_12") or {}
        self.assertEqual(morning.get("status"), "INSUFFICIENT_DATA")
        stability = ctx.get("stability_status") or {}
        self.assertEqual(stability.get("status"), "DIVERGENT")
        self.assertNotIn("rank_score", evidence)
        self.assertNotIn("probability", evidence)

    def test_detail_lineage_gains_research_attachment_ref(self) -> None:
        self._attach_default()
        detail = build_opportunity_detail_payload(self.store, self.opportunity.opportunity_id)
        kinds = {ref.get("kind") for ref in detail.get("lineage_refs") or [] if isinstance(ref, dict)}
        self.assertIn("research_evidence_artifact", kinds)

    def test_attach_fails_closed_on_unknown_artifact(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            handle_research_artifact_attachment_post(
                self.store,
                {
                    "attachment_id": "esa-bad",
                    "opportunity_id": self.opportunity.opportunity_id,
                    "artifact_type": "EDGE_STATS_EVIDENCE_ARTIFACT",
                    "content_sha256": "0" * 64,
                    "attached_at": "2026-09-14T22:05:00.000000Z",
                },
            )
        self.assertIn("ARTIFACT_NOT_IN_CATALOG", str(ctx.exception))

    def test_attach_fails_closed_on_missing_opportunity(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            handle_research_artifact_attachment_post(
                self.store,
                {
                    "attachment_id": "esa-missing-opp",
                    "opportunity_id": "opp-does-not-exist",
                    "artifact_type": "EDGE_STATS_EVIDENCE_ARTIFACT",
                    "content_sha256": _GOLDEN_SHA,
                    "attached_at": "2026-09-14T22:05:00.000000Z",
                },
            )
        self.assertIn("OPPORTUNITY_NOT_FOUND", str(ctx.exception))

    def test_attach_fails_closed_on_scope_mismatch(self) -> None:
        wrong_scope = OpportunityV1(
            opportunity_id="opp-edge-stats-wrong-scope",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="regular"),
            created_at_ns=1_700_000_000_000_000_001,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            expected_return=0.1,
            expected_net_edge=0.05,
            reason_summary="wrong instrument scope",
            lineage_refs=(ContractReference(kind="forecast", id="fc-aapl-1"),),
        )
        self.repo.put_opportunity(wrong_scope)
        with self.assertRaises(ValueError) as ctx:
            handle_research_artifact_attachment_post(
                self.store,
                {
                    "attachment_id": "esa-scope-mismatch",
                    "opportunity_id": wrong_scope.opportunity_id,
                    "artifact_type": "EDGE_STATS_EVIDENCE_ARTIFACT",
                    "content_sha256": _GOLDEN_SHA,
                    "attached_at": "2026-09-14T22:05:00.000000Z",
                },
            )
        self.assertIn("SCOPE_MISMATCH", str(ctx.exception))

    def test_runtime_does_not_invoke_edge_stats_pipeline(self) -> None:
        runtime = ResearchArtifactAttachmentRuntime(
            self.repo,
            get_opportunity=self.repo.get_opportunity,
        )
        with mock.patch(
            "market_platform_foundation.research.edge_stats.pipeline.run_edge_stats_pipeline",
        ) as mocked:
            runtime.attach(
                {
                    "attachment_id": "esa-runtime",
                    "opportunity_id": self.opportunity.opportunity_id,
                    "artifact_type": "EDGE_STATS_EVIDENCE_ARTIFACT",
                    "content_sha256": _GOLDEN_SHA,
                    "attached_at": "2026-09-14T22:05:00.000000Z",
                }
            )
            mocked.assert_not_called()

    def test_projection_matches_golden_fixture_fields(self) -> None:
        artifact = load_json_strict(_FIXTURE)
        ctx = project_historical_statistical_context(artifact)
        self.assertEqual(ctx["dataset"]["source_object_id"], "ADMITTED-SHORTSQ-BIYA-BARS-001")
        self.assertEqual(ctx["confidence_interval"]["status"], "OK")


if __name__ == "__main__":
    unittest.main()
