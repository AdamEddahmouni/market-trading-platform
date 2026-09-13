"""DoD item 2 — Moomoo OpenD is Primary L1; Yahoo stays a DELAYED overlay.

Covers the three mandated behaviors:
  * No OpenD -> honest unavailable, no generated quotes (never mock).
  * Yahoo overlay stays DELAYED and never impersonates OpenD/real-time/ES.
  * Composition wiring puts OpenD in the primary ``equity_quote`` slot.

The cloud VM cannot reach an operator-machine OpenD daemon, so the
"no OpenD" fail-closed path is exercised unconditionally (no live OpenD
required to prove it). A local loopback TCP listener stands in only for the
*reachability* check (never for a moomoo protocol/tick), proving OpenD is
never mocked as live ticks even when the daemon-level TCP port is open.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import unittest

from market_platform_foundation.providers.adapters.moomoo_opend_equity_quote import (
    MOOMOO_OPEND_PROVIDER_ID,
    MOOMOO_TRANSPORT_NOT_IMPLEMENTED,
    OPEND_NON_LOOPBACK_BLOCKED,
    OPEND_UNAVAILABLE,
    US_EQUITY_L1_CAPABILITY,
    MoomooOpenDEquityQuoteProvider,
    opend_is_loopback,
    opend_reachable,
)
from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (
    ES_SYMBOL_BLOCKED,
    YAHOO_CAPABILITY,
    YAHOO_PROVIDER_ID,
    YahooDelayedEquityQuoteProvider,
    is_es_futures_symbol,
)
from market_platform_foundation.providers.composition import (
    ProviderComposition,
    with_moomoo_opend_primary_quote,
)
from market_platform_foundation.providers.equity_quote_selection import (
    delayed_cloud_overlay_provider,
    opend_readiness,
    primary_equity_quote_provider,
)

_MOOMOO_ENV_NAMES = ("IMP_MOOMOO_HOST", "IMP_MOOMOO_PORT")


@contextlib.contextmanager
def _env(**overrides: str):
    previous = {name: os.environ.get(name) for name in overrides}
    try:
        os.environ.update(overrides)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextlib.contextmanager
def _cleared_moomoo_env():
    previous = {name: os.environ.pop(name, None) for name in _MOOMOO_ENV_NAMES}
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is not None:
                os.environ[name] = value


class MoomooOpenDPrimaryL1Tests(unittest.TestCase):
    """No OpenD -> honest unavailable, no generated quotes."""

    def test_default_identity_is_primary_l1(self) -> None:
        provider = MoomooOpenDEquityQuoteProvider()
        self.assertEqual(provider.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(provider.capability, US_EQUITY_L1_CAPABILITY)
        self.assertEqual(provider.timeliness, "REAL_TIME")

    def test_no_opend_fails_closed_with_no_generated_quotes(self) -> None:
        """Cloud VM has no loopback daemon on the default port — proves fail-closed."""
        with _cleared_moomoo_env():
            provider = MoomooOpenDEquityQuoteProvider()
            result = provider.fetch_quote("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, OPEND_UNAVAILABLE)
        self.assertEqual(result.events, ())
        self.assertEqual(result.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(result.capability, US_EQUITY_L1_CAPABILITY)

    def test_unreachable_arbitrary_port_fails_closed(self) -> None:
        with _env(IMP_MOOMOO_HOST="127.0.0.1", IMP_MOOMOO_PORT="1"):
            result = MoomooOpenDEquityQuoteProvider().fetch_quote("MSFT")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, OPEND_UNAVAILABLE)
        self.assertEqual(result.events, ())

    def test_non_loopback_host_blocked_without_connecting(self) -> None:
        with _env(IMP_MOOMOO_HOST="203.0.113.10", IMP_MOOMOO_PORT="11111"):
            self.assertFalse(opend_is_loopback("203.0.113.10"))
            result = MoomooOpenDEquityQuoteProvider().fetch_quote("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, OPEND_NON_LOOPBACK_BLOCKED)
        self.assertEqual(result.events, ())

    def test_reachable_loopback_still_fails_closed_never_mocks(self) -> None:
        """Even if a local TCP listener answers the port, no tick is fabricated.

        The listener here proves only that this adapter checks *reachability*
        honestly (real TCP connect, not a stubbed boolean) and still refuses
        to synthesize a quote once connected, because the in-tree vendor
        transport is intentionally not implemented.
        """
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        host, port = listener.getsockname()
        try:
            with _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                self.assertTrue(opend_reachable(host=host, port=port))
                result = MoomooOpenDEquityQuoteProvider().fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, MOOMOO_TRANSPORT_NOT_IMPLEMENTED)
        self.assertEqual(result.events, ())

    def test_never_returns_available_status(self) -> None:
        """Property: this adapter has no code path that returns status='available'."""
        with _cleared_moomoo_env():
            unreachable = MoomooOpenDEquityQuoteProvider().fetch_quote("AAPL")
        with _env(IMP_MOOMOO_HOST="198.51.100.7", IMP_MOOMOO_PORT="11111"):
            non_loopback = MoomooOpenDEquityQuoteProvider().fetch_quote("AAPL")
        for result in (unreachable, non_loopback):
            self.assertNotEqual(result.status, "available")


class YahooDelayedOverlayTests(unittest.TestCase):
    """Yahoo overlay stays DELAYED, distinct identity, never ES."""

    def _valid_payload(self) -> dict:
        return {
            "chart": {
                "error": None,
                "result": [
                    {
                        "meta": {
                            "ask": 191.25,
                            "bid": 191.10,
                            "regularMarketPrice": 191.20,
                            "regularMarketTime": 1_800_000_000,
                        },
                        "timestamp": [1_800_000_000],
                    }
                ],
            }
        }

    def test_identity_is_distinct_from_opend(self) -> None:
        yahoo = YahooDelayedEquityQuoteProvider()
        self.assertEqual(yahoo.provider_id, YAHOO_PROVIDER_ID)
        self.assertEqual(yahoo.capability, YAHOO_CAPABILITY)
        self.assertEqual(yahoo.timeliness, "DELAYED")
        self.assertNotEqual(yahoo.provider_id, MOOMOO_OPEND_PROVIDER_ID)

    def test_never_calls_network_in_tests_and_reports_delayed(self) -> None:
        calls: list[str] = []

        def fake_fetch(url: str) -> tuple[int, bytes]:
            calls.append(url)
            return 200, json.dumps(self._valid_payload()).encode("utf-8")

        provider = YahooDelayedEquityQuoteProvider(fetch=fake_fetch)
        result = provider.fetch_quote("AAPL")

        self.assertEqual(result.status, "available")
        self.assertEqual(len(calls), 1)
        self.assertIn("AAPL", calls[0])
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event["timeliness"], "DELAYED")
        self.assertEqual(event["entitlement"], "DELAYED")
        self.assertEqual(event["provider"], YAHOO_PROVIDER_ID)
        self.assertNotEqual(event["provider"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertNotIn("REAL_TIME", str(event.values()))

    def test_rejects_es_futures_symbols_without_any_network_call(self) -> None:
        calls: list[str] = []

        def fake_fetch(url: str) -> tuple[int, bytes]:
            calls.append(url)
            return 200, b"{}"

        provider = YahooDelayedEquityQuoteProvider(fetch=fake_fetch)
        for symbol in ("ES=F", "/ES", "ES1!", "MES", "es=f"):
            with self.subTest(symbol=symbol):
                result = provider.fetch_quote(symbol)
                self.assertEqual(result.status, "unavailable")
                self.assertEqual(result.reason_code, ES_SYMBOL_BLOCKED)
        self.assertEqual(calls, [], "ES-style symbols must fail closed before any HTTP call")

    def test_is_es_futures_symbol_classifier(self) -> None:
        for symbol in ("ES=F", "/es", "MES=F", "ES1!"):
            self.assertTrue(is_es_futures_symbol(symbol), symbol)
        for symbol in ("AAPL", "MSFT", "SPY"):
            self.assertFalse(is_es_futures_symbol(symbol), symbol)

    def test_http_error_fails_closed(self) -> None:
        provider = YahooDelayedEquityQuoteProvider(fetch=lambda url: (500, b""))
        result = provider.fetch_quote("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "PROVIDER_HTTP_ERROR")
        self.assertEqual(result.events, ())

    def test_rate_limit_fails_closed(self) -> None:
        provider = YahooDelayedEquityQuoteProvider(fetch=lambda url: (429, b""))
        result = provider.fetch_quote("AAPL")
        self.assertEqual(result.reason_code, "RATE_LIMIT")

    def test_malformed_json_fails_closed(self) -> None:
        provider = YahooDelayedEquityQuoteProvider(fetch=lambda url: (200, b"not-json"))
        result = provider.fetch_quote("AAPL")
        self.assertEqual(result.reason_code, "MALFORMED_RECORD")

    def test_empty_symbol_required(self) -> None:
        provider = YahooDelayedEquityQuoteProvider(fetch=lambda url: (200, b"{}"))
        result = provider.fetch_quote("   ")
        self.assertEqual(result.reason_code, "INSTRUMENT_ID_REQUIRED")


class EquityQuoteSelectionTests(unittest.TestCase):
    """Selection layer: OpenD is always primary; Yahoo is a distinct overlay."""

    def test_primary_provider_is_moomoo_opend(self) -> None:
        provider = primary_equity_quote_provider()
        self.assertIsInstance(provider, MoomooOpenDEquityQuoteProvider)
        self.assertEqual(provider.provider_id, MOOMOO_OPEND_PROVIDER_ID)

    def test_overlay_provider_is_yahoo_and_distinct(self) -> None:
        overlay = delayed_cloud_overlay_provider()
        self.assertIsInstance(overlay, YahooDelayedEquityQuoteProvider)
        self.assertNotEqual(overlay.provider_id, MOOMOO_OPEND_PROVIDER_ID)

    def test_opend_readiness_reports_unreachable_on_this_vm(self) -> None:
        with _cleared_moomoo_env():
            readiness = opend_readiness()
        self.assertTrue(readiness.loopback)
        self.assertFalse(readiness.reachable)

    def test_readiness_is_diagnostic_and_does_not_change_primary_selection(self) -> None:
        with _cleared_moomoo_env():
            readiness = opend_readiness()
            provider = primary_equity_quote_provider()
        self.assertFalse(readiness.reachable)
        self.assertEqual(provider.provider_id, MOOMOO_OPEND_PROVIDER_ID)


class CompositionWiringTests(unittest.TestCase):
    """`with_moomoo_opend_primary_quote` puts OpenD in the equity_quote slot."""

    def test_wires_opend_into_equity_quote_slot(self) -> None:
        composition = with_moomoo_opend_primary_quote(ProviderComposition())
        self.assertEqual(composition.equity_quote.provider_id, MOOMOO_OPEND_PROVIDER_ID)

    def test_wired_slot_still_fails_closed_without_live_opend(self) -> None:
        composition = with_moomoo_opend_primary_quote(ProviderComposition())
        with _cleared_moomoo_env():
            result = composition.equity_quote.fetch_quote("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, OPEND_UNAVAILABLE)
        self.assertEqual(result.events, ())

    def test_default_composition_unaffected(self) -> None:
        composition = ProviderComposition()
        self.assertEqual(composition.equity_quote.provider_id, "stub.equity_quote.unconfigured")


if __name__ == "__main__":
    unittest.main()
