"""Contract tests for Grok/agent intelligence ingest boundary (Lane I)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.agent_ingest import (  # noqa: E402
    AgentBotCapability,
    AgentBotRole,
    AgentClaimType,
    AgentEnrichmentEvidenceV1,
    AgentSkillRef,
    ForbiddenIngestMutation,
    IngestOperation,
    agent_enrichment_evidence_v1_from_dict,
    agent_enrichment_evidence_v1_to_dict,
    bot_role_allows_capability,
    reject_forbidden_ingest_mutation,
    validate_ingest_operation_allowed,
)
from market_platform_foundation.intelligence.contracts.common import SourceReference  # noqa: E402
from market_platform_foundation.intelligence.contracts.ingest_ui_timing import (  # noqa: E402
    IntelligenceSurfacePhase,
    evaluate_ui_intelligence_render_gate,
)
from market_platform_foundation.intelligence.ingest.runtime import (  # noqa: E402
    AgentEnrichmentIngestRuntime,
)
from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
)


class GrokIntelligenceIngestContractTests(unittest.TestCase):
    def test_agent_enrichment_round_trip(self) -> None:
        record = AgentEnrichmentEvidenceV1(
            record_id="aer-001",
            schema_version="1",
            opportunity_id="opp-abc",
            event_id="evt-9",
            retrieved_at="2026-09-14T14:00:00-04:00",
            agent_id="grok.sentinel.v1",
            bot_role=AgentBotRole.SENTINEL,
            skill=AgentSkillRef(skill_id="imp.sentinel.verify", version="1.0.0"),
            claim_type=AgentClaimType.VERIFICATION,
            confidence=0.72,
            expires_at="2026-09-14T18:00:00-04:00",
            provenance={"ingest_plane": "grok", "session_ref": "sess-local"},
            operation=IngestOperation.ATTACH_EVIDENCE,
            source_refs=(
                SourceReference(
                    provider_id="finviz.news",
                    source_type="news_article",
                    source_record_id="src-1",
                ),
            ),
            claim_body={"summary": "Source corroborates headline catalyst"},
        )
        payload = agent_enrichment_evidence_v1_to_dict(record)
        restored = agent_enrichment_evidence_v1_from_dict(payload)
        self.assertEqual(restored.opportunity_id, "opp-abc")
        self.assertEqual(restored.event_id, "evt-9")
        self.assertEqual(restored.bot_role, AgentBotRole.SENTINEL)
        self.assertEqual(restored.skill.version, "1.0.0")

    def test_allowed_ingest_operations(self) -> None:
        self.assertEqual(
            validate_ingest_operation_allowed(IngestOperation.SUGGEST_HYPOTHESIS),
            IngestOperation.SUGGEST_HYPOTHESIS,
        )
        with self.assertRaises(ValueError):
            validate_ingest_operation_allowed("PAPER_SUBMIT")

    def test_forbidden_mutations_fail_closed(self) -> None:
        """Every ForbiddenIngestMutation value matches GROK_INTELLIGENCE_INGEST_API.md."""
        doc_paper_live = frozenset(
            {
                ForbiddenIngestMutation.PAPER_SUBMIT,
                ForbiddenIngestMutation.PAPER_CANCEL,
                ForbiddenIngestMutation.PAPER_REPLACE,
                ForbiddenIngestMutation.LIVE_SUBMIT,
                ForbiddenIngestMutation.LIVE_CANCEL,
                ForbiddenIngestMutation.LIVE_REPLACE,
            }
        )
        self.assertTrue(doc_paper_live.issubset(frozenset(ForbiddenIngestMutation)))
        for mutation in ForbiddenIngestMutation:
            with self.subTest(mutation=mutation.value):
                with self.assertRaises(ValueError):
                    reject_forbidden_ingest_mutation(mutation)
                with self.assertRaises(ValueError):
                    reject_forbidden_ingest_mutation(mutation.value)

    def test_bot_capability_matrix(self) -> None:
        self.assertTrue(
            bot_role_allows_capability(AgentBotRole.SENTINEL, AgentBotCapability.DETECT)
        )
        self.assertFalse(
            bot_role_allows_capability(AgentBotRole.CROWD_WATCH, AgentBotCapability.ORCHESTRATE)
        )

    def test_ui_renders_on_detection_without_agent(self) -> None:
        gate = evaluate_ui_intelligence_render_gate(
            deterministic_detection={"detection_id": "det-1"},
            wait_for_agent_enrichment=False,
            agent_enrichment_count=0,
            agent_enrichment_expected=True,
        )
        self.assertTrue(gate.allowed)
        self.assertEqual(gate.phase, IntelligenceSurfacePhase.AGENT_ENRICHMENT_PENDING)
        self.assertEqual(gate.reason_code, "DETECTION_READY")

    def test_ui_never_waits_for_grok(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            evaluate_ui_intelligence_render_gate(
                deterministic_detection={"detection_id": "det-1"},
                wait_for_agent_enrichment=True,
            )
        self.assertIn("UI_BLOCKED_ON_AGENT_ENRICHMENT", str(ctx.exception))

    def test_ui_missing_detection_not_ready(self) -> None:
        gate = evaluate_ui_intelligence_render_gate(
            deterministic_detection=None,
            wait_for_agent_enrichment=False,
        )
        self.assertFalse(gate.allowed)
        self.assertEqual(gate.reason_code, "DETERMINISTIC_DETECTION_MISSING")

    def test_runtime_rejects_paper_submit_mutation_hint(self) -> None:
        runtime = AgentEnrichmentIngestRuntime(InMemoryIntelligenceRepository())
        payload = agent_enrichment_evidence_v1_to_dict(
            AgentEnrichmentEvidenceV1(
                record_id="aer-forbidden",
                schema_version="1",
                opportunity_id="opp-x",
                retrieved_at="2026-09-14T14:00:00-04:00",
                agent_id="grok.sentinel.v1",
                bot_role=AgentBotRole.SENTINEL,
                skill=AgentSkillRef(skill_id="imp.sentinel.verify", version="1.0.0"),
                claim_type=AgentClaimType.VERIFICATION,
                confidence=0.5,
                expires_at="2099-01-01T00:00:00+00:00",
                provenance={"ingest_plane": "grok"},
                operation=IngestOperation.ATTACH_EVIDENCE,
            )
        )
        payload["requested_mutation"] = ForbiddenIngestMutation.PAPER_SUBMIT.value
        with self.assertRaises(ValueError):
            runtime.ingest(payload, as_of_iso="2026-09-14T15:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
