"""Observation ingress router — idempotent multi-consumer dispatch."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
    NormalizationResult,
)
from market_platform_foundation.intelligence.normalization.errors import (  # noqa: E402
    NormalizationDiagnostic,
    NormalizationErrorCode,
)
from market_platform_foundation.intelligence.normalization.providers.moomoo import (  # noqa: E402
    normalize_moomoo_capture,
)
from market_platform_foundation.intelligence.observation_ingress import (  # noqa: E402
    IngressConsumerKind,
    IngressConsumerOutcome,
    IngressConsumerStatus,
    IngressDispatchContext,
    IngressDispatchError,
    IngressDispatchJournal,
    IngressRouterPolicyV1,
    ObservationIngressRouter,
    audit_sink_consumer,
    detector_stub_consumer,
    dispatch_normalization_result,
    enrichment_trigger_consumer,
    oe_evidence_consumer,
    store_consumer,
)
from tests.intelligence.test_persistence_fixtures import sample_event  # noqa: E402
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
        class FailingMiddle:
            consumer_id = "ingress.middle_fail"
            kind = IngressConsumerKind.STORE
            required = True

            def consume(self, event, *, context):  # type: ignore[no-untyped-def]
                raise RuntimeError("STORE_DOWN")

        repo = InMemoryIntelligenceRepository()
        router = ObservationIngressRouter(
            [
                store_consumer(repo),
                FailingMiddle(),
                audit_sink_consumer([]),
            ]
        )
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
        self.assertEqual(len(err.exception.partial_outcomes), 3)
        by_id = {row["consumer_id"]: row for row in err.exception.partial_outcomes}
        self.assertEqual(by_id["ingress.middle_fail"]["status"], IngressConsumerStatus.FAILED.value)
        self.assertEqual(by_id["ingress.store"]["status"], IngressConsumerStatus.SKIPPED.value)
        self.assertEqual(by_id["ingress.audit_replay"]["status"], IngressConsumerStatus.OK.value)

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

    def test_invalid_quality_rejected(self) -> None:
        from market_platform_foundation.intelligence.contracts import EventV1

        repo = InMemoryIntelligenceRepository()
        router = ObservationIngressRouter([store_consumer(repo)])
        base = sample_event(
            "evt-invalid",
            event_time_ns=T0,
            available_time_ns=T0 + FIVE_SEC,
        )
        invalid = EventV1(
            event_id=base.event_id,
            schema_version=base.schema_version,
            event_type=base.event_type,
            event_time_ns=base.event_time_ns,
            available_time_ns=base.available_time_ns,
            payload=base.payload,
            quality=QualitySummary(state=QualityState.INVALID, flags=("TEST",)),
            source=base.source,
            instrument_id=base.instrument_id,
            received_time_ns=base.received_time_ns,
        )
        with self.assertRaises(ValueError) as err:
            router.dispatch(invalid, context=IngressDispatchContext(dispatch_time_ns=T0 + FIVE_SEC))
        self.assertIn("INGRESS_EVENT_QUALITY_INVALID", str(err.exception))

    def test_journal_bound_exceeded(self) -> None:
        repo = InMemoryIntelligenceRepository()
        journal = IngressDispatchJournal(max_entries=1)
        router = ObservationIngressRouter(
            [store_consumer(repo)],
            journal=journal,
        )
        ctx = NormalizationContext(received_time_ns=T0 + FIVE_SEC, ingestion_mode=IngestionMode.FIXTURE)
        normalized = normalize_moomoo_capture(_moomoo_quote_fixture(), context=ctx)
        dispatch_ctx = IngressDispatchContext(dispatch_time_ns=T0 + FIVE_SEC)
        first = dispatch_normalization_result(router, normalized, context=dispatch_ctx)
        self.assertIsNotNone(first)
        raw = _moomoo_quote_fixture()
        raw["sequence"] = 43
        second_norm = normalize_moomoo_capture(raw, context=ctx)
        with self.assertRaises(ValueError) as err:
            dispatch_normalization_result(router, second_norm, context=dispatch_ctx)
        self.assertIn("INGRESS_JOURNAL_BOUND_EXCEEDED", str(err.exception))

    def test_enrichment_trigger_bound_exceeded(self) -> None:
        repo = InMemoryIntelligenceRepository()
        policy = IngressRouterPolicyV1(max_enrichment_triggers=1)
        router = ObservationIngressRouter(
            [store_consumer(repo), enrichment_trigger_consumer()],
            policy=policy,
        )
        ctx = NormalizationContext(received_time_ns=T0 + FIVE_SEC, ingestion_mode=IngestionMode.FIXTURE)
        dispatch_ctx = IngressDispatchContext(dispatch_time_ns=T0 + FIVE_SEC)
        first = dispatch_normalization_result(
            router,
            normalize_moomoo_capture(_moomoo_quote_fixture(), context=ctx),
            context=dispatch_ctx,
        )
        self.assertIsNotNone(first)
        raw = _moomoo_quote_fixture()
        raw["sequence"] = 44
        second_norm = normalize_moomoo_capture(raw, context=ctx)
        with self.assertRaises(ValueError) as err:
            dispatch_normalization_result(router, second_norm, context=dispatch_ctx)
        self.assertIn("INGRESS_ENRICHMENT_TRIGGER_BOUND_EXCEEDED", str(err.exception))

    def test_optional_consumer_failure_does_not_abort(self) -> None:
        repo = InMemoryIntelligenceRepository()

        class FailingOptionalAudit:
            consumer_id = "ingress.audit_replay"
            kind = IngressConsumerKind.AUDIT_REPLAY
            required = False

            def consume(self, event, *, context):  # type: ignore[no-untyped-def]
                raise RuntimeError("AUDIT_DOWN")

        router = ObservationIngressRouter([FailingOptionalAudit(), store_consumer(repo)])
        event = sample_event("evt-opt-fail", event_time_ns=T0, available_time_ns=T0 + FIVE_SEC)
        receipt = router.dispatch(event, context=IngressDispatchContext(dispatch_time_ns=T0 + FIVE_SEC))
        self.assertFalse(receipt.duplicate)
        self.assertEqual(len(receipt.outcomes), 2)
        by_id = {row.consumer_id: row for row in receipt.outcomes}
        self.assertEqual(by_id["ingress.audit_replay"].status, IngressConsumerStatus.FAILED)
        self.assertEqual(by_id["ingress.store"].status, IngressConsumerStatus.OK)
        self.assertIsNotNone(repo.get_event(event.event_id))

    def test_consumers_invoked_in_sorted_consumer_id_order(self) -> None:
        invocation_order: list[str] = []

        class RecordingConsumer:
            def __init__(self, consumer_id: str) -> None:
                self.consumer_id = consumer_id
                self.kind = IngressConsumerKind.DETECTOR
                self.required = False

            def consume(self, event, *, context):  # type: ignore[no-untyped-def]
                invocation_order.append(self.consumer_id)
                return IngressConsumerOutcome(
                    consumer_id=self.consumer_id,
                    kind=self.kind,
                    status=IngressConsumerStatus.OK,
                )

        router = ObservationIngressRouter(
            [
                RecordingConsumer("z.consumer"),
                RecordingConsumer("a.consumer"),
                RecordingConsumer("m.consumer"),
            ]
        )
        self.assertEqual(router.consumer_ids, ("a.consumer", "m.consumer", "z.consumer"))
        event = sample_event("evt-order", event_time_ns=T0, available_time_ns=T0 + FIVE_SEC)
        router.dispatch(event, context=IngressDispatchContext(dispatch_time_ns=T0 + FIVE_SEC))
        self.assertEqual(invocation_order, ["a.consumer", "m.consumer", "z.consumer"])

    def test_dispatch_normalization_result_none_event(self) -> None:
        router = ObservationIngressRouter([store_consumer(InMemoryIntelligenceRepository())])
        result = NormalizationResult(event=None)
        receipt = dispatch_normalization_result(
            router,
            result,
            context=IngressDispatchContext(dispatch_time_ns=T0),
        )
        self.assertIsNone(receipt)

    def test_dispatch_normalization_result_with_diagnostics(self) -> None:
        router = ObservationIngressRouter([store_consumer(InMemoryIntelligenceRepository())])
        event = sample_event("evt-diag", event_time_ns=T0, available_time_ns=T0 + FIVE_SEC)
        result = NormalizationResult(
            event=event,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.MALFORMED_PAYLOAD,
                    message="synthetic diagnostic for ingress bridge test",
                ),
            ),
        )
        with self.assertRaises(IngressDispatchError) as err:
            dispatch_normalization_result(
                router,
                result,
                context=IngressDispatchContext(dispatch_time_ns=T0),
            )
        self.assertEqual(err.exception.code, "INGRESS_NORMALIZATION_DIAGNOSTICS")


if __name__ == "__main__":
    unittest.main()
