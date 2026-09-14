"""Lane G — agent enrichment ingest runtime (forbidden, idempotency, expiry, non-blocking)."""

from __future__ import annotations

import unittest
from pathlib import Path

from market_platform_foundation.intelligence.contracts.common import (
    IntelligenceScope,
    OpportunitySide,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.contracts.agent_ingest import (
    AgentBotRole,
    AgentClaimType,
    ForbiddenIngestMutation,
    IngestOperation,
)
from market_platform_foundation.intelligence.contracts.ingest_ui_timing import (
    evaluate_ui_intelligence_render_gate,
)
from market_platform_foundation.intelligence.ingest.runtime import (
    AgentEnrichmentIngestRuntime,
    IngestDisposition,
    enrichments_for_opportunity_detail,
    is_agent_enrichment_expired,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.ingest.boundary import (
    AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES,
    enforce_agent_enrichment_body_limit,
    resolve_agent_enrichment_persistence,
)

_IMP_SRC = Path(__file__).resolve().parents[2] / "src" / "market_platform_foundation"


SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(opportunity_id: str = "opp-lane-g") -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=SCOPE,
        created_at_ns=10_000,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        reason_summary="Lane G candidate",
    )


def _payload(
    *,
    record_id: str = "aer-lane-g-1",
    claim_type: str = "SUPPORTING_EVIDENCE",
    operation: str = "ATTACH_EVIDENCE",
    expires_at: str = "2099-01-01T00:00:00+00:00",
) -> dict:
    return {
        "record_id": record_id,
        "schema_version": "1",
        "opportunity_id": "opp-lane-g",
        "retrieved_at": "2026-09-14T14:00:00+00:00",
        "agent_id": "grok.sentinel.v1",
        "bot_role": "SENTINEL",
        "skill": {"skill_id": "imp.sentinel.verify", "version": "1.0.0"},
        "claim_type": claim_type,
        "confidence": 0.5,
        "expires_at": expires_at,
        "provenance": {"ingest_plane": "grok"},
        "operation": operation,
        "claim_body": {"summary": "supporting context"},
    }


class AgentEnrichmentIngestRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryIntelligenceRepository()
        self.repository.put_opportunity(_opportunity())
        self.runtime = AgentEnrichmentIngestRuntime(
            self.repository,
            get_opportunity=self.repository.get_opportunity,
        )

    def test_forbidden_mutation_matrix(self) -> None:
        for mutation in ForbiddenIngestMutation:
            with self.subTest(mutation=mutation.value):
                body = dict(_payload())
                body["requested_mutation"] = mutation.value
                with self.assertRaises(ValueError):
                    self.runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")

    def test_evidence_kind_operations(self) -> None:
        cases = (
            ("SUPPORTING_EVIDENCE", "ATTACH_EVIDENCE"),
            ("SOURCE_ATTRIBUTION", "ATTACH_SOURCE_CONTEXT"),
            ("CONTRADICTION", "ATTACH_CONTRADICTION"),
            ("CROWD_CONTEXT", "ATTACH_CROWD_CONTEXT"),
            ("HYPOTHESIS_SUGGESTION", "SUGGEST_HYPOTHESIS"),
        )
        for index, (claim_type, operation) in enumerate(cases):
            with self.subTest(claim_type=claim_type):
                body = _payload(
                    record_id=f"aer-kind-{index}",
                    claim_type=claim_type,
                    operation=operation,
                )
                result = self.runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
                self.assertEqual(result.disposition, IngestDisposition.INSERTED)

    def test_idempotency_and_update_own_record(self) -> None:
        body = _payload()
        first = self.runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        second = self.runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        self.assertEqual(first.disposition, IngestDisposition.INSERTED)
        self.assertEqual(second.disposition, IngestDisposition.ALREADY_PRESENT)
        updated = dict(body)
        updated["operation"] = "UPDATE_OWN_EVIDENCE_RECORD"
        updated["claim_body"] = {"summary": "revised"}
        third = self.runtime.ingest(updated, as_of_iso="2026-09-14T15:00:00+00:00")
        self.assertEqual(third.disposition, IngestDisposition.UPDATED)
        stored = self.runtime.retrieve("aer-lane-g-1")
        assert stored is not None
        self.assertEqual(stored.claim_body.get("summary"), "revised")

    def test_expiry_filters_active_rows(self) -> None:
        body = _payload(expires_at="2026-09-14T16:00:00+00:00")
        self.runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        record = self.runtime.retrieve("aer-lane-g-1")
        assert record is not None
        self.assertTrue(is_agent_enrichment_expired(record, as_of_iso="2026-09-14T17:00:00+00:00"))
        active = self.runtime.list_active_for_opportunity(
            "opp-lane-g",
            as_of_iso="2026-09-14T17:00:00+00:00",
        )
        self.assertEqual(active, ())

    def test_enrichment_does_not_mutate_opportunity_summary_source(self) -> None:
        before = self.repository.get_opportunity("opp-lane-g")
        assert before is not None
        self.runtime.ingest(_payload(), as_of_iso="2026-09-14T15:00:00+00:00")
        after = self.repository.get_opportunity("opp-lane-g")
        assert after is not None
        self.assertEqual(before, after)
        gate = evaluate_ui_intelligence_render_gate(
            deterministic_detection={"detection_id": "det-1"},
            wait_for_agent_enrichment=False,
            agent_enrichment_count=0,
            agent_enrichment_expected=True,
        )
        self.assertTrue(gate.allowed)

    def test_rejects_missing_opportunity(self) -> None:
        body = _payload()
        body["opportunity_id"] = "opp-missing"
        with self.assertRaises(ValueError) as ctx:
            self.runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        self.assertIn("AGENT_ENRICHMENT_OPPORTUNITY_NOT_FOUND", str(ctx.exception))

    def test_http_body_limit_fail_closed(self) -> None:
        over = AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES + 1
        with self.assertRaises(ValueError) as ctx:
            enforce_agent_enrichment_body_limit(over)
        self.assertIn("AGENT_ENRICHMENT_BODY_TOO_LARGE", str(ctx.exception))
        enforce_agent_enrichment_body_limit(AGENT_ENRICHMENT_INGEST_MAX_BODY_BYTES)

    def test_no_silent_sidecar_when_strategy_repository_unsupported(self) -> None:
        class _ForeignRepository:
            def get_opportunity(self, opportunity_id: str) -> None:
                return None

        with self.assertRaises(ValueError) as ctx:
            resolve_agent_enrichment_persistence(_ForeignRepository())
        self.assertIn("AGENT_ENRICHMENT_REPOSITORY_UNSUPPORTED", str(ctx.exception))

    def test_detail_overlay_attaches_without_touching_assembler(self) -> None:
        self.runtime.ingest(_payload(), as_of_iso="2026-09-14T15:00:00+00:00")
        overlay = enrichments_for_opportunity_detail(
            self.runtime,
            opportunity_id="opp-lane-g",
            as_of_iso="2026-09-14T15:00:00+00:00",
            base_lineage_refs=(),
            base_metadata={},
        )
        self.assertEqual(overlay["metadata"]["agent_enrichment"]["count"], 1)
        self.assertEqual(len(overlay["agent_enrichment_records"]), 1)

        ingest_source = (_IMP_SRC / "intelligence" / "opportunity" / "ingest.py").read_text(encoding="utf-8")
        ranking_source = (_IMP_SRC / "intelligence" / "opportunity" / "ranking.py").read_text(encoding="utf-8")
        projections_source = (_IMP_SRC / "ui_api" / "opportunity_projections.py").read_text(encoding="utf-8")
        self.assertNotIn("AgentEnrichmentIngestRuntime", ingest_source)
        self.assertNotIn("agent_enrichment", ranking_source)
        rank_block = projections_source.split("def build_ranked_rows", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("overlay_agent_enrichment", rank_block)
        detail_block = projections_source.split("def build_opportunity_detail_payload", 1)[1].split(
            "\ndef ",
            1,
        )[0]
        self.assertIn("overlay_agent_enrichment_on_detail", detail_block)


if __name__ == "__main__":
    unittest.main()
