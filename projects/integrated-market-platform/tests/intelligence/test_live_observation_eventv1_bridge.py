"""Live observation → EventV1 production ingress bridge (LIVE_OBSERVED)."""

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
from market_platform_foundation.intelligence.normalization.errors import (  # noqa: E402
    NormalizationErrorCode,
)
from market_platform_foundation.intelligence.normalization.models import (  # noqa: E402
    PROVENANCE_METADATA_KEY,
)
from market_platform_foundation.intelligence.observation_ingress import (  # noqa: E402
    ObservationIngressRouter,
    audit_sink_consumer,
    build_production_observation_ingress_router,
    detector_stub_consumer,
    dispatch_admitted_live_observation,
    enrichment_trigger_consumer,
    normalize_admitted_live_observation,
    oe_evidence_consumer,
    store_consumer,
)
from market_platform_foundation.intelligence.observation_ingress.live_observation_dispatch import (  # noqa: E402
    canonicalize_live_observation_record,
    resolve_live_observation_source_key,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime  # noqa: E402
from market_platform_foundation.market_data.normalization import live_envelope_from_capture  # noqa: E402

T0 = 1_700_000_000_000_000_000
FIVE_SEC = 5 * 1_000_000_000


def _live_quote_record(*, sequence: int = 42, capability: str = "US_EQUITY_L1") -> dict:
    return {
        "provider": "moomoo.opend.observational",
        "capability": capability,
        "provider_symbol": "US.NVDA",
        "instrument_id": "NVDA",
        "sequence": sequence,
        "schema_version": "market_data.provider_envelope/1.0.0",
        "clocks": {
            "event_time_ns": T0,
            "provider_time_ns": T0 + 5_000_000,
            "available_time_ns": T0 + 10_000_000,
            "received_time_ns": T0 + FIVE_SEC,
        },
        "quality_flags": [],
        "raw_payload": {
            "bid_price": 100.0,
            "ask_price": 100.05,
            "bid_vol": 500,
            "ask_vol": 400,
            "last_price": 100.02,
            "code": "US.NVDA",
        },
    }


def _live_bar_envelope(*, sequence: int = 7) -> tuple[dict, dict]:
    """Admitted-shaped bar observation: capture record + live envelope."""
    record = {
        "provider": "moomoo.opend.observational",
        "capability": "US_EQUITY_BARS",
        "provider_symbol": "US.AAPL",
        "instrument_id": "AAPL",
        "sequence": sequence,
        "schema_version": "market_data.provider_envelope/1.0.0",
        "clocks": {
            "event_time_ns": T0,
            "provider_time_ns": T0,
            "available_time_ns": T0 + 1_000_000,
            "received_time_ns": T0 + FIVE_SEC,
        },
        "quality_flags": [],
        "raw_payload": {
            "open": 190.0,
            "high": 191.0,
            "low": 189.5,
            "close": 190.5,
            "volume": 1000,
            "code": "US.AAPL",
        },
    }
    envelope = live_envelope_from_capture(record)
    return record, envelope


class LiveObservationEventV1BridgeTests(unittest.TestCase):
    def test_canonicalize_maps_opend_l1_to_quote(self) -> None:
        prepared = canonicalize_live_observation_record(_live_quote_record())
        self.assertEqual(prepared["capability"], "QUOTE")
        self.assertEqual(prepared["source_capability"], "US_EQUITY_L1")
        self.assertEqual(resolve_live_observation_source_key(prepared), "moomoo.capture")

    def test_normalize_live_quote_preserves_pit_and_provenance(self) -> None:
        record = _live_quote_record()
        result = normalize_admitted_live_observation(record)
        self.assertTrue(result.ok)
        event = result.event
        assert event is not None
        self.assertEqual(event.event_type, "QUOTE")
        self.assertEqual(event.event_time_ns, T0)
        self.assertEqual(event.received_time_ns, T0 + FIVE_SEC)
        # LIVE_OBSERVED availability floor is local receipt.
        self.assertEqual(event.available_time_ns, T0 + FIVE_SEC)
        self.assertGreaterEqual(event.available_time_ns, event.event_time_ns)
        provenance = event.metadata.get(PROVENANCE_METADATA_KEY) or {}
        self.assertEqual(provenance.get("ingestion_mode"), IngestionMode.LIVE_OBSERVED.value)
        self.assertEqual(provenance.get("provider_id"), "moomoo.opend.observational")
        self.assertEqual(provenance.get("adapter_id"), "moomoo.capture")

    def test_refuse_non_live_ingestion_mode(self) -> None:
        result = normalize_admitted_live_observation(
            _live_quote_record(),
            context=NormalizationContext(
                received_time_ns=T0 + FIVE_SEC,
                ingestion_mode=IngestionMode.REPLAY,
            ),
        )
        self.assertIsNone(result.event)
        self.assertEqual(result.diagnostics[0].code, NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD)

    def test_bar_envelope_uses_envelope_normalizer(self) -> None:
        record, envelope = _live_bar_envelope()
        self.assertEqual(
            resolve_live_observation_source_key(record, envelope=envelope),
            "envelope",
        )
        result = normalize_admitted_live_observation(record, envelope=envelope)
        self.assertTrue(result.ok)
        event = result.event
        assert event is not None
        self.assertEqual(event.event_type, "US_EQUITY_BARS")
        self.assertEqual(event.instrument_id, "AAPL")
        self.assertEqual(event.event_id, envelope["normalized_event_id"])
        provenance = event.metadata.get(PROVENANCE_METADATA_KEY) or {}
        self.assertEqual(provenance.get("ingestion_mode"), IngestionMode.LIVE_OBSERVED.value)
        self.assertEqual(provenance.get("adapter_id"), "envelope.bridge")

    def test_unsupported_capability_without_envelope_fails_closed(self) -> None:
        record = _live_quote_record(capability="US_EQUITY_BARS")
        result = normalize_admitted_live_observation(record)
        self.assertIsNone(result.event)
        self.assertEqual(result.diagnostics[0].code, NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD)

    def test_dispatch_to_production_ingress_is_idempotent(self) -> None:
        repo = InMemoryIntelligenceRepository()
        audit: list = []
        evidence: list[dict[str, str]] = []
        seen: set[str] = set()
        router = build_production_observation_ingress_router(
            repo,
            audit_replay_sink=audit,
            oe_evidence_sink=evidence,
            detector_seen=seen,
        )
        record = _live_quote_record()
        first = dispatch_admitted_live_observation(router, record)
        assert first is not None
        self.assertFalse(first.duplicate)
        event_id = first.event_id
        self.assertIsNotNone(repo.get_event(event_id))
        self.assertEqual(len(audit), 1)
        self.assertEqual(evidence[0]["event_id"], event_id)
        self.assertIn(event_id, seen)

        second = dispatch_admitted_live_observation(router, record)
        assert second is not None
        self.assertTrue(second.duplicate)
        self.assertEqual(router.metrics()["duplicates"], 1)
        self.assertEqual(len(audit), 1)

    def test_admitted_runtime_path_emits_eventv1_when_router_attached(self) -> None:
        repo = InMemoryIntelligenceRepository()
        router = ObservationIngressRouter(
            [
                store_consumer(repo),
                audit_sink_consumer([]),
                oe_evidence_consumer([]),
                detector_stub_consumer(set()),
                enrichment_trigger_consumer(),
            ]
        )
        runtime = LiveObservationalRuntime()
        runtime.attach_observation_ingress(router)
        runtime.admission.on_connect()
        record = _live_quote_record(sequence=99)
        result = runtime.ingest_record(record, wall_now_ns=T0 + FIVE_SEC + 1_000_000)
        self.assertEqual(result["admission"]["display"], "DISPLAY_ADMITTED")
        self.assertEqual(runtime.ingress_metrics["dispatched"], 1)
        self.assertEqual(runtime.ingress_metrics["failed"], 0)
        # Deterministic event_id from moomoo.capture normalizer.
        normalized = normalize_admitted_live_observation(record)
        assert normalized.event is not None
        self.assertIsNotNone(repo.get_event(normalized.event.event_id))

    def test_runtime_without_router_does_not_emit(self) -> None:
        runtime = LiveObservationalRuntime()
        runtime.admission.on_connect()
        record = _live_quote_record(sequence=100)
        runtime.ingest_record(record, wall_now_ns=T0 + FIVE_SEC + 1_000_000)
        self.assertEqual(runtime.ingress_metrics["dispatched"], 0)
        self.assertIsNone(runtime.observation_ingress_router)

    def test_duplicate_admission_retry_does_not_double_dispatch(self) -> None:
        repo = InMemoryIntelligenceRepository()
        router = build_production_observation_ingress_router(repo)
        runtime = LiveObservationalRuntime()
        runtime.attach_observation_ingress(router)
        runtime.admission.on_connect()
        record = _live_quote_record(sequence=101)
        first = runtime.ingest_record(record, wall_now_ns=T0 + FIVE_SEC + 1_000_000)
        second = runtime.ingest_record(record, wall_now_ns=T0 + FIVE_SEC + 2_000_000)
        self.assertIsNotNone(first.get("envelope"))
        # Second pass is still evaluated; router idempotency prevents duplicate fan-out.
        self.assertEqual(runtime.ingress_metrics["dispatched"], 1)
        self.assertEqual(runtime.ingress_metrics["duplicates"], 1)
        self.assertEqual(router.metrics()["duplicates"], 1)
        _ = second

    def test_admission_blocked_skips_ingress(self) -> None:
        repo = InMemoryIntelligenceRepository()
        router = build_production_observation_ingress_router(repo)
        runtime = LiveObservationalRuntime()
        runtime.attach_observation_ingress(router)
        runtime.admission.on_disconnect()
        record = _live_quote_record(sequence=102)
        result = runtime.ingest_record(record, wall_now_ns=T0 + FIVE_SEC + 1_000_000)
        self.assertEqual(result["admission"]["display"], "BLOCKED")
        self.assertEqual(runtime.ingress_metrics["dispatched"], 0)
        self.assertEqual(runtime.ingress_metrics["skipped_not_admitted"], 1)

    def test_bridge_does_not_register_broker_consumers(self) -> None:
        from market_platform_foundation.intelligence.observation_ingress.types import (
            validate_consumer_kind,
        )

        for forbidden in ("BROKER_ACTION", "EXECUTION", "ORDER_SUBMIT"):
            with self.assertRaises(ValueError):
                validate_consumer_kind(forbidden)


if __name__ == "__main__":
    unittest.main()
