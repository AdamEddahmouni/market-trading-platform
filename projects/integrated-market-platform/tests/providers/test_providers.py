"""Phase 9 provider and whale ledger tests."""

from __future__ import annotations

import importlib
import pkgutil
import sys
import unittest
from dataclasses import fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import sha256_bytes
from market_platform_foundation.features.institutional import (
    NO_ENTITLED_SOURCE,
    REGULATORY_DISCLOSURE_FAMILY,
    configure_institutional_ledger,
    get_institutional_ledger,
    query_all_institutional,
    query_institutional_evidence,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.adapters.edgar_disclosure import (
    DEFAULT_FIXTURE,
    FixtureEdgarDisclosureProvider,
)
from market_platform_foundation.providers.composition import (
    ProviderComposition,
    configure_provider_composition,
    get_provider_composition,
)
from market_platform_foundation.providers.contracts import EXECUTION_DISABLED, PROVIDER_UNAVAILABLE
from market_platform_foundation.providers.whale_ledger import (
    WHALE_ENTITLED_DISCLOSURE,
    WhaleLedger,
    build_ledger_from_edgar_fixture,
)
from market_platform_foundation.replay.feature_lifecycle import verify_capability_surface
from market_platform_foundation.ui_api.projections import build_capabilities
from market_platform_foundation.ui_api.store import ReplayStore


class ProviderContractTests(unittest.TestCase):
    def setUp(self) -> None:
        configure_provider_composition(None)

    def test_unconfigured_stubs_fail_closed(self) -> None:
        composition = ProviderComposition()
        results = {
            "disclosure": composition.disclosure.fetch_disclosures("BIYA"),
            "reference_data": composition.reference_data.resolve_symbol("BIYA"),
            "equity_quote": composition.equity_quote.fetch_quote("BIYA"),
            "option_chain": composition.option_chain.fetch_chain("BIYA"),
            "futures_chain": composition.futures_chain.fetch_chain("ES"),
            "futures_positioning": composition.futures_positioning.fetch_positioning("ES"),
            "futures_bars": composition.futures_bars.fetch_bars("ES"),
            "futures_macro": composition.futures_macro.fetch_macro_events("ES"),
            "futures_margin": composition.futures_margin.fetch_margin("ES"),
            "distribution_forecast": (
                composition.distribution_forecast.fetch_distribution_forecast("BIYA")
            ),
            "order_flow": composition.order_flow.fetch_order_flow("BIYA"),
            "paper_execution": composition.paper_execution.place_order({}),
        }
        default_provider_fields = {field.name for field in fields(ProviderComposition)}
        self.assertEqual(set(results), default_provider_fields)

        for provider_name, result in results.items():
            with self.subTest(provider_name=provider_name):
                self.assertEqual(result.status, "unavailable")
                self.assertEqual(
                    result.capability,
                    getattr(composition, provider_name).capability,
                )
                expected_reason = (
                    EXECUTION_DISABLED
                    if provider_name == "paper_execution"
                    else PROVIDER_UNAVAILABLE
                )
                self.assertEqual(result.reason_code, expected_reason)

    def test_default_composition_uses_stubs(self) -> None:
        composition = get_provider_composition()
        self.assertEqual(composition.disclosure.provider_id, "stub.disclosure.unconfigured")


class EdgarAdapterTests(unittest.TestCase):
    def test_fixture_ingest_is_deterministic(self) -> None:
        first = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE)
        second = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE)
        self.assertEqual(first.root_hash(), second.root_hash())
        self.assertGreater(len(first.events), 0)

    def test_pit_cutoff_excludes_future_filings(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-16T23:59:59Z")
        ledger = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE, as_of_time_ns=cutoff)
        events = ledger.query_events(
            family="regulatory_disclosure",
            instrument_id="BIYA",
            prediction_cutoff=cutoff,
        )
        accession_numbers = {
            str(event["disclosure_event"]["accession_number"])
            for event in events
            if isinstance(event.get("disclosure_event"), dict)
        }
        self.assertIn("0001849639-26-000010", accession_numbers)
        self.assertNotIn("0001849639-26-000099", accession_numbers)

    def test_amendment_ordering_after_base_filing(self) -> None:
        provider = FixtureEdgarDisclosureProvider(fixture_path=DEFAULT_FIXTURE)
        envelopes = provider.build_envelopes()
        revisions = [
            (str(row["source_record_id"]), str(row["source_revision_id"]))
            for row in envelopes
            if str(row["source_record_id"]) == "0001849639-26-000010"
        ]
        self.assertEqual(revisions, [("0001849639-26-000010", "1"), ("0001849639-26-000010", "2")])

    def test_unknown_symbol_unavailable(self) -> None:
        provider = FixtureEdgarDisclosureProvider(fixture_path=DEFAULT_FIXTURE)
        result = provider.fetch_disclosures("ZZZZ")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "EDGAR_SYMBOL_NOT_IN_FIXTURE")


class WhaleLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(None)

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_institutional_unavailable_without_ledger(self) -> None:
        rows = query_all_institutional(prediction_cutoff=10**30)
        self.assertTrue(all(row["status"] == "unavailable" for row in rows))
        self.assertTrue(all(row["reason_code"] == NO_ENTITLED_SOURCE for row in rows))

    def test_regulatory_disclosure_available_with_ledger(self) -> None:
        ledger = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE)
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-16T23:59:59Z")
        row = query_institutional_evidence(
            REGULATORY_DISCLOSURE_FAMILY,
            prediction_cutoff=cutoff,
            instrument_id="BIYA",
        )
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["reason_code"], WHALE_ENTITLED_DISCLOSURE)
        other = query_institutional_evidence("order_flow", prediction_cutoff=cutoff)
        self.assertEqual(other["status"], "unavailable")

    def test_capability_surface_allows_entitled_disclosure(self) -> None:
        ledger = build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE)
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2026-07-16T23:59:59Z")
        institutional = query_all_institutional(prediction_cutoff=cutoff, instrument_id="BIYA")
        snapshot = {
            "bar_features": [],
            "institutional_evidence": institutional,
            "prediction_cutoff": cutoff,
        }
        status, reasons = verify_capability_surface(snapshot)
        self.assertEqual(status, "PASS")
        self.assertEqual(reasons, [])

    def test_dedup_on_append(self) -> None:
        ledger = WhaleLedger()
        event = {
            "available_time": 1,
            "disclosure_event": {"family": "regulatory_disclosure"},
            "normalized_event_id": "evt-1",
            "source_record_id": "acc-1",
            "source_revision_id": "1",
        }
        self.assertEqual(ledger.append([event]), 1)
        self.assertEqual(ledger.append([event]), 0)


class ImportBoundaryTests(unittest.TestCase):
    def test_features_do_not_import_adapters(self) -> None:
        import market_platform_foundation.features.institutional as institutional

        source_path = Path(institutional.__file__).resolve()
        text = source_path.read_text(encoding="utf-8")
        self.assertNotIn("providers.adapters", text)

    def test_strategy_package_has_no_http_adapter_imports(self) -> None:
        strategy_root = SRC / "market_platform_foundation" / "strategy"
        for module in pkgutil.walk_packages([str(strategy_root)], prefix="market_platform_foundation.strategy."):
            loaded = importlib.import_module(module.name)
            module_path = Path(loaded.__file__).resolve()
            text = module_path.read_text(encoding="utf-8")
            self.assertNotIn("urllib.request", text)
            self.assertNotIn("providers.adapters.edgar_disclosure", text)


class UiDisclosureProjectionTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=ROOT.parent)
        cls.store.load()

    def test_capabilities_show_disclosure_available(self) -> None:
        caps = build_capabilities(self.store)
        by_id = {row["capability_id"]: row for row in caps}
        self.assertEqual(by_id["whale.disclosure"]["state"], "AVAILABLE")
        self.assertEqual(by_id["whale.regulatory_disclosure"]["state"], "AVAILABLE")
        self.assertEqual(by_id["whale.order_flow"]["state"], "AVAILABLE")
        self.assertEqual(by_id["whale.options"]["state"], "AVAILABLE")
        self.assertEqual(by_id["whale.large_transactions"]["state"], "AVAILABLE")
        self.assertEqual(by_id["whale.order_book"]["state"], "AVAILABLE")
        self.assertEqual(by_id["depth.L2"]["state"], "AVAILABLE")

    def test_workspace_disclosure_payload(self) -> None:
        from market_platform_foundation.providers.projections import build_workspace_disclosure_payload

        payload = build_workspace_disclosure_payload(
            "BIYA",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=self.store.prediction_cutoff(),
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["research_only"])
        self.assertIn("disclosure_lag_note", payload)
        self.assertGreater(payload["event_count"], 0)


if __name__ == "__main__":
    unittest.main()
