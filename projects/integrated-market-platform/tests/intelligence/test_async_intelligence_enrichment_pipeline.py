"""Lane B — async intelligence enrichment dispatch + read model."""

from __future__ import annotations

import time
import unittest

from market_platform_foundation.intelligence.contracts import ContractReference
from market_platform_foundation.intelligence.contracts.agent_ingest import ForbiddenIngestMutation
from market_platform_foundation.intelligence.contracts.common import (
    IntelligenceScope,
    OpportunitySide,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.contracts.ingest_ui_timing import (
    IntelligenceSurfacePhase,
    evaluate_ui_intelligence_render_gate,
)
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.contracts.strategy_match import (
    StrategyMatch,
    StrategyMatchDisposition,
)
from market_platform_foundation.intelligence.enrichment import (
    InMemoryEnrichmentOutbox,
    RecordingEnrichmentDispatcher,
    async_enrichment_fields_for_detail,
    flush_outbox_to_dispatcher,
    overlay_async_enrichment_on_detail,
)
from market_platform_foundation.intelligence.enrichment.outbox import EnrichmentOutboxPutResult
from market_platform_foundation.intelligence.ingest.runtime import (
    AgentEnrichmentIngestRuntime,
    IngestDisposition,
    enrichments_for_opportunity_detail,
)
from market_platform_foundation.intelligence.opportunity import bridge_strategy_match_to_opportunity
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.quality.models import AvailabilityState
from tests.intelligence.opportunity_fixtures import (
    champion_forecast,
    default_opportunity_context,
    default_opportunity_policy,
)
from tests.intelligence.test_universal_opportunity import UniversalEconomicAssessmentTests
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import bootstrap_control_champion, validated_candidate_bundle


SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _payload(
    *,
    record_id: str = "aer-async-1",
    expires_at: str = "2099-01-01T00:00:00+00:00",
    opportunity_id: str = "opp-async",
) -> dict:
    return {
        "record_id": record_id,
        "schema_version": "1",
        "opportunity_id": opportunity_id,
        "retrieved_at": "2026-09-14T14:00:00+00:00",
        "agent_id": "grok.sentinel.v1",
        "bot_role": "SENTINEL",
        "skill": {"skill_id": "imp.sentinel.verify", "version": "1.0.0"},
        "claim_type": "SUPPORTING_EVIDENCE",
        "confidence": 0.5,
        "expires_at": expires_at,
        "provenance": {"ingest_plane": "grok"},
        "operation": "ATTACH_EVIDENCE",
        "claim_body": {"summary": "async context"},
    }


class AsyncIntelligenceEnrichmentPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryIntelligenceRepository()
        self.outbox = InMemoryEnrichmentOutbox()
        promotion = __import__(
            "market_platform_foundation.intelligence.promotion",
            fromlist=["PromotionEngine"],
        ).PromotionEngine()
        _repo, _manifest, candidate, _bytes, _report, _plan = validated_candidate_bundle()
        self.champion = bootstrap_control_champion(promotion, candidate, effective_from_ns=T)
        self.forecast = champion_forecast(self.champion)
        self.policy = default_opportunity_policy()
        self.context = default_opportunity_context(decision_time_ns=T + 1_000_000_000)
        self.sidecar = UniversalEconomicAssessmentTests()._assessment()
        self.match = StrategyMatch.create(
            strategy_id="strategy-async",
            strategy_identity_hash="strategy-hash",
            scope=self.forecast.scope,
            decision_time_ns=T,
            disposition=StrategyMatchDisposition.MATCHED,
            capability_state=AvailabilityState.AVAILABLE,
            quality=self.forecast.quality,
            source_forecast_refs=(
                ContractReference(kind="forecast", id=self.forecast.forecast_id),
            ),
            context={"account_id": "paper-account", "mode": "ACTUAL_LIVE"},
        )

    def _bridge(self):
        return bridge_strategy_match_to_opportunity(
            match=self.match,
            forecast=self.forecast,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            policy=self.policy,
            context=self.context,
            opportunity_decision_time_ns=T + 1_000_000_000,
            economic_assessment=self.sidecar,
            repository=self.repository,
            enrichment_outbox=self.outbox,
        )

    def test_deterministic_opportunity_surfaces_without_agent(self) -> None:
        result = self._bridge()
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.EMIT)
        assert result.opportunity is not None
        gate = evaluate_ui_intelligence_render_gate(
            deterministic_detection={"opportunity_id": result.opportunity.opportunity_id},
            wait_for_agent_enrichment=False,
            agent_enrichment_count=0,
            agent_enrichment_expected=True,
        )
        self.assertTrue(gate.allowed)
        self.assertEqual(gate.phase, IntelligenceSurfacePhase.AGENT_ENRICHMENT_PENDING)

    def test_slow_dispatcher_does_not_delay_opportunity_surface(self) -> None:
        before = time.perf_counter()
        result = self._bridge()
        elapsed_surface = time.perf_counter() - before
        self.assertIsNotNone(result.opportunity)

        class _SlowDispatcher(RecordingEnrichmentDispatcher):
            def dispatch(self, request) -> None:
                time.sleep(0.05)
                super().dispatch(request)

        dispatcher = _SlowDispatcher()
        started = time.perf_counter()
        flush_outbox_to_dispatcher(self.outbox, dispatcher)
        elapsed_dispatch = time.perf_counter() - started
        self.assertGreater(elapsed_dispatch, 0.04)
        self.assertLess(elapsed_surface, 0.02)
        self.assertEqual(len(dispatcher.dispatched), 1)

    def test_request_generated_on_emit(self) -> None:
        result = self._bridge()
        pending = self.outbox.list_pending()
        self.assertEqual(len(pending), 1)
        assert result.opportunity is not None
        self.assertEqual(pending[0].opportunity_id, result.opportunity.opportunity_id)

    def test_ingest_updates_same_opportunity_detail(self) -> None:
        result = self._bridge()
        assert result.opportunity is not None
        opportunity = result.opportunity
        runtime = AgentEnrichmentIngestRuntime(
            self.repository,
            get_opportunity=self.repository.get_opportunity,
        )
        body = _payload(opportunity_id=opportunity.opportunity_id)
        result = runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        self.assertEqual(result.disposition, IngestDisposition.INSERTED)
        self.assertEqual(result.opportunity_id, opportunity.opportunity_id)
        overlay = enrichments_for_opportunity_detail(
            runtime,
            opportunity_id=opportunity.opportunity_id,
            as_of_iso="2026-09-14T15:00:00+00:00",
            base_lineage_refs=(),
            base_metadata={},
        )
        self.assertEqual(overlay["metadata"]["agent_enrichment"]["count"], 1)
        stored = self.repository.get_opportunity(opportunity.opportunity_id)
        assert stored is not None
        self.assertEqual(stored.opportunity_id, opportunity.opportunity_id)

    def test_idempotent_duplicate_callbacks(self) -> None:
        result = self._bridge()
        assert result.opportunity is not None
        opportunity = result.opportunity
        runtime = AgentEnrichmentIngestRuntime(
            self.repository,
            get_opportunity=self.repository.get_opportunity,
        )
        body = _payload(opportunity_id=opportunity.opportunity_id)
        first = runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        second = runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        self.assertEqual(first.disposition, IngestDisposition.INSERTED)
        self.assertEqual(second.disposition, IngestDisposition.ALREADY_PRESENT)
        rows = self.repository.list_agent_enrichment_by_opportunity(opportunity.opportunity_id)
        self.assertEqual(len(rows), 1)

    def test_outbox_idempotency(self) -> None:
        self._bridge()
        first = self.outbox.list_pending()
        second_bridge = bridge_strategy_match_to_opportunity(
            match=self.match,
            forecast=self.forecast,
            champion_at_forecast=self.champion,
            champion_at_opportunity=self.champion,
            policy=self.policy,
            context=self.context,
            opportunity_decision_time_ns=T + 1_000_000_000,
            economic_assessment=self.sidecar,
            repository=self.repository,
            enrichment_outbox=self.outbox,
        )
        self.assertIsNotNone(second_bridge.opportunity)
        pending = self.outbox.list_pending()
        self.assertEqual(len(pending), len(first))
        duplicate = self.outbox.append(pending[0])
        self.assertEqual(duplicate, EnrichmentOutboxPutResult.ALREADY_PRESENT)

    def test_late_result_after_hard_expiry_not_active(self) -> None:
        opportunity = OpportunityV1(
            opportunity_id="opp-late",
            schema_version="1",
            scope=SCOPE,
            created_at_ns=10_000,
            quality=QUALITY,
            side=OpportunitySide.LONG,
            valid_until_ns=1_000_000_000,
            reason_summary="late path",
        )
        self.repository.put_opportunity(opportunity)
        runtime = AgentEnrichmentIngestRuntime(
            self.repository,
            get_opportunity=self.repository.get_opportunity,
        )
        body = _payload(
            record_id="aer-late",
            opportunity_id="opp-late",
            expires_at="2026-09-14T12:00:00+00:00",
        )
        result = runtime.ingest(body, as_of_iso="2026-09-14T18:00:00+00:00")
        self.assertEqual(result.disposition, IngestDisposition.RESEARCH_ONLY_LATE_RESULT)
        active = runtime.list_active_for_opportunity("opp-late", as_of_iso="2026-09-14T18:00:00+00:00")
        self.assertEqual(active, ())
        stored = runtime.retrieve("aer-late")
        assert stored is not None
        self.assertEqual(stored.metadata.get("ingest_disposition"), "RESEARCH_ONLY_LATE_RESULT")

    def test_forbidden_mutations_still_fail_closed(self) -> None:
        result = self._bridge()
        assert result.opportunity is not None
        opportunity = result.opportunity
        runtime = AgentEnrichmentIngestRuntime(
            self.repository,
            get_opportunity=self.repository.get_opportunity,
        )
        for mutation in ForbiddenIngestMutation:
            body = _payload(opportunity_id=opportunity.opportunity_id)
            body["requested_mutation"] = mutation.value
            with self.subTest(mutation=mutation.value):
                with self.assertRaises(ValueError):
                    runtime.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")

    def test_read_model_additive_fields(self) -> None:
        result = self._bridge()
        assert result.opportunity is not None
        opportunity = result.opportunity
        runtime = AgentEnrichmentIngestRuntime(
            self.repository,
            get_opportunity=self.repository.get_opportunity,
        )
        detail = {
            "opportunity_id": opportunity.opportunity_id,
            "summary_id": opportunity.opportunity_id,
        }
        enriched = overlay_async_enrichment_on_detail(
            detail,
            outbox=self.outbox,
            runtime=runtime,
            as_of_iso="2026-09-14T15:00:00+00:00",
        )
        self.assertIn("async_enrichment", enriched)
        self.assertEqual(enriched["async_enrichment"]["pending_request_count"], 1)
        fields = async_enrichment_fields_for_detail(
            opportunity_id=opportunity.opportunity_id,
            deterministic_detection={"opportunity_id": opportunity.opportunity_id},
            outbox=self.outbox,
            runtime=runtime,
            as_of_iso="2026-09-14T15:00:00+00:00",
        )
        self.assertEqual(fields["async_enrichment"]["phase"], "AGENT_ENRICHMENT_PENDING")


if __name__ == "__main__":
    unittest.main()
