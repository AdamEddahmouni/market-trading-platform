from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from apps.research_screener.news_live import (
    FinnhubNewsProvider,
    NewsOrchestrator,
    NewsProvider,
)
from apps.research_screener.finnhub_live import FinnhubClient


class _StubNewsProvider(NewsProvider):
    def __init__(self, name: str, items: list[dict[str, Any]], *, configured: bool = True) -> None:
        self._name = name
        self._items = items
        self._configured = configured

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def provider_name(self) -> str:
        return self._name

    def fetch_news(self, symbol: str, *, force: bool = False) -> list[dict[str, Any]]:
        return list(self._items)


def test_orchestrator_sort_tolerates_unparseable_timestamps() -> None:
    providers = [
        _StubNewsProvider(
            "Finviz Elite",
            [
                {"headline": "older", "timestamp": "not-a-date"},
                {"headline": "newer", "timestamp": "2026-07-27T12:00:00Z"},
            ],
        ),
    ]
    orch = NewsOrchestrator(providers=providers, cache_ttl_s=0)
    headlines = orch.fetch_news("AAA", force=True)
    assert len(headlines) == 2
    assert headlines[0]["headline"] == "newer"


def test_provider_order_resolves_finviz_news_alias() -> None:
    finviz = _StubNewsProvider("Finviz Elite", [{"headline": "from finviz", "timestamp": ""}])
    other = _StubNewsProvider("NewsAPI", [{"headline": "from newsapi", "timestamp": ""}])
    orch = NewsOrchestrator(
        providers=[finviz, other],
        provider_order=["Finviz News", "NewsAPI"],
        cache_ttl_s=0,
    )
    ordered = [p.provider_name for p in orch._ordered_providers()]
    assert ordered == ["Finviz Elite", "NewsAPI"]


def test_finnhub_company_news_includes_from_and_to(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> list:
            return []

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        captured["params"] = kwargs.get("params")
        return FakeResponse()

    monkeypatch.setattr("apps.research_screener.news_live.requests.get", fake_get)
    provider = FinnhubNewsProvider("test-token")
    provider.fetch_news("AAA", force=True)

    params = captured.get("params") or {}
    assert params.get("symbol") == "AAA"
    assert params.get("from")
    assert params.get("to")
    from_date = datetime.fromisoformat(str(params["from"]))
    to_date = datetime.fromisoformat(str(params["to"]))
    assert (to_date - from_date).days == 7


def test_finnhub_403_reports_account_access_without_plan_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 403

    monkeypatch.setattr(
        "apps.research_screener.news_live.requests.get",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    provider = FinnhubNewsProvider("test-token")

    assert provider.fetch_news("AAA", force=True) == []
    error = str(provider.status()["last_error"]).lower()
    assert "account access" in error
    assert "premium" not in error


def test_finnhub_client_403_reports_account_access_without_plan_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 403

    monkeypatch.setattr(
        "apps.research_screener.finnhub_live.requests.get",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    client = FinnhubClient("test-token")

    assert client.fetch_company_news("AAA") == []
    error = str(client.status()["news_last_error"]).lower()
    assert "account access" in error
    assert "premium" not in error


def test_finviz_news_timestamp_normalization() -> None:
    from apps.research_screener.finviz_live import _normalize_finviz_news_timestamp

    iso = _normalize_finviz_news_timestamp("2026-07-27T10:15:00Z")
    assert iso.startswith("2026-07-27")
    parsed = _normalize_finviz_news_timestamp("Jul-27-26")
    assert "2026" in parsed
