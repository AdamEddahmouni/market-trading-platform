"""Observation ingress router — idempotent multi-consumer dispatch."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
)
from market_platform_foundation.intelligence.normalization.providers.moomoo import (  # noqa: E402
    normalize_moomoo_capture,
)
from market_platform_foundation.intelligence.observation_ingress import (  # noqa: E402
    IngressConsumerKind,
    IngressConsumerStatus,
    IngressDispatchContext,
    IngressDispatchError,
    ObservationIngressRouter,
    audit_sink_consumer,
    detector_stub_consumer,
    dispatch_normalization_result,
    enrichment_trigger_consumer,
    oe_evidence_consumer,
    store_consumer,
)
from market_platform_foundation.intelligence.persistence.memory import (  # noqa: E402
    InMemoryIntelligenceRepository,
)

T0 = 1_000_000_000_000
FIVE_SEC = 5 * 1_000_000_000


def _moomoo_quote_fixture() -> dict:
    return {
        "provider": "moomoo.opend.observational",
        "capability": "QUOTE",
        "provider_symbol": "US.NVDA",
        "sequence": 42,
        "clocks": {
            "event_time_ns": T0,
            "provider_time_ns": T0 + 5_000_000,
            "received_time_ns": T0 + FIVE_SEC,
        },
        "raw_payload": {
            "bid_price": 100.0,
            "ask_price": 100.05,
            "bid_vol": 500,
            "ask_vol": 400,
        },
    }


class ObservationIngressRouterTests(unittest.TestCase):
    def test_moomoo_normalization_dispatches_to_store_and_audit(self) -> None:
        repo = InMemoryIntelligenceRepository()
        audit: list = []
        evidence: list[dict[str, str]] = []
        seen: set[str] = set()
        router = ObservationIngressRouter(
            [
                store_consumer(repo),
                audit_sink_consumer(audit),
                oe_evidence_consumer(evidence),
                detector_stub_consumer(seen),
                enrichment_trigger_consumer(),
            ]
        )
        ctx = NormalizationContext(
            received_time_ns=T0 + FIVE_SEC,
            ingestion_mode=IngestionMode.LIVE_OBSERVED,
        )
        normalized = normalize_moomoo_capture(_moomoo_quote_fixture(), context=ctx)
        receipt = dispatch_normalization_result(
            router,
            normalized,
            context=IngressDispatchContext(
                dispatch_time_ns=T0 + FIVE_SEC,
                ingestion_mode=IngestionMode.LIVE_OBSERVED,
                source_label="moomoo.capture",
            ),
        )
        assert receipt is not None
        self.assertFalse(receipt.duplicate)
        self.assertTrue(receipt.dispatch_id.startswith("ING-"))
        event = normalized.event
        assert event is not None
        self.assertIsNotNone(repo.get_event(event.event_id))
        self.assertEqual(len(audit), 1)
        self.assertEqual(evidence[0]["event_id"], event.event_id)
        self.assertIn(event.event_id, seen)
        self.assertEqual(len(router.enrichment_triggers), 1)
        self.assertEqual(router.metrics()["dispatched"], 1)

    def test_duplicate_dispatch_is_idempotent(self) -> None:
        repo = InMemoryIntelligenceRepository()
        router = ObservationIngressRouter([store_consumer(repo)])
        ctx = NormalizationContext(
            received_time_ns=T0 + FIVE_SEC,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        normalized = normalize_moomoo_capture(_moomoo_quote_fixture(), context=ctx)
        dispatch_ctx = IngressDispatchContext(dispatch_time_ns=T0 + FIVE_SEC)
        first = dispatch_normalization_result(router, normalized, context=dispatch_ctx)
        second = dispatch_normalization_result(router, normalized, context=dispatch_ctx)
        assert first is not None and second is not None
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        self.assertEqual(first.dispatch_id, second.dispatch_id)
        self.assertEqual(router.metrics()["duplicates"], 1)

    def test_fail_closed_on_required_consumer_failure(self) -> None:
        class FailingStore:
            consumer_id = "ingress.store"
            kind = IngressConsumerKind.STORE
            required = True

            def consume(self, event, *, context):  # type: ignore[no-untyped-def]
                raise RuntimeError("STORE_DOWN")

        router = ObservationIngressRouter([FailingStore()])
        ctx = NormalizationContext(
            received_time_ns=T0 + FIVE_SEC,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        normalized = normalize_moomoo_capture(_moomoo_quote_fixture(), context=ctx)
        with self.assertRaises(IngressDispatchError) as err:
            dispatch_normalization_result(
                router,
                normalized,
                context=IngressDispatchContext(dispatch_time_ns=T0 + FIVE_SEC),
            )
        self.assertEqual(err.exception.code, "INGRESS_REQUIRED_CONSUMER_FAILED")

    def test_journal_replay_is_deterministic(self) -> None:
        repo = InMemoryIntelligenceRepository()
        audit: list = []
        router = ObservationIngressRouter([store_consumer(repo), audit_sink_consumer(audit)])
        ctx = NormalizationContext(
            received_time_ns=T0 + FIVE_SEC,
            ingestion_mode=IngestionMode.REPLAY,
        )
        normalized = normalize_moomoo_capture(_moomoo_quote_fixture(), context=ctx)
        dispatch_ctx = IngressDispatchContext(dispatch_time_ns=T0 + FIVE_SEC)
        receipt = dispatch_normalization_result(router, normalized, context=dispatch_ctx)
        assert receipt is not None
        event = normalized.event
        assert event is not None
        replayed = router.replay_from_journal({event.event_id: event}, dispatch_time_ns=T0 + FIVE_SEC + 1)
        self.assertEqual(len(replayed), 1)
        self.assertFalse(replayed[0].duplicate)

    def test_forbidden_consumer_kind_rejected(self) -> None:
        from market_platform_foundation.intelligence.observation_ingress.types import validate_consumer_kind

        with self.assertRaises(ValueError):
            validate_consumer_kind("BROKER_ACTION")


if __name__ == "__main__":
    unittest.main()
