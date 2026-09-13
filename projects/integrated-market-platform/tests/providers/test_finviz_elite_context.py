"""Finviz Elite fail-closed context overlay — not L1, not a comparator."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.finviz.news import parse_news_csv
from market_platform_foundation.finviz.screener import parse_screener_csv
from market_platform_foundation.providers.adapters.finviz_elite_context import (
    FINVIZ_CONTEXT_PROVIDER_ID,
    FINVIZ_CONTEXT_TIMELINESS,
    FinvizEliteContextProvider,
)
from market_platform_foundation.providers.composition import (
    ProviderComposition,
    with_finviz_elite_context,
)
from market_platform_foundation.providers.contracts import PROVIDER_UNAVAILABLE
from market_platform_foundation.finviz.credential_manager import (  # noqa: E402
    reset_finviz_credential_manager,
)
from market_platform_foundation.finviz.secure_store import (  # noqa: E402
    write_login_credentials,
)
from market_platform_foundation.providers.finviz_context_discovery import (
    FINVIZ_LOGIN_NAMES,
    FINVIZ_TOKEN_NAMES,
    discover_finviz_context_stack,
    run_finviz_context_overlay,
    token_names_present,
)

FIXTURES = ROOT / "tests" / "fixtures" / "finviz"
TEST_TOKEN = "test-token-not-a-secret"
FETCHED_TOKEN = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
LOGIN_PASSWORD = "not-a-real-password"


class _FakeScreener:
    def __init__(self) -> None:
        self.calls = 0
        text = (FIXTURES / "screener_sample.csv").read_text(encoding="utf-8")
        rows, _, err = parse_screener_csv(text)
        if err:
            raise AssertionError(err)
        self._rows = {row.ticker: row for row in rows}

    def fetch_symbol(self, symbol: str, *, force: bool = False) -> dict[str, Any]:
        del force
        self.calls += 1
        row = self._rows.get(symbol.strip().upper())
        if row is None:
            return {"success": False, "error": "FINVIZ_SYMBOL_NOT_IN_EXPORT", "row": None}
        return {"success": True, "error": None, "row": row}


class _FakeNews:
    def __init__(self) -> None:
        self.calls = 0
        text = (FIXTURES / "news_sample.csv").read_text(encoding="utf-8")
        items, err = parse_news_csv(text)
        if err:
            raise AssertionError(err)
        self._items = items

    def fetch_news(self, *, force: bool = False) -> dict[str, Any]:
        del force
        self.calls += 1
        return {"success": True, "error": None, "items": list(self._items)}

    def news_for_symbol(self, symbol: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        needle = symbol.strip().upper()
        return [item for item in items if needle in item.get("tickers", [])]


def _absent_env() -> dict[str, str]:
    env = {name: "" for name in FINVIZ_TOKEN_NAMES}
    for name in FINVIZ_LOGIN_NAMES:
        env[name] = ""
    return env


def _token_env(*, live: bool = False) -> dict[str, str]:
    env = _absent_env()
    env["FINVIZ_API_KEY"] = TEST_TOKEN
    if live:
        env["IMP_FINVIZ_LIVE"] = "1"
    return env


class FinvizContextDiscoveryTests(unittest.TestCase):
    def test_token_absent_is_not_configured(self) -> None:
        provider, discovery = discover_finviz_context_stack(env=_absent_env())
        self.assertIsInstance(provider, FinvizEliteContextProvider)
        self.assertEqual(provider.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
        self.assertEqual(discovery.classification, "NOT_CONFIGURED")
        self.assertEqual(discovery.reason_code, "NOT_CONFIGURED")
        self.assertEqual(discovery.timeliness, "DELAYED")
        self.assertNotEqual(discovery.timeliness, "REAL_TIME")
        self.assertEqual(discovery.role, "CONTEXT")
        self.assertFalse(discovery.is_l1)
        self.assertFalse(discovery.is_paper_comparator)
        self.assertEqual(discovery.token_names_present, ())

    def test_absent_overlay_never_uses_yahoo_identity(self) -> None:
        payload = run_finviz_context_overlay("AAPL", env=_absent_env())
        self.assertEqual(payload["discovery"]["provider_id"], FINVIZ_CONTEXT_PROVIDER_ID)
        self.assertEqual(payload["result"]["status"], "unavailable")
        self.assertEqual(payload["result"]["reason_code"], "NOT_CONFIGURED")
        dumped = json.dumps(payload)
        self.assertNotIn("yahoo", dumped.lower())
        self.assertNotIn(TEST_TOKEN, dumped)

    def test_placeholder_token_is_absent(self) -> None:
        env = _absent_env()
        env["FINVIZ_API_KEY"] = "CHANGEME"
        _, discovery = discover_finviz_context_stack(env=env)
        self.assertEqual(discovery.classification, "NOT_CONFIGURED")
        self.assertEqual(discovery.token_names_present, ())

    def test_token_present_live_off_is_configured_blocked(self) -> None:
        provider, discovery = discover_finviz_context_stack(env=_token_env())
        self.assertIs(type(provider), FinvizEliteContextProvider)
        self.assertEqual(discovery.classification, "CONFIGURED_BLOCKED")
        self.assertEqual(discovery.reason_code, "LIVE_DISABLED")
        result = provider.fetch_context("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "LIVE_DISABLED")
        self.assertEqual(result.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)

    def test_token_present_uses_injected_adapter_path(self) -> None:
        screener = _FakeScreener()
        news = _FakeNews()
        factory_calls: list[str] = []

        def boom(_token: str) -> tuple[Any, Any]:
            factory_calls.append("called")
            raise AssertionError("paid Finviz HTTP must not run in tests")

        provider = FinvizEliteContextProvider(
            env=_token_env(),
            screener=screener,
            news_client=news,
            client_factory=boom,
        )
        _, discovery = discover_finviz_context_stack(env=_token_env(), provider=provider)
        self.assertEqual(discovery.classification, "CONFIGURED")
        result = provider.fetch_context("AAPL")
        self.assertEqual(result.status, "available")
        self.assertEqual(result.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
        self.assertEqual(result.capability, "equity_context")
        self.assertEqual(screener.calls, 1)
        self.assertEqual(news.calls, 1)
        self.assertEqual(factory_calls, [])
        event = result.events[0]
        self.assertEqual(event["timeliness"], "DELAYED")
        self.assertEqual(event["role"], "CONTEXT")
        self.assertEqual(event["screen"]["kind"], "SCREEN_SNAPSHOT")
        self.assertEqual(event["news"]["items"][0]["tickers"], ["AAPL"])
        self.assertNotIn("REAL_TIME", json.dumps(event))

    def test_live_token_uses_factory_not_network(self) -> None:
        screener = _FakeScreener()
        news = _FakeNews()

        def factory(token: str) -> tuple[Any, Any]:
            self.assertEqual(token, TEST_TOKEN)
            return screener, news

        provider = FinvizEliteContextProvider(env=_token_env(live=True), client_factory=factory)
        result = provider.fetch_context("AAPL")
        self.assertEqual(result.status, "available")
        self.assertEqual(result.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
        self.assertEqual(screener.calls, 1)

    def test_live_without_token_stays_not_configured(self) -> None:
        env = _absent_env()
        env["IMP_FINVIZ_LIVE"] = "1"
        _, discovery = discover_finviz_context_stack(env=env)
        self.assertEqual(discovery.classification, "NOT_CONFIGURED")
        result = FinvizEliteContextProvider(env=env).fetch_context("AAPL")
        self.assertEqual(result.reason_code, "NOT_CONFIGURED")

    def test_es_symbol_is_rejected(self) -> None:
        provider = FinvizEliteContextProvider(
            env=_token_env(),
            screener=_FakeScreener(),
            news_client=_FakeNews(),
        )
        result = provider.fetch_context("ES")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "FINVIZ_NOT_ES_OR_FUTURES")

    def test_discovery_does_not_leak_secrets(self) -> None:
        env = _token_env()
        present = token_names_present(env)
        self.assertEqual(present, ("FINVIZ_API_KEY",))
        dumped = json.dumps(present)
        self.assertNotIn(TEST_TOKEN, dumped)
        self.assertNotIn("secret", dumped.lower())
        payload = run_finviz_context_overlay("AAPL", env=env)
        dumped_payload = json.dumps(payload)
        self.assertNotIn(TEST_TOKEN, dumped_payload)
        self.assertIn("FINVIZ_API_KEY", dumped_payload)

    def test_client_factory_not_called_when_token_absent(self) -> None:
        calls: list[str] = []

        def factory(_token: str) -> tuple[Any, Any]:
            calls.append("called")
            raise AssertionError("must not contact Finviz without a token")

        provider = FinvizEliteContextProvider(env=_absent_env(), client_factory=factory)
        result = provider.fetch_context("AAPL")
        self.assertEqual(result.reason_code, "NOT_CONFIGURED")
        self.assertEqual(calls, [])

    def test_composition_default_stub_is_unconfigured(self) -> None:
        composition = ProviderComposition()
        result = composition.equity_context.fetch_context("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, PROVIDER_UNAVAILABLE)
        self.assertEqual(composition.equity_context.provider_id, "stub.equity_context.unconfigured")

    def test_composition_helper_wires_finviz_identity(self) -> None:
        composition = with_finviz_elite_context(ProviderComposition(), env=_absent_env())
        self.assertEqual(composition.equity_context.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
        result = composition.equity_context.fetch_context("AAPL")
        self.assertEqual(result.reason_code, "NOT_CONFIGURED")
        self.assertFalse(hasattr(composition.equity_context, "fetch_quote"))
        self.assertEqual(composition.equity_context.timeliness, FINVIZ_CONTEXT_TIMELINESS)

    def test_overlay_is_not_l1_or_comparator(self) -> None:
        payload = run_finviz_context_overlay("AAPL", env=_absent_env())
        self.assertFalse(payload["discovery"]["is_l1"])
        self.assertFalse(payload["discovery"]["is_paper_comparator"])
        self.assertFalse(payload["result"]["is_l1"])
        self.assertFalse(payload["result"]["is_paper_comparator"])
        self.assertEqual(payload["discovery"]["role"], "CONTEXT")


def _login_env() -> dict[str, str]:
    env = _absent_env()
    env["FINVIZ_USERNAME"] = "operator@example.com"
    env["FINVIZ_PASSWORD"] = LOGIN_PASSWORD
    return env


def _stub_login_session(*, token: str = FETCHED_TOKEN, fail: bool = False) -> MagicMock:
    session = MagicMock()
    if fail:
        session.get.return_value = MagicMock(
            status_code=401,
            text="unauthorized",
            url="https://finviz.com/login-email?remember=true",
            headers={"content-type": "text/html"},
        )
        session.post.return_value = MagicMock(
            status_code=401,
            text="unauthorized",
            url="https://finviz.com/login_submit",
            headers={"content-type": "text/html"},
        )
        return session
    session.get.side_effect = [
        MagicMock(
            status_code=200,
            text='<form action="/login_submit"></form>',
            url="https://finviz.com/login-email?remember=true",
            headers={"content-type": "text/html"},
        ),
        MagicMock(
            status_code=200,
            text=f'<a href="/export/screener?auth={token}">API</a>',
            url="https://elite.finviz.com/api_explanation",
            headers={"content-type": "text/html"},
        ),
        MagicMock(
            status_code=200,
            text="Ticker,Price\nAAPL,100\n",
            url="https://elite.finviz.com/export/screener",
            headers={"content-type": "text/csv"},
        ),
    ]
    session.post.return_value = MagicMock(
        status_code=200,
        text="account",
        url="https://finviz.com/",
        headers={"content-type": "text/html"},
    )
    return session


class FinvizOverlayAutofetchTests(unittest.TestCase):
    def test_fetch_failure_keeps_overlay_absent(self) -> None:
        provider, discovery = discover_finviz_context_stack(
            env=_login_env(),
            session_factory=lambda: _stub_login_session(fail=True),
        )
        self.assertEqual(discovery.classification, "NOT_CONFIGURED")
        self.assertEqual(discovery.reason_code, "NOT_CONFIGURED")
        self.assertEqual(discovery.auto_fetch_status, "FETCH_FAILED")
        self.assertFalse(discovery.overlay_token_present)
        self.assertFalse(discovery.is_l1)
        result = provider.fetch_context("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "NOT_CONFIGURED")

    def test_token_fetcher_failure_is_not_configured(self) -> None:
        def boom() -> str:
            raise RuntimeError("login transport failed")

        _, discovery = discover_finviz_context_stack(
            env=_login_env(),
            token_fetcher=boom,
        )
        self.assertEqual(discovery.classification, "NOT_CONFIGURED")
        self.assertEqual(discovery.reason_code, "NOT_CONFIGURED")
        self.assertEqual(discovery.auto_fetch_status, "FETCH_FAILED")

    def test_http_stub_fetch_makes_overlay_token_present(self) -> None:
        screener = _FakeScreener()
        news = _FakeNews()
        received: list[str] = []

        def factory(token: str) -> tuple[Any, Any]:
            received.append("ok")
            self.assertEqual(token, FETCHED_TOKEN)
            return screener, news

        provider = FinvizEliteContextProvider(
            env=_login_env(),
            screener=screener,
            news_client=news,
            client_factory=factory,
        )
        adapter, discovery = discover_finviz_context_stack(
            env=_login_env(),
            provider=provider,
            session_factory=lambda: _stub_login_session(),
        )
        self.assertEqual(discovery.classification, "CONFIGURED")
        self.assertEqual(discovery.reason_code, "FINVIZ_CONTEXT_OVERLAY")
        self.assertEqual(discovery.auto_fetch_status, "FETCHED")
        self.assertTrue(discovery.overlay_token_present)
        self.assertFalse(discovery.is_l1)
        self.assertFalse(discovery.is_paper_comparator)
        self.assertEqual(adapter.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
        result = adapter.fetch_context("AAPL")
        self.assertEqual(result.status, "available")
        self.assertEqual(result.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
        self.assertEqual(screener.calls, 1)
        self.assertEqual(received, [])
        dumped = json.dumps(discovery.to_dict())
        self.assertNotIn(FETCHED_TOKEN, dumped)
        self.assertNotIn(LOGIN_PASSWORD, dumped)
        self.assertNotIn("operator@example.com", dumped)
        payload = run_finviz_context_overlay(
            "AAPL",
            env=_login_env(),
            provider=adapter,
        )
        dumped_payload = json.dumps(payload)
        self.assertNotIn(FETCHED_TOKEN, dumped_payload)
        self.assertNotIn(LOGIN_PASSWORD, dumped_payload)
        self.assertNotIn("yahoo", dumped_payload.lower())

    def test_fetched_token_without_transport_stays_live_disabled(self) -> None:
        _, discovery = discover_finviz_context_stack(
            env=_login_env(),
            session_factory=lambda: _stub_login_session(),
        )
        self.assertEqual(discovery.classification, "CONFIGURED_BLOCKED")
        self.assertEqual(discovery.reason_code, "LIVE_DISABLED")
        self.assertTrue(discovery.overlay_token_present)
        self.assertFalse(discovery.is_l1)

    def test_autofetch_from_existing_login_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp)
            isolated = {
                "IMP_FINVIZ_SECRET_DIR": str(secret),
                "IMP_PROVIDER_ENV": str(secret / "missing.env"),
            }
            for name in (*FINVIZ_TOKEN_NAMES, *FINVIZ_LOGIN_NAMES):
                isolated[name] = ""
            with patch.dict(os.environ, isolated, clear=False):
                reset_finviz_credential_manager()
                self.assertTrue(
                    write_login_credentials("operator@example.com", LOGIN_PASSWORD)
                )
                adapter, discovery = discover_finviz_context_stack(
                    env=None,
                    session_factory=lambda: _stub_login_session(),
                )
                self.assertEqual(discovery.auto_fetch_status, "FETCHED")
                self.assertTrue(adapter.configured())
                self.assertTrue(discovery.overlay_token_present)
                self.assertEqual(adapter.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
                dumped = json.dumps(discovery.to_dict())
                self.assertNotIn(FETCHED_TOKEN, dumped)
                self.assertNotIn(LOGIN_PASSWORD, dumped)
                reset_finviz_credential_manager()

    def test_autofetch_from_providers_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp)
            providers = secret / "providers.env"
            providers.write_text(
                "FINVIZ_USERNAME=operator@example.com\n"
                f"FINVIZ_PASSWORD={LOGIN_PASSWORD}\n",
                encoding="utf-8",
            )
            isolated = {
                "IMP_FINVIZ_SECRET_DIR": str(secret),
                "IMP_PROVIDER_ENV": str(providers),
            }
            for name in (*FINVIZ_TOKEN_NAMES, *FINVIZ_LOGIN_NAMES):
                isolated[name] = ""
            with patch.dict(os.environ, isolated, clear=False):
                reset_finviz_credential_manager()
                adapter, discovery = discover_finviz_context_stack(
                    env=None,
                    session_factory=lambda: _stub_login_session(),
                )
                self.assertEqual(discovery.auto_fetch_status, "FETCHED")
                self.assertTrue(adapter.configured())
                dumped = json.dumps(discovery.to_dict())
                self.assertNotIn(FETCHED_TOKEN, dumped)
                self.assertNotIn(LOGIN_PASSWORD, dumped)
                reset_finviz_credential_manager()

    def test_cloud_without_local_provider_info_stays_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp)
            isolated = {
                "IMP_FINVIZ_SECRET_DIR": str(secret),
                "IMP_PROVIDER_ENV": str(secret / "missing.env"),
            }
            for name in (*FINVIZ_TOKEN_NAMES, *FINVIZ_LOGIN_NAMES):
                isolated[name] = ""
            with patch.dict(os.environ, isolated, clear=False):
                reset_finviz_credential_manager()
                _, discovery = discover_finviz_context_stack(env=None)
                self.assertEqual(discovery.classification, "NOT_CONFIGURED")
                self.assertEqual(discovery.reason_code, "NOT_CONFIGURED")
                self.assertEqual(discovery.auto_fetch_status, "CREDENTIALS_ABSENT")
                self.assertFalse(discovery.overlay_token_present)
                reset_finviz_credential_manager()


if __name__ == "__main__":
    unittest.main()
