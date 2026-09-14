"""Alpaca Paper HTTPS comparator — fail-closed, no SDK, live host blocked."""

from __future__ import annotations

import ast
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.runner import (  # noqa: E402
    STATUS_COMPARATOR_NOT_CONFIGURED,
    STATUS_ENVIRONMENT_AMBIGUOUS,
    STATUS_HARNESS_READY,
    STATUS_LIVE_FORBIDDEN,
    STATUS_WAITING_FOR_MARKET,
    alpaca_paper_configured,
    classify_calibration_run,
    run_calibration_campaign,
    tradier_sandbox_configured,
)
from market_platform_foundation.providers.adapters.alpaca_paper import (  # noqa: E402
    ALPACA_PROVIDER_ID,
    AlpacaReplayStore,
    make_alpaca_paper_provider,
)
from market_platform_foundation.providers.adapters.alpaca_paper_http import (  # noqa: E402
    ALPACA_PAPER_ORIGIN,
    AlpacaPaperHttpError,
    AlpacaPaperHttpTransport,
    AlpacaPaperReadOnlyHttpTransport,
    alpaca_http_fetch_account,
    alpaca_http_fetch_clock,
    alpaca_http_fetch_positions,
    alpaca_http_place_order,
    assert_alpaca_paper_readonly_request,
    assert_alpaca_paper_url,
    canonicalize_alpaca_paper_origin,
    normalize_alpaca_wire_order,
    paper_api_url,
)
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_PROVIDER_ID,
)
from market_platform_foundation.providers.adapters.tradier_sandbox_http import (  # noqa: E402
    TradierSandboxHttpError,
    assert_tradier_sandbox_url,
)
from market_platform_foundation.providers.composition import (  # noqa: E402
    ProviderComposition,
    with_alpaca_paper_execution,
    with_broker_paper_execution,
)

T0 = 1_700_000_000_000_000_000
PAPER_ENV = {
    "IMP_ALPACA_PAPER": "1",
    "IMP_BROKER_PAPER_EXECUTION": "1",
    "APCA_API_KEY_ID": "PKTEST",
    "APCA_API_SECRET_KEY": "secret-test",
    "APCA_API_BASE_URL": ALPACA_PAPER_ORIGIN,
    "IMP_ALPACA_PAPER_HTTP": "1",
}


