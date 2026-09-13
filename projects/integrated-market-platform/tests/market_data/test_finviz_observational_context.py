"""Finviz Elite context overlay joined into the canonical observational hop.

Proves the fail-closed screening/news overlay (``equity_context``) is wired
into ``ObservationalRuntimeComposition`` — the canonical quote → admission →
observational-store hop — as a side-channel lane. Not L1, not admission, not
the Paper comparator, and never ``REAL_TIME``.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.finviz.news import parse_news_csv  # noqa: E402
from market_platform_foundation.finviz.screener import parse_screener_csv  # noqa: E402
from market_platform_foundation.market_data.observational_lanes import (  # noqa: E402
    ObservationalLaneRuntime,
)
from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)
from market_platform_foundation.market_data.runtime_composition import (  # noqa: E402
    ObservationalRuntimeComposition,
)
from market_platform_foundation.providers.adapters.finviz_elite_context import (  # noqa: E402
    FINVIZ_CONTEXT_PROVIDER_ID,
    FinvizEliteContextProvider,
)
from market_platform_foundation.providers.composition import (  # noqa: E402
    with_finviz_elite_observational_context,
)
from market_platform_foundation.providers.contracts import (  # noqa: E402
    PROVIDER_UNAVAILABLE,
    ProviderResult,
)
from market_platform_foundation.providers.finviz_context_discovery import (  # noqa: E402
    FINVIZ_LOGIN_NAMES,
    FINVIZ_TOKEN_NAMES,
    discover_finviz_context_stack,
)

FIXTURES = ROOT / "tests" / "fixtures" / "finviz"
TEST_TOKEN = "test-token-not-a-secret"
FETCHED_TOKEN = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
LOGIN_PASSWORD = "not-a-real-password"


def _absent_env() -> dict[str, str]:
    env = {name: "" for name in FINVIZ_TOKEN_NAMES}
    for name in FINVIZ_LOGIN_NAMES:
        env[name] = ""
    return env


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


def _token_env() -> dict[str, str]:
    env = _absent_env()
    env["FINVIZ_API_KEY"] = TEST_TOKEN
    return env


class _FakeScreener:
    """Fixture-backed screener client — never contacts elite.finviz.com."""

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
    """Fixture-backed news client — never contacts elite.finviz.com."""

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


class _RealTimeClaimProvider:
    """Adversarial fixture: a context provider that declares REAL_TIME."""

    provider_id = "test.context.realtime_liar"
    capability = "equity_context"
    role = "CONTEXT"
    timeliness = "REAL_TIME"

    def fetch_context(self, symbol: str) -> ProviderResult:
        return ProviderResult(
            status="available",
            events=({"instrument_id": symbol, "timeliness": "REAL_TIME"},),
            provider_id=self.provider_id,
            capability=self.capability,
        )


class _EventLevelRealTimeClaimProvider:
    """Declares DELAYED but the event payload itself claims REAL_TIME."""

    provider_id = "test.context.event_realtime_liar"
    capability = "equity_context"
    role = "CONTEXT"
    timeliness = "DELAYED"

    def fetch_context(self, symbol: str) -> ProviderResult:
        return ProviderResult(
            status="available",
            events=({"instrument_id": symbol, "timeliness": "REAL_TIME"},),
            provider_id=self.provider_id,
            capability=self.capability,
        )


class ObservationalContextOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ObservationalStateStore()
        self.lanes = ObservationalLaneRuntime(self.store)

    def test_default_composition_slot_is_unconfigured_fail_closed(self) -> None:
        composition = ObservationalRuntimeComposition()
        self.assertEqual(
            composition.equity_context.provider_id, "stub.equity_context.unconfigured"
        )
        payload = composition.context_for("AAPL")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], PROVIDER_UNAVAILABLE)
        self.assertFalse(payload["is_l1"])
        self.assertFalse(payload["is_paper_comparator"])
        self.assertEqual(composition.manifest()["context_provider_id"], "stub.equity_context.unconfigured")

    def test_token_absent_is_not_configured_no_elite_http(self) -> None:
        calls: list[str] = []

        def boom(_token: str) -> tuple[Any, Any]:
            calls.append("called")
            raise AssertionError("paid Finviz HTTP must not run when the token is absent")

        provider = FinvizEliteContextProvider(env=_absent_env(), client_factory=boom)
        composition = with_finviz_elite_observational_context(
            ObservationalRuntimeComposition(), provider=provider
        )
        self.assertEqual(composition.equity_context.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
        payload = composition.context_for("AAPL")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "NOT_CONFIGURED")
        self.assertEqual(calls, [], "Elite HTTP client factory must not be invoked without a token")

    def test_discovery_wires_finviz_identity_when_no_provider_given(self) -> None:
        composition = with_finviz_elite_observational_context(
            ObservationalRuntimeComposition(), env=_absent_env()
        )
        self.assertEqual(composition.equity_context.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
        payload = composition.context_for("AAPL")
        self.assertEqual(payload["reason"], "NOT_CONFIGURED")

    def test_context_lane_does_not_replace_l1_or_claim_real_time(self) -> None:
        composition = with_finviz_elite_observational_context(
            ObservationalRuntimeComposition(), env=_absent_env()
        )
        composition.store.apply_quote_update(
            instrument_id="AAPL",
            bid_price=100.0,
            ask_price=101.0,
            provider="ibkr.observational",
            event_time_ns=900,
            received_ns=1000,
        )
        bundle = composition.evidence_for("AAPL")
        self.assertIn("l1", bundle)
        self.assertIn("context", bundle)
        l1 = bundle["l1"]
        context = bundle["context"]
        self.assertEqual(l1["provenance"]["provider"], "ibkr.observational")
        self.assertNotEqual(context.get("provider_id"), "ibkr.observational")
        self.assertFalse(context["is_l1"])
        self.assertFalse(context["is_paper_comparator"])
        self.assertNotEqual(context.get("timeliness"), "REAL_TIME")

    def test_configured_token_stays_delayed_role_context_via_injected_clients(self) -> None:
        screener = _FakeScreener()
        news = _FakeNews()
        provider = FinvizEliteContextProvider(
            env=_token_env(), screener=screener, news_client=news
        )
        composition = with_finviz_elite_observational_context(
            ObservationalRuntimeComposition(), provider=provider
        )
        payload = composition.context_for("AAPL")
        self.assertTrue(payload["available"])
        self.assertEqual(payload["timeliness"], "DELAYED")
        self.assertNotEqual(payload["timeliness"], "REAL_TIME")
        self.assertEqual(payload["role"], "CONTEXT")
        self.assertFalse(payload["is_l1"])
        self.assertFalse(payload["is_paper_comparator"])
        self.assertEqual(screener.calls, 1)
        self.assertEqual(news.calls, 1)

    def test_declared_real_time_provider_fails_closed(self) -> None:
        payload = self.lanes.build_context_payload("AAPL", _RealTimeClaimProvider())
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "CONTEXT_TIMELINESS_INVALID")
        self.assertFalse(payload["is_l1"])
        self.assertFalse(payload["is_paper_comparator"])

    def test_event_level_real_time_claim_fails_closed(self) -> None:
        payload = self.lanes.build_context_payload("AAPL", _EventLevelRealTimeClaimProvider())
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "CONTEXT_TIMELINESS_INVALID")

    def test_missing_fetch_context_attribute_fails_closed(self) -> None:
        class _NoFetch:
            provider_id = "test.context.no_fetch"

        payload = self.lanes.build_context_payload("AAPL", _NoFetch())
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], PROVIDER_UNAVAILABLE)

    def test_evidence_hash_unaffected_by_context_lane(self) -> None:
        composition = ObservationalRuntimeComposition()
        composition.store.apply_quote_update(
            instrument_id="NVDA",
            bid_price=100.0,
            ask_price=101.0,
            provider="replay",
        )
        first = composition.evidence_for("NVDA")
        second = composition.evidence_for("NVDA")
        self.assertEqual(first["evidence_hash"], second["evidence_hash"])
        with_finviz_elite_observational_context(composition, env=_absent_env())
        third = composition.evidence_for("NVDA")
        self.assertEqual(third["evidence_hash"], first["evidence_hash"])

    def test_helper_rejects_composition_without_equity_context_slot(self) -> None:
        class _NoSlot:
            pass

        with self.assertRaises(AttributeError):
            with_finviz_elite_observational_context(_NoSlot(), env=_absent_env())

    def test_autofetch_failure_keeps_hop_context_absent_and_l1_untouched(self) -> None:
        composition = with_finviz_elite_observational_context(
            ObservationalRuntimeComposition(),
            env=_login_env(),
            session_factory=lambda: _stub_login_session(fail=True),
        )
        composition.store.apply_quote_update(
            instrument_id="AAPL",
            bid_price=100.0,
            ask_price=101.0,
            provider="moomoo.opend",
            event_time_ns=900,
            received_ns=1000,
        )
        bundle = composition.evidence_for("AAPL")
        self.assertEqual(bundle["l1"]["provenance"]["provider"], "moomoo.opend")
        context = bundle["context"]
        self.assertFalse(context["available"])
        self.assertEqual(context["reason"], "NOT_CONFIGURED")
        self.assertFalse(context["is_l1"])
        self.assertNotEqual(context.get("provider_id"), "moomoo.opend")
        self.assertNotEqual(context.get("provider_id"), "yahoo.finance.delayed")
        dumped = json.dumps(bundle["context"])
        self.assertNotIn(LOGIN_PASSWORD, dumped)
        self.assertNotIn(FETCHED_TOKEN, dumped)

    def test_autofetch_success_is_overlay_only_not_hop_l1(self) -> None:
        provider = FinvizEliteContextProvider(
            env=_login_env(),
            screener=_FakeScreener(),
            news_client=_FakeNews(),
        )
        adapter, discovery = discover_finviz_context_stack(
            env=_login_env(),
            provider=provider,
            session_factory=lambda: _stub_login_session(),
        )
        self.assertEqual(discovery.auto_fetch_status, "FETCHED")
        self.assertTrue(discovery.overlay_token_present)
        self.assertFalse(discovery.is_l1)
        composition = with_finviz_elite_observational_context(
            ObservationalRuntimeComposition(), provider=adapter
        )
        composition.store.apply_quote_update(
            instrument_id="AAPL",
            bid_price=100.0,
            ask_price=101.0,
            provider="moomoo.opend",
            event_time_ns=900,
            received_ns=1000,
        )
        bundle = composition.evidence_for("AAPL")
        self.assertEqual(bundle["l1"]["provenance"]["provider"], "moomoo.opend")
        context = bundle["context"]
        self.assertTrue(context["available"])
        self.assertEqual(context["provider_id"], FINVIZ_CONTEXT_PROVIDER_ID)
        self.assertEqual(context["role"], "CONTEXT")
        self.assertEqual(context["timeliness"], "DELAYED")
        self.assertFalse(context["is_l1"])
        self.assertFalse(context["is_paper_comparator"])
        self.assertNotEqual(context["provider_id"], "yahoo.finance.delayed")
        dumped = json.dumps(context)
        self.assertNotIn(FETCHED_TOKEN, dumped)
        self.assertNotIn(LOGIN_PASSWORD, dumped)
        self.assertNotIn("yahoo", dumped.lower())


if __name__ == "__main__":
    unittest.main()
