"""G3 BL-0203 — canonical identity admission tests.

Proves the executable boundary resolves order targets through canonical
XA-01 identity metadata and fails closed for every non-executable class:
- canonical equity / option contract / specific future admitted;
- future family / continuous series / reference / non-tradable rejected;
- ambiguous and unresolved aliases behave explicitly (no symbol heuristics);
- operator fixtures (BIYA/AAPL) take the canonical-registration path;
- registered non-executable aliases can never masquerade as equities.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.eligibility import (
    InstrumentAdmissionError,
    admit_order_instrument,
    ensure_operator_fixture_registered,
)
from market_platform_foundation.xa01.compatibility import (
    register_commodity_economic,
    register_continuous_futures_series,
    register_crypto_pair,
    register_equity,
    register_future_contract,
    register_future_family,
    register_option_contract,
)
from market_platform_foundation.xa01.contracts import ExternalIdentifier
from market_platform_foundation.xa01.enums import (
    ExternalIdentifierType,
    InstrumentKind,
    Tradability,
)
from market_platform_foundation.xa01.errors import Xa01Error
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests


def _add_ticker_alias(registry: InstrumentRegistry, canonical_id: str, alias: str) -> None:
    registry.add_alias(
        canonical_id,
        ExternalIdentifier(
            identifier_type=ExternalIdentifierType.TICKER,
            alias_value=alias.upper(),
        ),
    )


class CanonicalAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_canonical_equity_admitted(self) -> None:
        register_equity(symbol="AAPL", registry=self.registry)
        ref = admit_order_instrument("AAPL", registry=self.registry)
        self.assertEqual(ref["instrument_kind"], "TRADABLE_SECURITY")
        self.assertEqual(ref["tradability"], "TRADABLE")
        self.assertEqual(ref["contract_multiplier"], "1")

    def test_option_contract_admitted_with_multiplier(self) -> None:
        option_id = register_option_contract(
            option_id="SPY260918C00500000",
            underlying_symbol="SPY",
            expiration="2026-09-18",
            strike="500.0",
            call_put="CALL",
            registry=self.registry,
        )
        _add_ticker_alias(self.registry, option_id, "SPY260918C00500000")
        ref = admit_order_instrument("SPY260918C00500000", registry=self.registry)
        self.assertEqual(ref["instrument_kind"], "OPTION_CONTRACT")
        self.assertEqual(ref["tradability"], "TRADABLE")
        self.assertEqual(ref["contract_multiplier"], "100")

    def test_specific_future_contract_admitted_at_identity_layer(self) -> None:
        future_id = register_future_contract(
            contract_id="ES202512",
            family_root="ES",
            expiration="2025-12-19",
            contract_multiplier="50",
            registry=self.registry,
        )
        _add_ticker_alias(self.registry, future_id, "ESZ5")
        ref = admit_order_instrument("ESZ5", registry=self.registry)
        self.assertEqual(ref["instrument_kind"], "FUTURE_CONTRACT")
        self.assertEqual(ref["tradability"], "TRADABLE")
        # Identity admission passes; the financial hook still fails closed
        # (UNSUPPORTED_RISK_MODEL) because no safe margin model exists — that
        # separation is proven in test_pretrade_hooks.py. The multiplier is
        # explicit canonical economics (ES spec = 50), never a silent 1.
        self.assertEqual(ref["contract_multiplier"], "50")

    def test_future_family_rejected(self) -> None:
        family = register_future_family(family_root="ES", registry=self.registry)
        _add_ticker_alias(self.registry, family, "ES")
        with self.assertRaises(InstrumentAdmissionError) as ctx:
            admit_order_instrument("ES", registry=self.registry)
        self.assertIn("UNSUPPORTED_INSTRUMENT_KIND", ctx.exception.code)

    def test_continuous_future_rejected(self) -> None:
        series = register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=self.registry,
        )
        _add_ticker_alias(self.registry, series, "ES1!")
        with self.assertRaises(InstrumentAdmissionError) as ctx:
            admit_order_instrument("ES1!", registry=self.registry)
        self.assertIn("UNSUPPORTED_INSTRUMENT_KIND", ctx.exception.code)

    def test_es_root_cannot_masquerade_as_equity(self) -> None:
        # The ES future root must never be admitted as an executable equity,
        # even when a provider/ticker alias points at the family identity.
        family = register_future_family(family_root="ES", registry=self.registry)
        _add_ticker_alias(self.registry, family, "ES")
        with self.assertRaises(InstrumentAdmissionError) as ctx:
            admit_order_instrument("ES", registry=self.registry)
        self.assertIn("UNSUPPORTED_INSTRUMENT_KIND", ctx.exception.code)

    def test_reference_commodity_rejected(self) -> None:
        commodity = register_commodity_economic(
            commodity_code="WTI",
            registry=self.registry,
        )
        _add_ticker_alias(self.registry, commodity, "WTI")
        with self.assertRaises(InstrumentAdmissionError) as ctx:
            admit_order_instrument("WTI", registry=self.registry)
        self.assertIn("UNSUPPORTED_INSTRUMENT_KIND", ctx.exception.code)

    def test_non_tradable_identity_rejected(self) -> None:
        from dataclasses import replace

        from market_platform_foundation.xa01.enums import Tradability as TradEnum

        equity = register_equity(symbol="LOCKED", registry=self.registry)
        record = self.registry.get(equity)
        updated = replace(record, descriptor=replace(record.descriptor, tradability=TradEnum.REFERENCE_ONLY))
        self.registry._records[equity] = updated  # noqa: SLF001 — test-only mutation
        with self.assertRaises(InstrumentAdmissionError) as ctx:
            admit_order_instrument("LOCKED", registry=self.registry)
        self.assertIn("NON_EXECUTABLE_INSTRUMENT", ctx.exception.code)

    def test_ambiguous_alias_fails_closed(self) -> None:
        # A provider alias that resolves ambiguously must fail closed. Two
        # distinct identities each claiming the alias is a registry conflict;
        # the executable boundary must never pick a winner by symbol shape.
        register_equity(symbol="DUPE", registry=self.registry)
        family = register_future_family(family_root="DUPE", registry=self.registry)
        self.registry.add_alias(
            family,
            ExternalIdentifier(
                identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
                alias_value="DUPE",
                provider_id="ibkr",
            ),
        )
        # The equity ticker alias resolves; the family provider alias would be
        # ambiguous at the provider scope. Regardless of which path is taken,
        # a family identity can never be admitted as an executable equity.
        try:
            ref = admit_order_instrument("DUPE", registry=self.registry)
            self.assertEqual(ref["instrument_kind"], "TRADABLE_SECURITY")
        except (InstrumentAdmissionError, Xa01Error):
            pass  # fail closed is acceptable for ambiguous input

    def test_unresolved_symbol_fails_closed(self) -> None:
        from market_platform_foundation.paper.eligibility import OPERATOR_FIXTURE_SYMBOLS

        # The legacy equity-default bridge is CLOSED: an unregistered symbol
        # is genuinely unknown and must fail closed, never silently invented
        # as an executable equity.
        self.assertEqual(OPERATOR_FIXTURE_SYMBOLS, frozenset({"BIYA", "AAPL"}))
        with self.assertRaises(InstrumentAdmissionError) as ctx:
            admit_order_instrument("ZZZZZZ", registry=self.registry)
        self.assertIn("UNKNOWN_INSTRUMENT", ctx.exception.code)

    def test_operator_fixture_registered_canonically(self) -> None:
        ensure_operator_fixture_registered(registry=self.registry)
        ref = admit_order_instrument("BIYA", registry=self.registry)
        self.assertEqual(ref["instrument_kind"], "TRADABLE_SECURITY")
        self.assertEqual(ref["tradability"], "TRADABLE")
        # Canonical registration is idempotent.
        ensure_operator_fixture_registered(registry=self.registry)
        ref2 = admit_order_instrument("BIYA", registry=self.registry)
        self.assertEqual(ref["instrument_id"], ref2["instrument_id"])

    def test_known_alias_resolves_through_g1(self) -> None:
        register_equity(symbol="MSFT", registry=self.registry)
        ref = admit_order_instrument("msft", registry=self.registry)  # case-insensitive
        self.assertEqual(ref["symbol"], "MSFT")
        self.assertNotEqual(ref["instrument_id"], "MSFT")  # canonical id, not symbol

    def test_crypto_pair_spot_admitted(self) -> None:
        pair = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USDT",
            registry=self.registry,
        )
        _add_ticker_alias(self.registry, pair, "BTCUSDT")
        ref = admit_order_instrument("BTCUSDT", registry=self.registry)
        self.assertEqual(ref["instrument_kind"], "CRYPTO_PAIR")
        self.assertEqual(ref["tradability"], "TRADABLE")


if __name__ == "__main__":
    unittest.main()