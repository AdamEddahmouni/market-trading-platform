"""G14 — canonical instrument selector and product surface tests."""

from __future__ import annotations

import time
import unittest

from market_platform_foundation.ui_api.g14_product_projections import (
    build_futures_product_payload,
    build_options_product_payload,
)
from market_platform_foundation.ui_api.instrument_route_codec import (
    decode_instrument_route_param,
    encode_instrument_route_param,
)
from market_platform_foundation.ui_api.instrument_selector import (
    build_selector_search_payload,
    ensure_g14_selector_catalog,
    resolve_instrument_route_ref,
    search_canonical_instruments,
)
from market_platform_foundation.xa01.enums import InstrumentKind
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests


class G14InstrumentRouteCodecTests(unittest.TestCase):
    def test_round_trip_preserves_identity(self) -> None:
        sample = "NVDA20260815C00130000"
        encoded = encode_instrument_route_param(sample)
        self.assertEqual(decode_instrument_route_param(encoded), sample)


class G14InstrumentSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()
        ensure_g14_selector_catalog(registry=self.registry)

    def test_equity_result(self) -> None:
        results = search_canonical_instruments("AAPL", registry=self.registry)
        kinds = {row["instrument_kind"] for row in results}
        self.assertIn("TRADABLE_SECURITY", kinds)

    def test_option_contract_result(self) -> None:
        results = search_canonical_instruments("NVDA20260815", registry=self.registry)
        self.assertTrue(any(row["instrument_kind"] == "OPTION_CONTRACT" for row in results))

    def test_future_family_non_executable(self) -> None:
        results = search_canonical_instruments("ES", registry=self.registry)
        family = next(row for row in results if row["instrument_kind"] == "FUTURE_FAMILY")
        self.assertFalse(family["execution_eligible"])
        self.assertEqual(family["selection_action"], "OPEN_FUTURE_FAMILY_REFERENCE")

    def test_future_contract_actionable(self) -> None:
        results = search_canonical_instruments("ES202512", registry=self.registry)
        contract = next(row for row in results if row["instrument_kind"] == "FUTURE_CONTRACT")
        self.assertTrue(contract["execution_eligible"])

    def test_crypto_pair_disambiguation(self) -> None:
        results = search_canonical_instruments("BTC", registry=self.registry)
        pairs = [row for row in results if row["instrument_kind"] == "CRYPTO_PAIR"]
        quotes = {row["metadata"].get("quote") for row in pairs}
        self.assertIn("USD", quotes)
        self.assertIn("USDT", quotes)

    def test_bounded_results(self) -> None:
        payload = build_selector_search_payload("A", limit=3)
        self.assertLessEqual(len(payload["results"]), 3)


class G14ProductProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()
        ensure_g14_selector_catalog(registry=self.registry)
        from market_platform_foundation.paper.ledger import PaperExecutionLedger

        self.ledger = PaperExecutionLedger.open_session(
            replay_session_id="g14-ui",
            instrument_id="BIYA",
            symbol="BIYA",
            policy={"initial_cash_minor": 100_000_00, "price_scale": 100, "currency": "USD"},
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )

        class _Store:
            paper_ledger = self.ledger
            instrument_id = "BIYA"
            cursor_index = 1

            def prediction_cutoff(self):
                return 0

        self.store = _Store()

    def test_route_ref_resolves_display_symbol_to_canonical_id(self) -> None:
        canonical_id = resolve_instrument_route_ref("NVDA20260815C00130000", registry=self.registry)
        option_id = next(
            row["instrument_id"]
            for row in search_canonical_instruments("NVDA20260815", registry=self.registry)
            if row["instrument_kind"] == "OPTION_CONTRACT"
        )
        self.assertEqual(canonical_id, option_id)

    def test_options_payload_carries_canonical_identity(self) -> None:
        option_id = next(
            row["instrument_id"]
            for row in search_canonical_instruments("NVDA20260815", registry=self.registry)
            if row["instrument_kind"] == "OPTION_CONTRACT"
        )
        payload = build_options_product_payload(self.store, "NVDA20260815C00130000", mode="PAPER")
        self.assertEqual(payload["instrument_id"], option_id)
        self.assertIn("runtime", payload)
        self.assertEqual(payload["runtime"]["instrument_kind"], InstrumentKind.OPTION_CONTRACT.value)

    def test_futures_family_non_actionable(self) -> None:
        family_id = next(
            row["instrument_id"]
            for row in search_canonical_instruments("ES", registry=self.registry)
            if row["instrument_kind"] == "FUTURE_FAMILY"
        )
        payload = build_futures_product_payload(self.store, family_id, mode="PAPER")
        self.assertFalse(payload["execution_available"])
        self.assertEqual(payload["status"], "UNSUPPORTED_INSTRUMENT")

    def test_futures_contract_margin_missing_or_available_explicit(self) -> None:
        contract_id = next(
            row["instrument_id"]
            for row in search_canonical_instruments("ES202512", registry=self.registry)
            if row["instrument_kind"] == "FUTURE_CONTRACT"
        )
        payload = build_futures_product_payload(self.store, contract_id, mode="PAPER")
        margin = payload["exposure"]["margin"]
        self.assertIn(margin["state"], {"AVAILABLE", "MARGIN_MISSING"})

    def test_g14_product_performance_measured(self) -> None:
        contract_id = next(
            row["instrument_id"]
            for row in search_canonical_instruments("ES202512", registry=self.registry)
            if row["instrument_kind"] == "FUTURE_CONTRACT"
        )
        start = time.perf_counter()
        for _ in range(100):
            build_futures_product_payload(self.store, contract_id, mode="PAPER")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 5000)


if __name__ == "__main__":
    unittest.main()
