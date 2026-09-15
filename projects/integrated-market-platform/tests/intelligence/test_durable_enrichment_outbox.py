"""Durable enrichment outbox: persistence, claim/retry, expiry, worker safety."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.contracts import ContractReference
from market_platform_foundation.intelligence.contracts.agent_ingest import AgentBotRole
from market_platform_foundation.intelligence.contracts.common import (
    IntelligenceScope,
    OpportunitySide,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.enrichment import (
    EnrichmentDeliveryState,
    EnrichmentOutboxWorker,
    EnrichmentRetryPolicy,
    InMemoryEnrichmentOutbox,
    RecordingEnrichmentDispatcher,
    SqliteEnrichmentOutbox,
    build_enrichment_request_for_opportunity,
    flush_outbox_to_dispatcher,
)
from market_platform_foundation.intelligence.enrichment.outbox import EnrichmentOutboxPutResult
from market_platform_foundation.local_state.connection import LocalStateConnection
from tests.intelligence.outcome_fixtures import T


SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(*, opportunity_id: str = "opp-durable", valid_until_ns: int = T + 10_000_000_000) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=SCOPE,
        created_at_ns=T,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        valid_until_ns=valid_until_ns,
        reason_summary="durable outbox",
    )


def _request(*, opportunity_id: str = "opp-durable", hard_expiry_ns: int | None = None):
    opportunity = _opportunity(opportunity_id=opportunity_id, valid_until_ns=hard_expiry_ns or T + 10_000_000_000)
    return build_enrichment_request_for_opportunity(
        opportunity=opportunity,
        assessment=None,
        detected_at_ns=T,
        requested_bot_role=AgentBotRole.SENTINEL,
        hard_expiry_ns=hard_expiry_ns or opportunity.valid_until_ns,
        known_evidence_refs=(ContractReference(kind="event", id="evt-1"),),
    )


class DurableEnrichmentOutboxBehaviorTests(unittest.TestCase):
    backend = "memory"

    def setUp(self) -> None:
        if self.backend == "memory":
            self.outbox = InMemoryEnrichmentOutbox()
            self._tmpdir = None
            self._connection = None
            return
        self._tmpdir = tempfile.TemporaryDirectory()
        self._connection = LocalStateConnection(Path(self._tmpdir.name) / "state.sqlite")
        self.outbox = SqliteEnrichmentOutbox(self._connection)

    def tearDown(self) -> None:
        if self._connection is not None:
            self._connection.close()
        if self._tmpdir is not None:
            self._tmpdir.cleanup()

    def test_append_idempotent(self) -> None:
        request = _request()
        first = self.outbox.append(request)
        second = self.outbox.append(request)
        self.assertEqual(first, EnrichmentOutboxPutResult.INSERTED)
        self.assertEqual(second, EnrichmentOutboxPutResult.ALREADY_PRESENT)
        self.assertEqual(len(self.outbox.list_pending()), 1)

    def test_restart_persistence(self) -> None:
        if self.backend != "sqlite":
            self.skipTest("sqlite-only")
        request = _request(opportunity_id="opp-restart")
        self.outbox.append(request)
        path = self._connection.path
        self._connection.close()
        self._connection = LocalStateConnection(path)
        outbox = SqliteEnrichmentOutbox(self._connection)
        self.assertIsNotNone(outbox.get(request.request_id))
        delivery = outbox.get_delivery(request.request_id)
        assert delivery is not None
        self.assertEqual(delivery.delivery_state, EnrichmentDeliveryState.PENDING)

    def test_worker_claim_and_dispatch(self) -> None:
        request = _request()
        self.outbox.append(request)
        dispatcher = RecordingEnrichmentDispatcher()
        worker = EnrichmentOutboxWorker(self.outbox, dispatcher, worker_id="w1")
        self.assertTrue(worker.run_once(now_ns=T))
        self.assertEqual(len(dispatcher.dispatched), 1)
        delivery = self.outbox.get_delivery(request.request_id)
        assert delivery is not None
        self.assertEqual(delivery.delivery_state, EnrichmentDeliveryState.DISPATCHED)

    def test_claim_collision_only_one_worker_wins(self) -> None:
        request = _request(opportunity_id="opp-claim")
        self.outbox.append(request)
        barrier = threading.Barrier(2)
        results: list[str | None] = []

        def _claim(worker_id: str) -> None:
            barrier.wait(timeout=2)
            claimed = self.outbox.claim_next(
                worker_id,
                now_ns=T,
                lease_duration_ns=60_000_000_000,
            )
            results.append(claimed.request_id if claimed is not None else None)

        threads = [
            threading.Thread(target=_claim, args=("w-a",)),
            threading.Thread(target=_claim, args=("w-b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        winners = [row for row in results if row == request.request_id]
        self.assertEqual(len(winners), 1)

    def test_expired_before_dispatch(self) -> None:
        request = _request(hard_expiry_ns=T - 1)
        self.outbox.append(request)
        expired = self.outbox.sweep_expired(T)
        self.assertEqual(expired, 1)
        delivery = self.outbox.get_delivery(request.request_id)
        assert delivery is not None
        self.assertEqual(delivery.delivery_state, EnrichmentDeliveryState.EXPIRED)
        self.assertIsNone(self.outbox.claim_next("w1", now_ns=T, lease_duration_ns=1_000))

    def test_lease_expiry_reclaims_claim(self) -> None:
        request = _request(opportunity_id="opp-lease")
        self.outbox.append(request)
        claimed = self.outbox.claim_next("w1", now_ns=T, lease_duration_ns=1_000)
        self.assertIsNotNone(claimed)
        released = self.outbox.release_expired_claims(T + 2_000)
        self.assertEqual(released, 1)
        delivery = self.outbox.get_delivery(request.request_id)
        assert delivery is not None
        self.assertEqual(delivery.delivery_state, EnrichmentDeliveryState.PENDING)

    def test_dispatch_failure_retries_then_dead_letters(self) -> None:
        request = _request(opportunity_id="opp-dead")
        self.outbox.append(request)
        policy = EnrichmentRetryPolicy(max_attempts=1, base_backoff_ns=0, max_backoff_ns=0)

        class _FailDispatcher(RecordingEnrichmentDispatcher):
            def dispatch(self, req) -> None:
                raise RuntimeError("dispatch failed")

        worker = EnrichmentOutboxWorker(self.outbox, _FailDispatcher(), policy=policy)
        worker.run_once(now_ns=T)
        delivery = self.outbox.get_delivery(request.request_id)
        assert delivery is not None
        self.assertEqual(delivery.delivery_state, EnrichmentDeliveryState.DEAD_LETTER)

    def test_acknowledged_is_terminal(self) -> None:
        request = _request(opportunity_id="opp-ack")
        self.outbox.append(request)
        self.outbox.mark_acknowledged(request.request_id, at_ns=T)
        self.assertEqual(self.outbox.list_for_opportunity(request.opportunity_id), ())


class MemoryDurableEnrichmentOutboxTests(DurableEnrichmentOutboxBehaviorTests):
    backend = "memory"


class SqliteDurableEnrichmentOutboxTests(DurableEnrichmentOutboxBehaviorTests):
    backend = "sqlite"


class DurableEnrichmentHotPathTests(unittest.TestCase):
    def test_flush_uses_worker_without_blocking_surface(self) -> None:
        outbox = InMemoryEnrichmentOutbox()
        request = _request()
        outbox.append(request)
        dispatcher = RecordingEnrichmentDispatcher()
        count = flush_outbox_to_dispatcher(outbox, dispatcher, now_ns=T)
        self.assertEqual(count, 1)
        self.assertEqual(len(dispatcher.dispatched), 1)


if __name__ == "__main__":
    unittest.main()
