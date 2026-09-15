"""EventV1 normalization + ingress for Market Trackers congressional PTR rows (Lane F)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
    get_normalizer,
)
from market_platform_foundation.intelligence.normalization.errors import (  # noqa: E402
    NormalizationErrorCode,
)
from market_platform_foundation.intelligence.normalization.providers.market_trackers_congressional_disclosure import (  # noqa: E402
    normalize_congressional_disclosure_row,
)
from market_platform_foundation.intelligence.observation_ingress import (  # noqa: E402
    build_production_observation_ingress_router,
    dispatch_congressional_disclosure_row,
)
from market_platform_foundation.intelligence.observation_ingress.types import IngressDispatchContext  # noqa: E402
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.market_trackers.congressional_disclosure.reconcile import (  # noqa: E402
    reconcile_congressional_clocks,
)

_MT_FIXTURES = ROOT / "tests" / "fixtures" / "market_trackers" / "congressional_disclosure"
_PTR_FIXTURES = ROOT / "tests" / "fixtures" / "congressional_disclosure"
_PLATFORM_RECEIVED_NS = 1_725_100_800_000_000_000
ONE_DAY = 86_400_000_000_000


def _load_mt(name: str) -> dict:
    return json.loads((_MT_FIXTURES / name).read_text(encoding="utf-8"))


def _load_ptr(name: str) -> dict:
    return json.loads((_PTR_FIXTURES / name).read_text(encoding="utf-8"))


class CongressionalDisclosureEventV1Tests(unittest.TestCase):
    def test_registry_registers_normalizer(self) -> None:
        fn = get_normalizer("market_trackers.congressional_disclosure")
        self.assertIsNotNone(fn)
        self.assertIs(fn, normalize_congressional_disclosure_row)

    def test_senate_golden_event_v1_five_clocks(self) -> None:
        row = _load_mt("senate_stock_purchase.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=ctx)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        clocks = result.event.payload["clocks"]
        self.assertGreater(clocks["economic_event_time_ns"], 0)
        self.assertGreater(clocks["filing_publication_time_ns"], 0)
        self.assertEqual(clocks["platform_received_time_ns"], _PLATFORM_RECEIVED_NS)
        self.assertGreater(result.event.available_time_ns, clocks["economic_event_time_ns"])
        flags = result.event.payload["reconcile_flags"]
        self.assertIn("PTR_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY", flags)
        evidence = result.event.payload["public_record_evidence"]
        self.assertIn("PTR_NOT_AUTO_DIRECTIONAL", evidence["uncertainty_flags"])

    def test_house_sale_fixture(self) -> None:
        row = _load_mt("house_stock_sale.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=ctx)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        self.assertEqual(result.event.payload["chamber"], "house")
        self.assertEqual(result.event.payload["disclosed_side"], "sell")

    def test_primary_ptr_reconcile(self) -> None:
        row = _load_mt("senate_stock_purchase.json")
        primary = _load_ptr("ptr_primary_senate_example.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=ctx, ptr_primary=primary)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        flags = result.event.payload["reconcile_flags"]
        self.assertIn("PRIMARY_SOURCE_PTR_WINS", flags)
        self.assertIn("PTR_PUBLICATION_FROM_PRIMARY", flags)
        self.assertTrue(result.event.payload["clock_doctrine"]["ptr_primary_supplied"])

    def test_day_only_primary_publication(self) -> None:
        row = _load_mt("senate_stock_purchase.json")
        primary = _load_ptr("ptr_primary_senate_day_only.json")
        clocks = reconcile_congressional_clocks(
            row,
            platform_received_time_ns=_PLATFORM_RECEIVED_NS,
            ptr_primary=primary,
        )
        self.assertIn("PTR_PUBLICATION_MISSING_DAY_BOUNDED_FILING", clocks.reconcile_flags)
        self.assertGreater(clocks.available_time_ns, clocks.economic_event_time_ns)
        self.assertNotIn("transactedAt", clocks.available_time_basis)

    def test_late_filing_lag_flags(self) -> None:
        row = _load_mt("senate_stock_exchange.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=ctx)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        self.assertGreater(result.event.payload["filed_at"], result.event.payload["transacted_at"])

    def test_missing_ticker_fail_closed(self) -> None:
        row = _load_mt("open_ended_amount_range.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=ctx)
        self.assertIsNone(result.event)
        self.assertEqual(result.diagnostics[0].code, NormalizationErrorCode.INVALID_INSTRUMENT)

    def test_open_ended_amount_range_flags(self) -> None:
        row = _load_mt("open_ended_amount_range.json")
        row = dict(row)
        row["ticker"] = "MSFT"
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=ctx)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        self.assertIn("OPEN_ENDED_AMOUNT_RANGE", result.event.payload["public_record_evidence"]["uncertainty_flags"])

    def test_exchange_side_evidence_flag(self) -> None:
        row = _load_mt("senate_stock_exchange.json")
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=ctx)
        assert result.event is not None
        self.assertEqual(result.event.payload["disclosed_side"], "exchange")
        self.assertIn(
            "EXCHANGE_NOT_SIMPLE_BUY_SELL",
            result.event.payload["public_record_evidence"]["uncertainty_flags"],
        )

    def test_transaction_date_is_not_available_time(self) -> None:
        row = _load_mt("senate_stock_purchase.json")
        clocks = reconcile_congressional_clocks(row, platform_received_time_ns=_PLATFORM_RECEIVED_NS)
        self.assertNotEqual(clocks.available_time_ns, clocks.economic_event_time_ns)

    def test_duplicate_dispatch_idempotent(self) -> None:
        row = _load_mt("senate_stock_purchase.json")
        norm_ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        repo = InMemoryIntelligenceRepository()
        router = build_production_observation_ingress_router(repo)
        dispatch_ctx = IngressDispatchContext(
            dispatch_time_ns=_PLATFORM_RECEIVED_NS + ONE_DAY,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        first = dispatch_congressional_disclosure_row(
            router,
            row,
            normalization_context=norm_ctx,
            dispatch_context=dispatch_ctx,
        )
        second = dispatch_congressional_disclosure_row(
            router,
            row,
            normalization_context=norm_ctx,
            dispatch_context=dispatch_ctx,
        )
        assert first is not None and second is not None
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)

    def test_explicit_replay_allows_redispatch(self) -> None:
        row = _load_mt("house_stock_sale.json")
        norm_ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=norm_ctx)
        assert result.event is not None
        repo = InMemoryIntelligenceRepository()
        router = build_production_observation_ingress_router(repo)
        dispatch_ctx = IngressDispatchContext(
            dispatch_time_ns=_PLATFORM_RECEIVED_NS + ONE_DAY,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        first = router.dispatch(result.event, context=dispatch_ctx)
        replay = router.dispatch(result.event, context=dispatch_ctx, allow_duplicate_replay=True)
        self.assertFalse(first.duplicate)
        self.assertFalse(replay.duplicate)
        self.assertEqual(first.dispatch_id, replay.dispatch_id)
        self.assertEqual(router.metrics()["dispatched"], 2)


if __name__ == "__main__":
    unittest.main()
