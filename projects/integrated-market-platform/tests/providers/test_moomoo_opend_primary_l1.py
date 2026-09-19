"""DoD item 2 — Moomoo OpenD is Primary L1; Yahoo stays a DELAYED overlay.

Covers the mandated behaviors:
  * No OpenD -> honest unavailable, no generated quotes (never mock).
  * Reachable loopback without vendor SDK -> ``MOOMOO_SDK_MISSING``.
  * Injected vendor failures (auth / protocol / missing last_price) fail closed.
  * Yahoo overlay stays DELAYED and never impersonates OpenD/real-time/ES.
  * Composition wiring puts OpenD in the primary ``equity_quote`` slot.

The cloud VM cannot reach an operator-machine OpenD daemon, so the
"no OpenD" fail-closed path is exercised unconditionally. A local loopback
TCP listener stands in only for the *reachability* check (never for a moomoo
protocol/tick). Mapping an injected vendor row is a contract test — not an
empirical tick and not FTEP evidence.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import sys
import unittest
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from market_platform_foundation.providers.adapters.moomoo_opend_equity_quote import (
    MISSING_TIMESTAMP,
    MOOMOO_AUTH_FAILURE,
    MOOMOO_LAST_PRICE_MISSING,
    MOOMOO_OPEND_PROVIDER_ID,
    MOOMOO_PROTOCOL_ERROR,
    MOOMOO_SDK_MISSING,
    MOOMOO_TRANSPORT_NOT_IMPLEMENTED,
    OPEND_NON_LOOPBACK_BLOCKED,
    OPEND_UNAVAILABLE,
    SYMBOL_REQUIRED,
    US_EQUITY_L1_CAPABILITY,
    MoomooOpenDEquityQuoteProvider,
    OpenDSnapshotResult,
    opend_is_loopback,
    opend_reachable,
    opend_sdk_available,
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
from market_platform_foundation.providers.equity_quote_discovery import discover_equity_quote_stack
from market_platform_foundation.providers.equity_quote_selection import (
    delayed_cloud_overlay_provider,
    opend_readiness,
    primary_equity_quote_provider,
)
from tests.support.hermetic_environment import (
    cleared_moomoo_endpoint_env,
    unreachable_opend_env,
    vendor_sdk_absent,
)

_MOOMOO_ENV_NAMES = ("IMP_MOOMOO_HOST", "IMP_MOOMOO_PORT")
_ADAPTER_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src/market_platform_foundation/providers/adapters/moomoo_opend_equity_quote.py"
)
_TOOLS_TRANSPORT = Path(__file__).resolve().parents[2] / "tools/moomoo/opend_quote_transport.py"


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
    """Legacy name — forces unreachable loopback OpenD, not the live collector port."""

    with cleared_moomoo_endpoint_env():
        yield


class _ScriptedOpenDTransport:
    def __init__(self, result: OpenDSnapshotResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str, int]] = []

    def fetch_snapshot(self, *, symbol: str, host: str, port: int) -> OpenDSnapshotResult:
        self.calls.append((symbol, host, port))
        return self.result


class _FakeQuoteContext:
    def __init__(
        self,
        *,
        state_ret: int = 0,
        state: dict[str, Any] | None = None,
        snap_ret: int = 0,
        snap_data: Any = None,
        explode: str | None = None,
    ) -> None:
        self._state_ret = state_ret
        self._state = state if state is not None else {"qot_logined": True}
        self._snap_ret = snap_ret
        self._snap_data = snap_data
        self._explode = explode
        self.closed = False

    def get_global_state(self) -> tuple[int, Any]:
        if self._explode == "state":
            raise RuntimeError("opend handshake failed")
        return self._state_ret, self._state

    def get_market_snapshot(self, codes: list[str]) -> tuple[int, Any]:
        if self._explode == "snapshot":
            raise RuntimeError("opend snapshot failed")
        if callable(self._snap_data):
            return self._snap_ret, self._snap_data(codes)
        return self._snap_ret, self._snap_data

    def close(self) -> None:
        self.closed = True


class _FakeMoomooSdk:
    RET_OK = 0

    def __init__(self, context: _FakeQuoteContext) -> None:
        self._context = context
        self.OpenQuoteContext = lambda **_kwargs: context


def _vendor_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "code": "US.AAPL",
        "last_price": 187.63,
        "update_time": "2026-09-12 15:59:00.000",
        "bid_price": 187.60,
        "ask_price": 187.65,
        "bid_vol": 100,
        "ask_vol": 200,
    }
    row.update(overrides)
    return row


class MoomooOpenDPrimaryL1Tests(unittest.TestCase):
    """No OpenD -> honest unavailable, no generated quotes."""

    def test_default_identity_is_primary_l1(self) -> None:
        provider = MoomooOpenDEquityQuoteProvider()
        self.assertEqual(provider.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(provider.capability, US_EQUITY_L1_CAPABILITY)
        self.assertEqual(provider.timeliness, "REAL_TIME")

    def test_adapter_source_never_imports_vendor_sdk_or_trade_apis(self) -> None:
        source = _ADAPTER_SOURCE.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^\s*import moomoo\b")
        self.assertNotRegex(source, r"(?m)^\s*from moomoo\b")
        self.assertNotRegex(source, r"(?m)^\s*import futu\b")
        self.assertNotRegex(source, r"(?m)^\s*from futu\b")
        self.assertNotIn("OpenTradeContext", source)
        self.assertNotIn("unlock_trade", source)

    def test_empty_symbol_fails_closed_before_opend(self) -> None:
        result = MoomooOpenDEquityQuoteProvider().fetch_quote("   ")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, SYMBOL_REQUIRED)
        self.assertEqual(result.events, ())

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

    def test_reachable_loopback_without_sdk_fails_closed_never_mocks(self) -> None:
        """TCP listener proves reachability; missing vendor SDK still yields no tick."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        host, port = listener.getsockname()
        try:
            with vendor_sdk_absent(), _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                self.assertTrue(opend_reachable(host=host, port=port))
                result = MoomooOpenDEquityQuoteProvider().fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, MOOMOO_SDK_MISSING)
        self.assertEqual(result.events, ())

    def test_tools_module_missing_still_fail_closed(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        host, port = listener.getsockname()
        try:
            with _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(transport=_ScriptedOpenDTransport(
                    OpenDSnapshotResult(reason_code=MOOMOO_TRANSPORT_NOT_IMPLEMENTED)
                )).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, MOOMOO_TRANSPORT_NOT_IMPLEMENTED)
        self.assertEqual(result.events, ())

    def test_auth_failure_fails_closed(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        host, port = listener.getsockname()
        try:
            with _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(
                        OpenDSnapshotResult(reason_code=MOOMOO_AUTH_FAILURE)
                    )
                ).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, MOOMOO_AUTH_FAILURE)
        self.assertEqual(result.events, ())

    def test_protocol_error_fails_closed(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        host, port = listener.getsockname()
        try:
            with _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(
                        OpenDSnapshotResult(reason_code=MOOMOO_PROTOCOL_ERROR)
                    )
                ).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, MOOMOO_PROTOCOL_ERROR)
        self.assertEqual(result.events, ())

    def test_vendor_row_without_last_price_never_synthesizes(self) -> None:
        row = _vendor_row()
        row.pop("last_price")
        row["bid_price"] = 191.0
        row["ask_price"] = 191.2
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        host, port = listener.getsockname()
        try:
            with _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(OpenDSnapshotResult(row=row))
                ).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, MOOMOO_LAST_PRICE_MISSING)
        self.assertEqual(result.events, ())

    def test_vendor_row_without_timestamp_fails_closed(self) -> None:
        row = _vendor_row()
        row.pop("update_time")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        host, port = listener.getsockname()
        try:
            with _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(OpenDSnapshotResult(row=row))
                ).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, MISSING_TIMESTAMP)
        self.assertEqual(result.events, ())

    def test_injected_vendor_row_maps_last_price_without_synthesis(self) -> None:
        """Contract mapping only — not an empirical OpenD tick."""
        row = _vendor_row(last_price=187.63)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        host, port = listener.getsockname()
        try:
            with _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(OpenDSnapshotResult(row=row))
                ).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.status, "available")
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event["raw_payload"]["last_price"], 187.63)
        self.assertEqual(event["provider"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(event["capability"], US_EQUITY_L1_CAPABILITY)
        self.assertEqual(event["timeliness"], "REAL_TIME")
        self.assertNotIn("yahoo", str(event).lower())

    def test_unreachable_does_not_call_transport(self) -> None:
        transport = _ScriptedOpenDTransport(
            OpenDSnapshotResult(row=_vendor_row())
        )
        with _env(IMP_MOOMOO_HOST="127.0.0.1", IMP_MOOMOO_PORT="1"):
            result = MoomooOpenDEquityQuoteProvider(transport=transport).fetch_quote("AAPL")
        self.assertEqual(result.reason_code, OPEND_UNAVAILABLE)
        self.assertEqual(transport.calls, [])

    def test_no_opend_never_returns_available(self) -> None:
        with _cleared_moomoo_env():
            unreachable = MoomooOpenDEquityQuoteProvider().fetch_quote("AAPL")
        with _env(IMP_MOOMOO_HOST="198.51.100.7", IMP_MOOMOO_PORT="11111"):
            non_loopback = MoomooOpenDEquityQuoteProvider().fetch_quote("AAPL")
        for result in (unreachable, non_loopback):
            self.assertNotEqual(result.status, "available")
            self.assertEqual(result.events, ())


class OpenDVendorTransportTests(unittest.TestCase):
    """Vendor SDK wrapper fail-closed paths. Fake SDK is not an empirical tick."""

    def test_tools_source_has_no_trade_apis(self) -> None:
        source = _TOOLS_TRANSPORT.read_text(encoding="utf-8")
        self.assertNotIn("OpenTradeContext", source)
        self.assertNotIn("unlock_trade", source)
        self.assertNotIn("place_order", source)

    def test_sdk_missing_without_fake(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_snapshot

        with vendor_sdk_absent():
            payload = fetch_snapshot("AAPL", host="127.0.0.1", port=1)
        self.assertEqual(payload["reason_code"], MOOMOO_SDK_MISSING)
        self.assertIsNone(payload["row"])

    def test_tools_dir_on_sys_path_is_not_vendor_sdk(self) -> None:
        """``tools/moomoo`` is not a top-level vendor package (no ``__init__.py``)."""
        from tools.moomoo import opend_quote_transport as transport

        from types import ModuleType

        self.assertFalse((_ROOT / "tools" / "moomoo" / "__init__.py").is_file())
        shadow = ModuleType("shadow_moomoo")
        self.assertFalse(transport.is_vendor_sdk(shadow))
        with vendor_sdk_absent():
            payload = transport.fetch_snapshot("AAPL", host="127.0.0.1", port=1)
        self.assertEqual(payload["reason_code"], MOOMOO_SDK_MISSING)
        self.assertIsNone(payload["row"])

    def test_non_loopback_blocked_even_with_fake_sdk(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_snapshot

        ctx = _FakeQuoteContext(snap_data=[_vendor_row()])
        payload = fetch_snapshot("AAPL", host="203.0.113.10", port=11111, sdk=_FakeMoomooSdk(ctx))
        self.assertEqual(payload["reason_code"], OPEND_NON_LOOPBACK_BLOCKED)
        self.assertIsNone(payload["row"])

    def test_auth_failure_from_qot_not_logined(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_snapshot

        ctx = _FakeQuoteContext(state={"qot_logined": False}, snap_data=[_vendor_row()])
        payload = fetch_snapshot("AAPL", host="127.0.0.1", port=11111, sdk=_FakeMoomooSdk(ctx))
        self.assertEqual(payload["reason_code"], MOOMOO_AUTH_FAILURE)
        self.assertIsNone(payload["row"])
        self.assertTrue(ctx.closed)

    def test_protocol_error_from_snapshot_ret(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_snapshot

        ctx = _FakeQuoteContext(snap_ret=-1, snap_data="handshake corrupt")
        payload = fetch_snapshot("AAPL", host="127.0.0.1", port=11111, sdk=_FakeMoomooSdk(ctx))
        self.assertEqual(payload["reason_code"], MOOMOO_PROTOCOL_ERROR)
        self.assertIsNone(payload["row"])

    def test_protocol_error_from_exception(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_snapshot

        ctx = _FakeQuoteContext(explode="snapshot")
        payload = fetch_snapshot("AAPL", host="127.0.0.1", port=11111, sdk=_FakeMoomooSdk(ctx))
        self.assertEqual(payload["reason_code"], MOOMOO_PROTOCOL_ERROR)
        self.assertIsNone(payload["row"])
        self.assertTrue(ctx.closed)

    def test_missing_last_price_not_filled_from_bid_ask(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_snapshot

        row = _vendor_row()
        row.pop("last_price")
        ctx = _FakeQuoteContext(snap_data=[row])
        payload = fetch_snapshot("AAPL", host="127.0.0.1", port=11111, sdk=_FakeMoomooSdk(ctx))
        self.assertEqual(payload["reason_code"], MOOMOO_LAST_PRICE_MISSING)
        self.assertIsNone(payload["row"])

    def test_vendor_row_copied_not_synthesized(self) -> None:
        """Fake SDK mapping — not an empirical OpenD observation."""
        from tools.moomoo.opend_quote_transport import fetch_snapshot

        ctx = _FakeQuoteContext(snap_data=[_vendor_row(last_price=187.63)])
        payload = fetch_snapshot("AAPL", host="127.0.0.1", port=11111, sdk=_FakeMoomooSdk(ctx))
        self.assertIsNone(payload["reason_code"])
        assert payload["row"] is not None
        self.assertEqual(payload["row"]["last_price"], 187.63)


class OpenDDiscoveryTests(unittest.TestCase):
    def test_discovery_unreachable_is_opend_unavailable(self) -> None:
        with _env(IMP_MOOMOO_HOST="127.0.0.1", IMP_MOOMOO_PORT="1"):
            _provider, discovery = discover_equity_quote_stack()
        self.assertEqual(discovery.reason_code, OPEND_UNAVAILABLE)
        self.assertFalse(discovery.opend_reachable)
        self.assertEqual(discovery.provider_id, MOOMOO_OPEND_PROVIDER_ID)

    def test_discovery_reachable_without_sdk_is_sdk_missing(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(32)
        host, port = listener.getsockname()
        try:
            with vendor_sdk_absent(), _env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                _provider, discovery = discover_equity_quote_stack()
        finally:
            listener.close()
        self.assertTrue(discovery.opend_reachable)
        self.assertEqual(discovery.reason_code, MOOMOO_SDK_MISSING)
        self.assertEqual(discovery.classification, "CONFIGURED_BLOCKED")
        self.assertEqual(discovery.overlay_provider_id, YAHOO_PROVIDER_ID)


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

    def test_empty_payload_fails_closed(self) -> None:
        provider = YahooDelayedEquityQuoteProvider(fetch=lambda url: (200, b""))
        result = provider.fetch_quote("AAPL")
        self.assertEqual(result.reason_code, "EMPTY_PAYLOAD")
        self.assertEqual(result.events, ())

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

    def test_opend_readiness_reports_unreachable_when_injected_closed(self) -> None:
        with unreachable_opend_env():
            readiness = opend_readiness()
        self.assertTrue(readiness.loopback)
        self.assertFalse(readiness.reachable)

    def test_readiness_is_diagnostic_and_does_not_change_primary_selection(self) -> None:
        with unreachable_opend_env():
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
        with unreachable_opend_env():
            result = composition.equity_quote.fetch_quote("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, OPEND_UNAVAILABLE)
        self.assertEqual(result.events, ())

    def test_default_composition_unaffected(self) -> None:
        composition = ProviderComposition()
        self.assertEqual(composition.equity_quote.provider_id, "stub.equity_quote.unconfigured")


if __name__ == "__main__":
    unittest.main()