class FakeAlpacaHttp:
    def __init__(self, responses: dict[tuple[str, str], tuple[int, dict]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, *, key_id: str, secret_key: str, json_body=None):
        del key_id, secret_key, json_body
        self.calls.append((method, url))
        if "api.alpaca.markets" in url and "paper-api.alpaca.markets" not in url:
            raise AssertionError("live host must never be contacted")
        key = (method, url)
        if key not in self.responses:
            raise AssertionError(f"unexpected paper call {method} {url}")
        return self.responses[key]


class UrlGuardTests(unittest.TestCase):
    def test_paper_origin_allowed(self) -> None:
        self.assertEqual(
            assert_alpaca_paper_url(f"{ALPACA_PAPER_ORIGIN}/v2/account"),
            f"{ALPACA_PAPER_ORIGIN}/v2/account",
        )
        self.assertEqual(canonicalize_alpaca_paper_origin(None), ALPACA_PAPER_ORIGIN)
        self.assertEqual(canonicalize_alpaca_paper_origin(ALPACA_PAPER_ORIGIN), ALPACA_PAPER_ORIGIN)
        self.assertEqual(
            canonicalize_alpaca_paper_origin(f"{ALPACA_PAPER_ORIGIN}/v2"),
            ALPACA_PAPER_ORIGIN,
        )
        self.assertEqual(paper_api_url(f"{ALPACA_PAPER_ORIGIN}/v2", "v2", "account"), f"{ALPACA_PAPER_ORIGIN}/v2/account")
        self.assertEqual(paper_api_url(ALPACA_PAPER_ORIGIN, "v2", "account"), f"{ALPACA_PAPER_ORIGIN}/v2/account")

    def test_live_host_blocked_before_urlopen(self) -> None:
        with self.assertRaises(AlpacaPaperHttpError) as ctx:
            assert_alpaca_paper_url("https://api.alpaca.markets/v2/account")
        self.assertEqual(str(ctx.exception), "LIVE_FORBIDDEN")
        with self.assertRaises(AlpacaPaperHttpError) as origin_ctx:
            canonicalize_alpaca_paper_origin("https://api.alpaca.markets")
        self.assertEqual(str(origin_ctx.exception), "LIVE_FORBIDDEN")
        transport = AlpacaPaperHttpTransport()
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            with self.assertRaises(AlpacaPaperHttpError) as blocked:
                transport.request(
                    "GET",
                    "https://api.alpaca.markets/v2/account",
                    key_id="x",
                    secret_key="y",
                )
        self.assertEqual(str(blocked.exception), "LIVE_FORBIDDEN")

    def test_other_hosts_forbidden(self) -> None:
        with self.assertRaises(AlpacaPaperHttpError) as ctx:
            assert_alpaca_paper_url("https://sandbox.tradier.com/v1/accounts")
        self.assertEqual(str(ctx.exception), "ALPACA_HOST_FORBIDDEN")
        with self.assertRaises(AlpacaPaperHttpError) as http_ctx:
            assert_alpaca_paper_url("http://paper-api.alpaca.markets/v2/account")
        self.assertEqual(str(http_ctx.exception), "ALPACA_HOST_FORBIDDEN")
        with self.assertRaises(AlpacaPaperHttpError) as spoof_ctx:
            assert_alpaca_paper_url("https://paper-api.alpaca.markets.evil.com/v2/account")
        self.assertEqual(str(spoof_ctx.exception), "ALPACA_HOST_FORBIDDEN")
        with self.assertRaises(AlpacaPaperHttpError) as userinfo_ctx:
            assert_alpaca_paper_url("https://user:pass@api.alpaca.markets/v2/account")
        self.assertEqual(str(userinfo_ctx.exception), "LIVE_FORBIDDEN")

    def test_readonly_request_allows_session_gets_and_refuses_orders(self) -> None:
        for path in ("/v2/account", "/v2/clock", "/v2/positions"):
            url = f"{ALPACA_PAPER_ORIGIN}{path}"
            self.assertEqual(assert_alpaca_paper_readonly_request("GET", url), url)
        with self.assertRaises(AlpacaPaperHttpError) as post_ctx:
            assert_alpaca_paper_readonly_request("POST", f"{ALPACA_PAPER_ORIGIN}/v2/orders")
        self.assertEqual(str(post_ctx.exception), "ALPACA_READONLY_FORBIDDEN")
        with self.assertRaises(AlpacaPaperHttpError) as get_orders_ctx:
            assert_alpaca_paper_readonly_request("GET", f"{ALPACA_PAPER_ORIGIN}/v2/orders")
        self.assertEqual(str(get_orders_ctx.exception), "ALPACA_READONLY_FORBIDDEN")
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            readonly = AlpacaPaperReadOnlyHttpTransport()
            with self.assertRaises(AlpacaPaperHttpError) as live_ctx:
                readonly.request(
                    "GET",
                    "https://api.alpaca.markets/v2/clock",
                    key_id="x",
                    secret_key="y",
                )
        self.assertEqual(str(live_ctx.exception), "LIVE_FORBIDDEN")
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            with self.assertRaises(AlpacaPaperHttpError) as order_ctx:
                AlpacaPaperReadOnlyHttpTransport().request(
                    "POST",
                    f"{ALPACA_PAPER_ORIGIN}/v2/orders",
                    key_id="x",
                    secret_key="y",
                    json_body={"symbol": "AAPL", "qty": "1", "side": "buy", "type": "market"},
                )
        self.assertEqual(str(order_ctx.exception), "ALPACA_READONLY_FORBIDDEN")

    def test_tradier_transport_still_refuses_alpaca_paper_host(self) -> None:
        with self.assertRaises(TradierSandboxHttpError):
            assert_tradier_sandbox_url(f"{ALPACA_PAPER_ORIGIN}/v2/account")


class RunnerFailClosedTests(unittest.TestCase):
    def test_no_keys_is_comparator_not_configured(self) -> None:
        result = run_calibration_campaign(env={}, now_ns=T0)
        self.assertEqual(result.status, STATUS_COMPARATOR_NOT_CONFIGURED)
        self.assertFalse(result.detail["orders_placed"])
        self.assertFalse(result.detail["fabricated_fills"])
        self.assertFalse(result.calibrated)
        self.assertFalse(result.empirical_active)
        self.assertFalse(alpaca_paper_configured({}))

    def test_paper_url_without_keys_stays_not_configured(self) -> None:
        env = {
            "IMP_ALPACA_PAPER": "1",
            "IMP_BROKER_PAPER_EXECUTION": "1",
            "APCA_API_BASE_URL": ALPACA_PAPER_ORIGIN,
        }
        self.assertEqual(
            classify_calibration_run(env=env, now_ns=T0, session_label="REGULAR"),
            STATUS_COMPARATOR_NOT_CONFIGURED,
        )

    def test_live_host_is_live_forbidden(self) -> None:
        env = {
            "APCA_API_BASE_URL": "https://api.alpaca.markets",
            "APCA_API_KEY_ID": "PKLIVE",
            "APCA_API_SECRET_KEY": "secret",
        }
        self.assertEqual(
            classify_calibration_run(env=env, now_ns=T0, requested_mode="PAPER"),
            STATUS_LIVE_FORBIDDEN,
        )

    def test_configured_paper_keys_are_harness_ready(self) -> None:
        self.assertTrue(alpaca_paper_configured(PAPER_ENV))
        self.assertEqual(
            classify_calibration_run(env=PAPER_ENV, now_ns=T0, session_label="REGULAR"),
            STATUS_HARNESS_READY,
        )

    def test_tradier_and_alpaca_xor(self) -> None:
        both = {
            **PAPER_ENV,
            "IMP_TRADIER_PAPER": "1",
            "IMP_TRADIER_TOKEN": "sandbox-test-token",
            "IMP_TRADIER_ENDPOINT": "https://sandbox.tradier.com/v1",
        }
        self.assertTrue(tradier_sandbox_configured(both))
        self.assertTrue(alpaca_paper_configured(both))
        self.assertEqual(
            classify_calibration_run(env=both, now_ns=T0, session_label="REGULAR"),
            STATUS_ENVIRONMENT_AMBIGUOUS,
        )

    def test_live_mode_still_forbidden(self) -> None:
        self.assertEqual(
            classify_calibration_run(env=PAPER_ENV, now_ns=T0, requested_mode="LIVE"),
            STATUS_LIVE_FORBIDDEN,
        )

    def test_pre_rth_utc_now_is_waiting_not_ready(self) -> None:
        # Monday 2026-09-14 12:54 UTC = 08:54 ET premarket. Naive UTC must not
        # be treated as America/New_York (that would false-ready the harness).
        now_ns = int(datetime(2026, 9, 14, 12, 54, 15, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
        result = run_calibration_campaign(env=PAPER_ENV, now_ns=now_ns)
        self.assertEqual(result.status, STATUS_WAITING_FOR_MARKET)
        self.assertNotEqual(result.status, STATUS_HARNESS_READY)
        self.assertFalse(result.calibrated)
        self.assertFalse(result.empirical_active)
        self.assertFalse(result.detail["orders_placed"])
        self.assertEqual(result.pair_count, 0)

    def test_place_orders_flag_cannot_place_or_claim_calibrated(self) -> None:
        result = run_calibration_campaign(
            env=PAPER_ENV,
            now_ns=T0,
            session_label="REGULAR",
            place_orders=True,
        )
        self.assertEqual(result.status, STATUS_HARNESS_READY)
        self.assertFalse(result.detail["orders_placed"])
        self.assertFalse(result.detail["fabricated_fills"])
        self.assertEqual(result.pair_count, 0)
        self.assertFalse(result.calibrated)
        self.assertFalse(result.empirical_active)
        payload = result.to_dict()
        self.assertFalse(payload["calibrated"])
        self.assertFalse(payload["empirical_active"])
        self.assertNotIn("CALIBRATED", payload["status"])
        self.assertNotIn("EMPIRICAL_ACTIVE", json.dumps(payload))


class AdapterTests(unittest.TestCase):
    def test_missing_keys_do_not_place_orders(self) -> None:
        provider = make_alpaca_paper_provider(
            env={
                "IMP_ALPACA_PAPER": "1",
                "IMP_BROKER_PAPER_EXECUTION": "1",
                "APCA_API_BASE_URL": ALPACA_PAPER_ORIGIN,
            },
            replay_store=AlpacaReplayStore(),
        )
        result = provider.place_order(
            {
                "instrument_id": "AAPL",
                "instrument": {"symbol": "AAPL", "instrument_id": "AAPL"},
                "client_order_id": "cli-x",
                "idempotency_key": "key-x",
                "intent_id": "int-x",
                "desired_quantity": 1,
                "created_time": T0,
                "side": "BUY",
                "order_type": "MARKET",
            }
        )
        self.assertEqual(result.reason_code, "COMPARATOR_NOT_CONFIGURED")

    def test_fixture_path_without_http_gate(self) -> None:
        env = dict(PAPER_ENV)
        env.pop("IMP_ALPACA_PAPER_HTTP")
        provider = make_alpaca_paper_provider(env=env, replay_store=AlpacaReplayStore())
        result = provider.fetch_account()
        self.assertEqual(result.reason_code, "BROKER_TRANSPORT_NOT_IMPLEMENTED")

    def test_injected_http_fetch_account(self) -> None:
        account_url = f"{ALPACA_PAPER_ORIGIN}/v2/account"
        fake = FakeAlpacaHttp(
            {
                ("GET", account_url): (
                    200,
                    {"id": "paper-acct", "cash": "100000.00", "buying_power": "200000.00", "status": "ACTIVE"},
                )
            }
        )
        provider = make_alpaca_paper_provider(
            env=PAPER_ENV,
            replay_store=AlpacaReplayStore(),
            http_transport=fake,
        )
        result = provider.fetch_account()
        self.assertEqual(result.status, "ok")
        self.assertEqual(fake.calls, [("GET", account_url)])

    def test_normalize_wire_order(self) -> None:
        record = normalize_alpaca_wire_order(
            {
                "id": "abc",
                "status": "filled",
                "symbol": "AAPL",
                "filled_avg_price": "10.50",
                "filled_qty": "2",
            },
            receive_time_ns=T0,
            instrument_id="AAPL",
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["status"], "filled")
        self.assertEqual(record["avg_fill_price_minor"], 1050)
        self.assertEqual(record["filled_quantity"], 2)

    def test_direct_fetch_account_helper(self) -> None:
        fake = FakeAlpacaHttp(
            {
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/account"): (
                    200,
                    {"id": "acct", "cash": "1.00", "buying_power": "2.00"},
                )
            }
        )
        account = alpaca_http_fetch_account(
            fake, origin=ALPACA_PAPER_ORIGIN, key_id="PK", secret_key="SK"
        )
        self.assertIsNotNone(account)
        assert account is not None
        self.assertEqual(account["account_id"], "acct")
        self.assertEqual(account["cash_minor"], 100)

    def test_readonly_transport_fetches_clock_and_positions(self) -> None:
        fake = FakeAlpacaHttp(
            {
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/clock"): (
                    200,
                    {
                        "is_open": True,
                        "timestamp": "2026-09-14T09:40:00-04:00",
                        "next_open": "2026-09-15T09:30:00-04:00",
                        "next_close": "2026-09-14T16:00:00-04:00",
                    },
                ),
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/positions"): (200, []),
            }
        )
        readonly = AlpacaPaperReadOnlyHttpTransport(inner=fake)
        clock = alpaca_http_fetch_clock(
            readonly, origin=ALPACA_PAPER_ORIGIN, key_id="PK", secret_key="SK"
        )
        positions = alpaca_http_fetch_positions(
            readonly, origin=ALPACA_PAPER_ORIGIN, key_id="PK", secret_key="SK"
        )
        self.assertIsNotNone(clock)
        assert clock is not None
        self.assertTrue(clock["is_open"])
        self.assertEqual(clock["next_close"], "2026-09-14T16:00:00-04:00")
        self.assertIsNotNone(positions)
        assert positions is not None
        self.assertEqual(positions["positions"], [])
        self.assertEqual(
            fake.calls,
            [
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/clock"),
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/positions"),
            ],
        )

    def test_readonly_transport_blocks_place_order_helper(self) -> None:
        class BoomInner:
            def request(self, method, url, *, key_id, secret_key, json_body=None):
                raise AssertionError(f"inner must not run {method} {url}")

        request = mock.Mock(
            order_type="MARKET",
            side="BUY",
            broker_symbol="AAPL",
            quantity=1,
            client_order_id="cli-readonly",
            limit_price_minor=None,
        )
        with self.assertRaises(AlpacaPaperHttpError) as ctx:
            alpaca_http_place_order(
                AlpacaPaperReadOnlyHttpTransport(inner=BoomInner()),
                origin=ALPACA_PAPER_ORIGIN,
                key_id="PK",
                secret_key="SK",
                request=request,
                instrument_id="AAPL",
            )
        self.assertEqual(str(ctx.exception), "ALPACA_READONLY_FORBIDDEN")


class CompositionXorTests(unittest.TestCase):
    def test_tradier_and_alpaca_never_coactive(self) -> None:
        composition = ProviderComposition()
        with_broker_paper_execution(composition, env={}, symbol_map={})
        self.assertEqual(composition.paper_execution.provider_id, TRADIER_PROVIDER_ID)
        with self.assertRaises(ValueError) as ctx:
            with_alpaca_paper_execution(composition, env=dict(PAPER_ENV))
        self.assertIn("PAPER_EXECUTION_PROVIDER_CONFLICT", str(ctx.exception))
        alpaca = ProviderComposition()
        with_alpaca_paper_execution(alpaca, env=dict(PAPER_ENV))
        self.assertEqual(alpaca.paper_execution.provider_id, ALPACA_PROVIDER_ID)
        with self.assertRaises(ValueError):
            with_broker_paper_execution(alpaca, env={}, symbol_map={})


class SdkProhibitionTests(unittest.TestCase):
    def test_adapter_modules_do_not_import_alpaca_sdk(self) -> None:
        adapters = Path(__file__).resolve().parents[2] / "src" / "market_platform_foundation" / "providers" / "adapters"
        for path in (adapters / "alpaca_paper.py", adapters / "alpaca_paper_http.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotEqual(alias.name.split(".", 1)[0], "alpaca")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotEqual(node.module.split(".", 1)[0], "alpaca")

    def test_probe_module_never_imports_order_helpers(self) -> None:
        path = Path(__file__).resolve().parents[2] / "tools" / "providers" / "probe_alpaca_paper.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "alpaca_paper_http" in node.module:
                imported.update(alias.name for alias in node.names)
        self.assertIn("AlpacaPaperReadOnlyHttpTransport", imported)
        self.assertIn("alpaca_http_fetch_account", imported)
        self.assertIn("alpaca_http_fetch_clock", imported)
        self.assertIn("alpaca_http_fetch_positions", imported)
        self.assertNotIn("alpaca_http_place_order", imported)
        self.assertNotIn("alpaca_http_cancel_order", imported)
        self.assertNotIn("AlpacaPaperHttpTransport", imported)
        self.assertNotRegex(source, r'(?m)^[^#\n]*["\']https://api\.alpaca\.markets')


class ProbeTests(unittest.TestCase):
    def test_probe_without_keys_exits_not_configured(self) -> None:
        from tools.providers.probe_alpaca_paper import EXIT_NOT_CONFIGURED, main

        with mock.patch("tools.providers.probe_alpaca_paper.load_keys", return_value=("", "")):
            with mock.patch("tools.providers.probe_alpaca_paper.load_private_values", return_value={}):
                code = main([])
        self.assertEqual(code, EXIT_NOT_CONFIGURED)

    def test_probe_env_file_dummy_keys_do_not_print_secrets(self) -> None:
        from tools.providers.probe_alpaca_paper import EXIT_NETWORK, main

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alpaca-paper.env"
            path.write_text(
                "APCA_API_KEY_ID=PKTESTDUMMY\n"
                "APCA_API_SECRET_KEY=not-a-real-secret\n"
                "APCA_API_BASE_URL=https://paper-api.alpaca.markets\n",
                encoding="utf-8",
            )
            isolated = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("APCA_", "ALPACA_", "IMP_ALPACA"))
            }
            with mock.patch.dict(os.environ, isolated, clear=True):
                with mock.patch(
                    "tools.providers.probe_alpaca_paper.alpaca_http_fetch_account",
                    side_effect=AlpacaPaperHttpError("ALPACA_PAPER_NETWORK:refused"),
                ):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as buf:
                        code = main(["--env-file", str(path)])
                        text = buf.getvalue()
        self.assertEqual(code, EXIT_NETWORK)
        self.assertIn('"APCA_API_KEY_ID": true', text)
        self.assertNotIn("PKTESTDUMMY", text)
        self.assertNotIn("not-a-real-secret", text)

    def test_probe_live_endpoint_is_forbidden_before_urlopen(self) -> None:
        from tools.providers.probe_alpaca_paper import EXIT_LIVE_FORBIDDEN, main

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alpaca-paper.env"
            path.write_text(
                "APCA_API_KEY_ID=PKTESTDUMMY\n"
                "APCA_API_SECRET_KEY=not-a-real-secret\n"
                "APCA_API_BASE_URL=https://paper-api.alpaca.markets\n",
                encoding="utf-8",
            )
            isolated = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("APCA_", "ALPACA_", "IMP_ALPACA"))
            }
            with mock.patch.dict(os.environ, isolated, clear=True):
                with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as buf:
                        code = main(
                            ["--env-file", str(path), "--endpoint", "https://api.alpaca.markets"]
                        )
                        text = buf.getvalue()
        self.assertEqual(code, EXIT_LIVE_FORBIDDEN)
        self.assertIn("LIVE_FORBIDDEN", text)
        self.assertIn("orders_placed=false", text)
        self.assertIn("fabricated_fills=false", text)
        self.assertNotIn("PKTESTDUMMY", text)
        self.assertNotIn("not-a-real-secret", text)
        self.assertNotIn("PROBE_PASSED", text)
        self.assertNotIn("CALIBRATED", text)

    def test_probe_success_is_get_only_session_paths(self) -> None:
        from tools.providers.probe_alpaca_paper import EXIT_OK, main

        fake = FakeAlpacaHttp(
            {
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/account"): (
                    200,
                    {"id": "paper-acct", "cash": "100000.00", "buying_power": "200000.00", "status": "ACTIVE"},
                ),
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/clock"): (
                    200,
                    {
                        "is_open": False,
                        "timestamp": "t",
                        "next_open": "2026-09-14T09:30:00-04:00",
                        "next_close": "2026-09-14T16:00:00-04:00",
                    },
                ),
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/positions"): (200, []),
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alpaca-paper.env"
            path.write_text(
                "APCA_API_KEY_ID=PKTESTDUMMY\n"
                "APCA_API_SECRET_KEY=not-a-real-secret\n"
                "APCA_API_BASE_URL=https://paper-api.alpaca.markets\n",
                encoding="utf-8",
            )
            isolated = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("APCA_", "ALPACA_", "IMP_ALPACA"))
            }
            with mock.patch.dict(os.environ, isolated, clear=True):
                with mock.patch(
                    "tools.providers.probe_alpaca_paper.AlpacaPaperReadOnlyHttpTransport",
                    return_value=AlpacaPaperReadOnlyHttpTransport(inner=fake),
                ):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as buf:
                        code = main(["--env-file", str(path)])
                        text = buf.getvalue()
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(
            fake.calls,
            [
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/account"),
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/clock"),
                ("GET", f"{ALPACA_PAPER_ORIGIN}/v2/positions"),
            ],
        )
        self.assertIn("clock_is_open=false", text)
        self.assertIn("positions_count=0", text)
        self.assertIn("orders_placed=false", text)
        self.assertIn("fabricated_fills=false", text)
        self.assertNotIn("PKTESTDUMMY", text)
        self.assertNotIn("CALIBRATED", text)
        self.assertNotIn("EMPIRICAL_ACTIVE", text)

    def test_harness_cli_ignores_place_sandbox_orders(self) -> None:
        from tools.providers.run_calibration_harness import main

        clean = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("IMP_", "APCA_", "ALPACA_"))
        }
        with mock.patch.dict(os.environ, clean, clear=True):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as buf:
                code = main(["--place-sandbox-orders"])
                payload = json.loads(buf.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], STATUS_COMPARATOR_NOT_CONFIGURED)
        self.assertFalse(payload["calibrated"])
        self.assertFalse(payload["empirical_active"])
        self.assertFalse(payload["detail"]["orders_placed"])
        self.assertFalse(payload["detail"]["fabricated_fills"])
        self.assertEqual(payload["pair_count"], 0)


if __name__ == "__main__":
    unittest.main()
