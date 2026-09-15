"""Phase 5 Lane A — production durable enrichment worker wiring."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from market_platform_foundation.intelligence.contracts.common import (
    IntelligenceScope,
    OpportunitySide,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.enrichment import (
    AgentEnrichmentIngestCoordinator,
    EnrichmentDeliveryState,
    EnrichmentOutboxAckDisposition,
    EnrichmentOutboxWorker,
    EnrichmentRetryPolicy,
    InMemoryEnrichmentOutbox,
    RecordingEnrichmentDispatcher,
    SqliteEnrichmentOutbox,
    build_enrichment_request_for_opportunity,
    enrichment_worker_enabled,
    maybe_acknowledge_enrichment_outbox,
    open_sqlite_enrichment_outbox,
    resolve_enrichment_dispatcher,
)
from market_platform_foundation.intelligence.contracts.agent_ingest import AgentBotRole
from market_platform_foundation.intelligence.ingest.runtime import (
    AgentEnrichmentIngestResult,
    AgentEnrichmentIngestRuntime,
    IngestDisposition,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.startup import open_enrichment_outbox, reset_local_state_for_tests
from tests.intelligence.outcome_fixtures import T


SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(opportunity_id: str = "opp-prod", valid_until_ns: int = T + 10_000_000_000) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=SCOPE,
        created_at_ns=T,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        valid_until_ns=valid_until_ns,
        reason_summary="production wiring",
    )


def _ingest_payload(opportunity_id: str) -> dict:
    return {
        "record_id": "aer-prod-1",
        "schema_version": "1",
        "opportunity_id": opportunity_id,
        "retrieved_at": "2026-09-14T14:00:00+00:00",
        "agent_id": "grok.sentinel.v1",
        "bot_role": "SENTINEL",
        "skill": {"skill_id": "imp.sentinel.verify", "version": "1.0.0"},
        "claim_type": "SUPPORTING_EVIDENCE",
        "confidence": 0.5,
        "expires_at": "2099-01-01T00:00:00+00:00",
        "provenance": {"ingest_plane": "grok"},
        "operation": "ATTACH_EVIDENCE",
        "claim_body": {"summary": "async context"},
    }


class ProductionEnrichmentWorkerWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._state_dir = Path(self._tmpdir.name)
        self._env = mock.patch.dict(
            os.environ,
            {
                "IMP_STATE_DIR": str(self._state_dir),
                "IMP_INTELLIGENCE_ENRICHMENT_WORKER": "",
            },
            clear=False,
        )
        self._env.start()
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        reset_local_state_for_tests()
        self._env.stop()
        self._tmpdir.cleanup()

    def _sqlite_outbox(self) -> SqliteEnrichmentOutbox:
        outbox = open_enrichment_outbox(force=True)
        assert outbox is not None
        return outbox

    def test_worker_gate_defaults_off(self) -> None:
        self.assertFalse(enrichment_worker_enabled())

    def test_open_enrichment_outbox_uses_local_state(self) -> None:
        outbox = open_enrichment_outbox(force=True)
        assert outbox is not None
        also = open_enrichment_outbox()
        assert also is not None
        self.assertIs(outbox, also)

    def test_restart_persistence_sqlite(self) -> None:
        outbox = self._sqlite_outbox()
        request = build_enrichment_request_for_opportunity(
            opportunity=_opportunity("opp-restart-prod"),
            assessment=None,
            detected_at_ns=T,
            requested_bot_role=AgentBotRole.SENTINEL,
        )
        outbox.append(request)
        path = outbox._connection.path
        reset_local_state_for_tests()
        reopened = SqliteEnrichmentOutbox(LocalStateConnection(path))
        self.assertIsNotNone(reopened.get(request.request_id))
        reopened._connection.close()

    def test_ingest_success_acknowledges_dispatched_request(self) -> None:
        outbox = InMemoryEnrichmentOutbox()
        opportunity = _opportunity("opp-ack-prod")
        request = build_enrichment_request_for_opportunity(
            opportunity=opportunity,
            assessment=None,
            detected_at_ns=T,
        )
        outbox.append(request)
        outbox.mark_dispatched(request.request_id, at_ns=T)
        repository = InMemoryIntelligenceRepository()
        repository.put_opportunity(opportunity)
        runtime = AgentEnrichmentIngestRuntime(repository, get_opportunity=repository.get_opportunity)
        coordinator = AgentEnrichmentIngestCoordinator(runtime, outbox=outbox)
        result = coordinator.ingest(_ingest_payload(opportunity.opportunity_id), as_of_iso="2026-09-14T15:00:00+00:00")
        self.assertEqual(result.disposition, IngestDisposition.INSERTED)
        delivery = outbox.get_delivery(request.request_id)
        assert delivery is not None
        self.assertEqual(delivery.delivery_state, EnrichmentDeliveryState.ACKNOWLEDGED)

    def test_duplicate_callback_idempotent_ack(self) -> None:
        outbox = InMemoryEnrichmentOutbox()
        opportunity = _opportunity("opp-dup-ack")
        request = build_enrichment_request_for_opportunity(
            opportunity=opportunity,
            assessment=None,
            detected_at_ns=T,
        )
        outbox.append(request)
        outbox.mark_dispatched(request.request_id, at_ns=T)
        repository = InMemoryIntelligenceRepository()
        repository.put_opportunity(opportunity)
        runtime = AgentEnrichmentIngestRuntime(repository, get_opportunity=repository.get_opportunity)
        coordinator = AgentEnrichmentIngestCoordinator(runtime, outbox=outbox)
        body = _ingest_payload(opportunity.opportunity_id)
        coordinator.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        second = coordinator.ingest(body, as_of_iso="2026-09-14T15:00:00+00:00")
        self.assertEqual(second.disposition, IngestDisposition.ALREADY_PRESENT)
        ack = maybe_acknowledge_enrichment_outbox(
            outbox,
            ingest_result=second,
            payload=body,
        )
        self.assertEqual(ack.disposition, EnrichmentOutboxAckDisposition.ALREADY_ACKNOWLEDGED)

    def test_unknown_request_does_not_ack(self) -> None:
        outbox = InMemoryEnrichmentOutbox()
        ack = maybe_acknowledge_enrichment_outbox(
            outbox,
            ingest_result=AgentEnrichmentIngestResult(
                disposition=IngestDisposition.INSERTED,
                record_id="aer-prod-1",
                opportunity_id="missing",
            ),
            payload=_ingest_payload("missing"),
        )
        self.assertEqual(ack.disposition, EnrichmentOutboxAckDisposition.REQUEST_UNKNOWN)

    def test_malformed_ingest_does_not_ack(self) -> None:
        outbox = InMemoryEnrichmentOutbox()
        opportunity = _opportunity("opp-bad")
        request = build_enrichment_request_for_opportunity(
            opportunity=opportunity,
            assessment=None,
            detected_at_ns=T,
        )
        outbox.append(request)
        outbox.mark_dispatched(request.request_id, at_ns=T)
        repository = InMemoryIntelligenceRepository()
        repository.put_opportunity(opportunity)
        runtime = AgentEnrichmentIngestRuntime(repository, get_opportunity=repository.get_opportunity)
        coordinator = AgentEnrichmentIngestCoordinator(runtime, outbox=outbox)
        with self.assertRaises(Exception):
            coordinator.ingest({"opportunity_id": opportunity.opportunity_id}, as_of_iso="2026-09-14T15:00:00+00:00")
        delivery = outbox.get_delivery(request.request_id)
        assert delivery is not None
        self.assertEqual(delivery.delivery_state, EnrichmentDeliveryState.DISPATCHED)

    def test_callback_after_expiry_not_acknowledged(self) -> None:
        outbox = InMemoryEnrichmentOutbox()
        opportunity = _opportunity("opp-expired", valid_until_ns=T - 1)
        request = build_enrichment_request_for_opportunity(
            opportunity=opportunity,
            assessment=None,
            detected_at_ns=T,
            hard_expiry_ns=T - 1,
        )
        outbox.append(request)
        outbox.mark_dispatched(request.request_id, at_ns=T)
        outbox.sweep_expired(T)
        ack = maybe_acknowledge_enrichment_outbox(
            outbox,
            ingest_result=AgentEnrichmentIngestResult(
                disposition=IngestDisposition.INSERTED,
                record_id="aer-prod-1",
                opportunity_id=opportunity.opportunity_id,
            ),
            payload=_ingest_payload(opportunity.opportunity_id),
        )
        self.assertEqual(ack.disposition, EnrichmentOutboxAckDisposition.REQUEST_NOT_ACK_ELIGIBLE)

    def test_dispatcher_timeout_records_failure(self) -> None:
        outbox = InMemoryEnrichmentOutbox()
        request = build_enrichment_request_for_opportunity(
            opportunity=_opportunity("opp-timeout"),
            assessment=None,
            detected_at_ns=T,
        )
        outbox.append(request)

        class _SlowDispatcher(RecordingEnrichmentDispatcher):
            def dispatch(self, req) -> None:
                time.sleep(0.05)

        policy = EnrichmentRetryPolicy(max_attempts=1, dispatch_timeout_sec=0.01)
        worker = EnrichmentOutboxWorker(outbox, _SlowDispatcher(), policy=policy)
        worker.run_once(now_ns=T)
        delivery = outbox.get_delivery(request.request_id)
        assert delivery is not None
        self.assertEqual(delivery.delivery_state, EnrichmentDeliveryState.DEAD_LETTER)

    def test_default_dispatcher_is_noop(self) -> None:
        dispatcher = resolve_enrichment_dispatcher()
        self.assertEqual(dispatcher.__class__.__name__, "NoOpEnrichmentDispatcher")

    def test_hot_path_latency_independent_of_dispatcher(self) -> None:
        outbox = InMemoryEnrichmentOutbox()
        request = build_enrichment_request_for_opportunity(
            opportunity=_opportunity("opp-hot"),
            assessment=None,
            detected_at_ns=T,
        )
        started = time.perf_counter()
        outbox.append(request)
        elapsed_enqueue = time.perf_counter() - started

        class _SlowDispatcher(RecordingEnrichmentDispatcher):
            def dispatch(self, req) -> None:
                time.sleep(0.05)
                super().dispatch(req)

        worker = EnrichmentOutboxWorker(outbox, _SlowDispatcher())
        started = time.perf_counter()
        worker.run_once(now_ns=T)
        elapsed_dispatch = time.perf_counter() - started
        self.assertLess(elapsed_enqueue, 0.02)
        self.assertGreater(elapsed_dispatch, 0.04)


if __name__ == "__main__":
    unittest.main()
