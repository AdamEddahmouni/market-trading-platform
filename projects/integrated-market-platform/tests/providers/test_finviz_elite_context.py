"""Finviz Elite fail-closed context overlay — not L1, not a comparator."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

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
from market_platform_foundation.providers.finviz_context_discovery import (
    FINVIZ_TOKEN_NAMES,
    discover_finviz_context_stack,
    run_finviz_context_overlay,
    token_names_present,
)

FIXTURES = ROOT / "tests" / "fixtures" / "finviz"
TEST_TOKEN = "test-token-not-a-secret"


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
    return {name: "" for name in FINVIZ_TOKEN_NAMES}


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


if __name__ == "__main__":
    unittest.main()
