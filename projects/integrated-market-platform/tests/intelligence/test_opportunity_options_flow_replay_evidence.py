"""Lane I — options-flow replay research-artifact attach (cold path, evidence-only)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

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
    OPTIONS_FLOW_REPLAY_EVIDENCE_READY,
    project_options_flow_transparent_context,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.research.edge_stats.artifact import AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION
from market_platform_foundation.research.options_flow_replay.artifact import ARTIFACT_TYPE
from market_platform_foundation.ui_api.opportunity_projections import (
    build_opportunity_evidence_payload,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.research_artifact_evidence import (
    handle_research_artifact_attachment_post,
)
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_GOLDEN_SHA = "8396D6B3FF31ECE0743F728F5AA2D753133A8F7C689FD566EBCB3C68CC0EF3BF"
_QUERY_HASH = "0A881C40BAA1C28F725C7A22435DEE1712A2F5589210958C1EC916B036C17126"
_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "research"
    / "options_flow_replay_golden_artifact.json"
)


class OpportunityOptionsFlowReplayEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.repo = InMemoryIntelligenceRepository()
        self.opportunity = OpportunityV1(
            opportunity_id="opp-options-flow-replay-1",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("NVDA",), context_id="regular"),
            created_at_ns=1_700_000_000_000_000_000,
            quality=QualitySummary(state=QualityState.GOOD),
            side=OpportunitySide.LONG,
            expected_return=0.1,
            expected_net_edge=0.05,
            reason_summary="NVDA replay context",
            lineage_refs=(ContractReference(kind="forecast", id="fc-nvda-1"),),
        )
        self.repo.put_opportunity(self.opportunity)
        self.store.strategy_repository = self.repo

    def _attach_default(self) -> None:
        handle_research_artifact_attachment_post(
            self.store,
            {
                "attachment_id": "ofr-nvda-default",
                "opportunity_id": self.opportunity.opportunity_id,
                "artifact_type": ARTIFACT_TYPE,
                "content_sha256": _GOLDEN_SHA,
                "query_version_hash": _QUERY_HASH,
                "attached_at": "2026-09-14T22:35:00.000000Z",
            },
        )

    def test_summary_does_not_surface_replay_overlay(self) -> None:
        self._attach_default()
        summary = build_opportunities_summary_payload(self.store)
        for item in summary.get("items") or []:
            if item.get("opportunity_id") == self.opportunity.opportunity_id:
                self.assertNotIn("research_artifact_evidence", item)
                self.assertNotIn("options_flow_transparent_context", item)
                return
        self.fail("minted opportunity missing from summary")

    def test_evidence_payload_includes_transparent_context(self) -> None:
        self._attach_default()
        evidence = build_opportunity_evidence_payload(self.store, self.opportunity.opportunity_id)
        block = evidence.get("research_artifact_evidence") or {}
        self.assertEqual(block.get("readiness"), OPTIONS_FLOW_REPLAY_EVIDENCE_READY)
        attachments = block.get("attachments") or []
        self.assertEqual(len(attachments), 1)
        ctx = attachments[0].get("options_flow_transparent_context") or {}
        self.assertEqual(ctx.get("print_count"), 3)
        self.assertEqual(ctx.get("live_feed_claim"), "NOT_CLAIMED")
        self.assertEqual(ctx.get("authority_class"), AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION)
        self.assertNotIn("rank_score", evidence)
        self.assertNotIn("confirmation_score", evidence)

    def test_runtime_does_not_invoke_replay_pipeline(self) -> None:
        runtime = ResearchArtifactAttachmentRuntime(
            self.repo,
            get_opportunity=self.repo.get_opportunity,
        )
        with mock.patch(
            "market_platform_foundation.research.options_flow_replay.pipeline.run_options_flow_replay_pipeline",
        ) as mocked:
            runtime.attach(
                {
                    "attachment_id": "ofr-runtime",
                    "opportunity_id": self.opportunity.opportunity_id,
                    "artifact_type": ARTIFACT_TYPE,
                    "content_sha256": _GOLDEN_SHA,
                    "attached_at": "2026-09-14T22:35:00.000000Z",
                }
            )
            mocked.assert_not_called()

    def test_projection_matches_golden_fixture(self) -> None:
        from market_platform_foundation.canonical import load_json_strict

        artifact = load_json_strict(_FIXTURE)
        ctx = project_options_flow_transparent_context(artifact)
        self.assertEqual(ctx["dataset"]["admission_id"], "ADMITTED-OPTIONS-FLOW-REPLAY-NVDA-001")
        self.assertEqual(ctx["trade_class_counts"], {"block": 1, "sweep": 2})


if __name__ == "__main__":
    unittest.main()
