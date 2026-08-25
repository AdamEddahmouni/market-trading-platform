"""BUILD 03 — provider normalization and provenance tests."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.fred.contracts import MacroObservation  # noqa: E402
from market_platform_foundation.intelligence.contracts import event_v1_to_dict  # noqa: E402
from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    AvailabilityBasis,
    AvailabilityConfidence,
    IngestionMode,
    NormalizationContext,
    NormalizationError,
    NormalizationErrorCode,
    ProviderProvenance,
    normalize_event,
    provenance_from_event,
    registered_sources,
    require_normalized_event,
)
from market_platform_foundation.intelligence.normalization.providers.moomoo import (  # noqa: E402
    normalize_moomoo_capture,
)
from market_platform_foundation.intelligence.normalization.providers.sec_edgar import (  # noqa: E402
    normalize_sec_filing,
)
from market_platform_foundation.intelligence.normalization.timestamps import parse_timestamp_ns  # noqa: E402
from market_platform_foundation.intelligence.temporal import (  # noqa: E402
    classify_duplicate_events,
    inspect_temporal_integrity,
)
from market_platform_foundation.short_intelligence.contracts import (  # noqa: E402
    FailsToDeliverObservation,
    ObservationFamily,
    ShortInterestObservation,
)

T0 = 1_000_000_000_000
FIVE_SEC = 5 * 1_000_000_000
ONE_SEC = 1_000_000_000


def _live_context(received: int = T0 + FIVE_SEC) -> NormalizationContext:
    return NormalizationContext(
        received_time_ns=received,
        ingestion_mode=IngestionMode.LIVE_OBSERVED,
    )


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


class RegistryTests(unittest.TestCase):
    def test_registered_sources_include_core_providers(self) -> None:
        sources = registered_sources()
        for key in ("moomoo.capture", "sec.edgar.filing", "finviz", "sec.ftd", "finra.short_interest", "fred.macro"):
            self.assertIn(key, sources)


class TimestampTests(unittest.TestCase):
    def test_parse_timestamp_ns_explicit_unit(self) -> None:
        ns, diag = parse_timestamp_ns(T0, field_name="t", unit="ns")
        self.assertIsNone(diag)
        self.assertEqual(ns, T0)

    def test_unknown_timestamp_unit_fails(self) -> None:
        _, diag = parse_timestamp_ns(T0, field_name="t", unit="fortnight")
        self.assertIsNotNone(diag)
        self.assertEqual(diag.code, NormalizationErrorCode.UNKNOWN_TIMESTAMP_UNIT)


class MoomooNormalizationTests(unittest.TestCase):
    def test_quote_normalization_live(self) -> None:
        raw = _moomoo_quote_fixture()
        result = normalize_moomoo_capture(raw, context=_live_context())
        self.assertIsNotNone(result.event)
        event = result.event
        assert event is not None
        self.assertEqual(event.event_type, "QUOTE")
        self.assertEqual(event.instrument_id, "NVDA")
        self.assertEqual(event.received_time_ns, T0 + FIVE_SEC)
        self.assertGreaterEqual(event.available_time_ns, event.received_time_ns)
        self.assertIn("bid", event.payload)

    def test_deterministic_event_id(self) -> None:
        raw = _moomoo_quote_fixture()
        ctx = _live_context()
        first = normalize_moomoo_capture(raw, context=ctx).event
        second = normalize_moomoo_capture(raw, context=ctx).event
        assert first is not None and second is not None
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(event_v1_to_dict(first), event_v1_to_dict(second))

    def test_raw_input_immutability(self) -> None:
        raw = _moomoo_quote_fixture()
        snapshot = copy.deepcopy(raw)
        normalize_moomoo_capture(raw, context=_live_context())
        self.assertEqual(raw, snapshot)

    def test_unsupported_capability(self) -> None:
        raw = {"capability": "UNKNOWN_WIDGET", "provider_symbol": "US.NVDA"}
        result = normalize_moomoo_capture(raw, context=_live_context())
        self.assertIsNone(result.event)
        self.assertTrue(result.diagnostics)


class SecEdgarTests(unittest.TestCase):
    def test_filing_uses_accession_identity(self) -> None:
        filing = {
            "accession_number": "0001234567-24-000001",
            "form_type": "4",
            "filing_date": "2024-01-15",
            "acceptance_datetime": "2024-01-15T16:05:03",
            "cik": "0000320193",
        }
        ctx = NormalizationContext(
            received_time_ns=T0,
            ingestion_mode=IngestionMode.HISTORICAL_RECONSTRUCTED,
            historical_available_time_ns=T0 + ONE_SEC,
            availability_basis=AvailabilityBasis.PUBLICATION_TIME,
        )
        result = normalize_sec_filing(filing, context=ctx, instrument_id="AAPL")
        self.assertIsNotNone(result.event)
        event = result.event
        assert event is not None
        self.assertEqual(event.event_type, "FILING")
        self.assertEqual(event.source.external_id, "0001234567-24-000001")
        self.assertLess(event.event_time_ns, event.available_time_ns + ONE_SEC)


class MacroInstrumentlessTests(unittest.TestCase):
    def test_macro_release_has_no_instrument(self) -> None:
        obs = MacroObservation(
            canonical_indicator_id="CPIAUCSL",
            series_id="CPIAUCSL",
            observation_date="2024-01-01",
            raw_value="3.1",
            normalized_value=3.1,
            frequency="M",
            units="Percent",
            seasonal_adjustment="SA",
            source_agency="BLS",
            fred_release_id=10,
            realtime_start="2024-01-01",
            realtime_end="2024-01-01",
            vintage_date="2024-01-01",
            available_time="2024-01-12T13:30:00Z",
        )
        ctx = NormalizationContext(
            received_time_ns=T0,
            ingestion_mode=IngestionMode.HISTORICAL_RECONSTRUCTED,
        )
        result = normalize_event(obs, context=ctx, source_key="fred.macro")
        self.assertIsNotNone(result.event)
        event = result.event
        assert event is not None
        self.assertIsNone(event.instrument_id)
        self.assertEqual(event.event_type, "MACRO_RELEASE")


class TemporalCompositionTests(unittest.TestCase):
    def test_delayed_live_composition(self) -> None:
        raw = _moomoo_quote_fixture()
        raw["clocks"] = {
            "event_time_ns": T0,
            "provider_time_ns": T0,
            "received_time_ns": T0 + FIVE_SEC,
        }
        ctx = NormalizationContext(received_time_ns=T0 + FIVE_SEC, ingestion_mode=IngestionMode.LIVE_OBSERVED)
        event = require_normalized_event(raw, context=ctx, source_key="moomoo.capture")
        early = inspect_temporal_integrity(event, decision_time_ns=T0 + 2 * ONE_SEC)
        late = inspect_temporal_integrity(event, decision_time_ns=T0 + 6 * ONE_SEC)
        self.assertFalse(early.eligible)
        self.assertTrue(late.eligible)

    def test_provider_time_cannot_bypass_availability(self) -> None:
        from market_platform_foundation.intelligence.contracts import (  # noqa: E402
            QualityState,
            QualitySummary,
            SourceReference,
        )
        from market_platform_foundation.intelligence.contracts.event import EventV1  # noqa: E402

        event = EventV1(
            event_id="evt-bypass",
            schema_version="1",
            event_type="TRADE",
            event_time_ns=T0,
            available_time_ns=T0 + FIVE_SEC,
            payload={"px": 1.0},
            quality=QualitySummary(state=QualityState.GOOD),
            source=SourceReference(provider_id="TEST", source_type="unit", source_record_id="r1"),
            provider_time_ns=T0,
            received_time_ns=T0 + FIVE_SEC,
        )
        report = inspect_temporal_integrity(event, decision_time_ns=T0 + 2 * ONE_SEC)
        self.assertFalse(report.eligible)


class ConflictDuplicateTests(unittest.TestCase):
    def test_same_identity_different_payload_conflict(self) -> None:
        raw1 = _moomoo_quote_fixture()
        raw2 = copy.deepcopy(raw1)
        raw2["raw_payload"]["bid_price"] = 99.0
        ctx = _live_context()
        e1 = require_normalized_event(raw1, context=ctx, source_key="moomoo.capture")
        e2 = require_normalized_event(raw2, context=ctx, source_key="moomoo.capture")
        self.assertEqual(e1.event_id, e2.event_id)
        self.assertEqual(
            classify_duplicate_events(e1, e2),
            __import__(
                "market_platform_foundation.intelligence.temporal.models",
                fromlist=["TemporalViolationCode"],
            ).TemporalViolationCode.CONFLICTING_DUPLICATE,
        )


class StrictApiTests(unittest.TestCase):
    def test_unknown_record_strict_error(self) -> None:
        with self.assertRaises(NormalizationError) as ctx:
            require_normalized_event({"foo": "bar"}, context=_live_context())
        self.assertEqual(ctx.exception.code, NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD)

    def test_malformed_timestamp_strict(self) -> None:
        _, diag = parse_timestamp_ns("not-a-number", field_name="t", unit="ns")
        self.assertIsNotNone(diag)
        self.assertEqual(diag.code, NormalizationErrorCode.INVALID_TIMESTAMP)


class NumericSentinelTests(unittest.TestCase):
    def test_na_not_zero(self) -> None:
        from market_platform_foundation.intelligence.normalization.numeric import normalize_optional_float  # noqa: E402

        val, diag = normalize_optional_float("N/A", field_name="x")
        self.assertIsNone(val)
        self.assertIsNone(diag)


class ProvenanceTests(unittest.TestCase):
    def test_provenance_round_trip(self) -> None:
        prov = ProviderProvenance(
            provider_id="test",
            source_record_type="unit",
            adapter_id="test.adapter",
            adapter_version="1",
            normalization_version="test/1",
            availability=__import__(
                "market_platform_foundation.intelligence.normalization.models",
                fromlist=["AvailabilityDerivation"],
            ).AvailabilityDerivation(
                basis=AvailabilityBasis.LOCAL_RECEIPT,
                confidence=AvailabilityConfidence.DIRECTLY_OBSERVED,
            ),
        )
        restored = ProviderProvenance.from_dict(prov.to_dict())
        self.assertEqual(restored.provider_id, prov.provider_id)
        self.assertEqual(restored.availability.basis, AvailabilityBasis.LOCAL_RECEIPT)

    def test_event_provenance_round_trip(self) -> None:
        event = require_normalized_event(_moomoo_quote_fixture(), context=_live_context(), source_key="moomoo.capture")
        prov = provenance_from_event(event)
        self.assertIsNotNone(prov)
        assert prov is not None
        self.assertEqual(prov.adapter_id, "moomoo.capture")


class SecretRedactionTests(unittest.TestCase):
    def test_no_secrets_in_provenance(self) -> None:
        raw = _moomoo_quote_fixture()
        raw["api_key"] = "secret-key-should-not-appear"
        raw["password"] = "hunter2"
        event = require_normalized_event(raw, context=_live_context(), source_key="moomoo.capture")
        serialized = str(event_v1_to_dict(event))
        self.assertNotIn("secret-key-should-not-appear", serialized)
        self.assertNotIn("hunter2", serialized)


class FinvizTests(unittest.TestCase):
    def test_finviz_candidate_normalization(self) -> None:
        candidate = {
            "provider_symbol": "NVDA",
            "screen_id": "SHORT_SQUEEZE_DISCOVERY",
            "screen_version": "1",
            "discovered_at": "2024-06-01T14:30:00Z",
            "available_time_ns": T0,
            "metrics": {"rel_volume": 2.5},
            "matched_reasons": ["RVOL 2.50"],
            "inspection_priority": 90,
            "quality": "PASS",
            "rank": 1,
        }
        ctx = NormalizationContext(
            received_time_ns=T0,
            ingestion_mode=IngestionMode.HISTORICAL_RECONSTRUCTED,
        )
        result = normalize_event(candidate, context=ctx, source_key="finviz")
        self.assertIsNotNone(result.event)
        event = result.event
        assert event is not None
        self.assertEqual(event.instrument_id, "NVDA")
        self.assertEqual(event.event_type, "DISCOVERY_CANDIDATE")


class IbkrInterfaceTests(unittest.TestCase):
    def test_ibkr_returns_unsupported_not_fabricated(self) -> None:
        result = normalize_event(
            {"record_type": "ibkr_snapshot", "symbol": "AAPL"},
            context=_live_context(),
            source_key="ibkr",
        )
        self.assertIsNone(result.event)
        self.assertEqual(result.diagnostics[0].code, NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD)


if __name__ == "__main__":
    unittest.main()
