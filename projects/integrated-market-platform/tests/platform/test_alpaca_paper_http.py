"""Alpaca Paper HTTPS comparator — fail-closed, no SDK, live host blocked."""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.runner import (  # noqa: E402
    STATUS_COMPARATOR_NOT_CONFIGURED,
    STATUS_ENVIRONMENT_AMBIGUOUS,
    STATUS_HARNESS_READY,
    STATUS_LIVE_FORBIDDEN,
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
    alpaca_http_fetch_account,
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
            with mock.patch(
                "tools.providers.probe_alpaca_paper.alpaca_http_fetch_account",
                side_effect=AlpacaPaperHttpError("ALPACA_PAPER_NETWORK:refused"),
            ):
                with mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as buf:
                    code = main(["--env-file", str(path)])
                    text = buf.getvalue()
        self.assertEqual(code, EXIT_NETWORK)
        self.assertIn('"APCA_API_KEY_ID": true', text)
        self.assertNotIn("PKTESTDUMMY", text)
        self.assertNotIn("not-a-real-secret", text)


if __name__ == "__main__":
    unittest.main()
