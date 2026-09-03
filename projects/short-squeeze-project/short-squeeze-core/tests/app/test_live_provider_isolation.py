from __future__ import annotations

from pathlib import Path

from apps.research_screener.finviz_live import FinvizClient
from apps.research_screener.live_providers import ProviderBundle
from apps.research_screener.news_live import NewsApiClient
from apps.research_screener.private_config import load_provider_credentials


class FakeResponse:
    def __init__(
        self, *, text: str = "", payload: dict | None = None, status_code: int = 200,
    ) -> None:
        self.text = text
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_private_config_is_disabled_without_an_explicit_path(tmp_path: Path) -> None:
    private = tmp_path / "providers.env"
    private.write_text("NEWSAPI_KEY=private-value\n", encoding="utf-8")
    credentials = load_provider_credentials()
    assert credentials.values == {}
    assert credentials.path is None
    assert NewsApiClient().configured is False


def test_private_config_loads_only_the_explicit_file(tmp_path: Path) -> None:
    private = tmp_path / "providers.env"
    private.write_text(
        "# local only\nFINVIZ_API_KEY=finviz-test\nNEWSAPI_KEY=news-test\n",
        encoding="utf-8",
    )
    credentials = load_provider_credentials(private)
    assert credentials.path == private.resolve()
    assert set(credentials.values) == {"FINVIZ_API_KEY", "NEWSAPI_KEY"}


def test_production_bundle_enables_public_sec_only_when_explicitly_built(
    tmp_path: Path,
) -> None:
    private = tmp_path / "providers.env"
    private.write_text("", encoding="utf-8")
    assert ProviderBundle.offline().sec.configured is False
    assert ProviderBundle.from_private_config(private).sec.configured is True


def test_finviz_official_csv_is_normalized_and_secret_is_not_in_url(monkeypatch) -> None:
    captured: dict = {}
    csv_text = (
        "Ticker,Company,Sector,Industry,Country,Price,Change,Volume,"
        "Average Volume,Relative Volume,Market Cap.,Shares Out.,Float,"
        "Short Float,Short Ratio,Earnings\n"
        "AAA,AAA Inc,Technology,Software,USA,7.00,12.5%,2000000,"
        "1000000,2.0,70M,10M,8M,14.0%,3.2,Jul 30 AMC\n"
    )

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(text=csv_text)

    monkeypatch.setattr("apps.research_screener.finviz_live.requests.get", fake_get)
    client = FinvizClient("finviz-secret")
    result = client.fetch_screener(force=True)
    row = client.get_row("AAA")
    assert result["success"] is True
    assert result["rows"] == 1
    assert row is not None
    assert row.float_shares == 8_000_000
    assert row.short_float_pct == 14.0
    assert "finviz-secret" not in captured["url"]
    assert captured["params"]["auth"] == "finviz-secret"


def test_finviz_error_is_redacted_and_last_good_rows_are_retained(monkeypatch) -> None:
    csv_text = "Ticker,Float\nAAA,8M\n"
    calls = iter([
        FakeResponse(text=csv_text),
        RuntimeError("request failed for https://example/?auth=finviz-secret"),
    ])

    def fake_get(*args, **kwargs):
        response = next(calls)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("apps.research_screener.finviz_live.requests.get", fake_get)
    client = FinvizClient("finviz-secret")
    assert client.fetch_screener(force=True)["success"] is True
    failed = client.fetch_screener(force=True)
    assert failed["success"] is False
    assert failed["stale"] is True
    assert failed["rows"] == 1
    assert failed["retained_last_good"] is True
    assert client.get_row("AAA") is not None
    assert client.status()["stale"] is True
    assert "finviz-secret" not in str(failed)


def test_finviz_rejects_login_page_and_records_provider_columns(monkeypatch) -> None:
    calls = iter([
        FakeResponse(text="Ticker,Float\nAAA,8M\n"),
        FakeResponse(
            text="<html><form action='/login'>Please log in</form></html>",
            status_code=200,
        ),
    ])

    monkeypatch.setattr(
        "apps.research_screener.finviz_live.requests.get",
        lambda *args, **kwargs: next(calls),
    )
    client = FinvizClient("finviz-secret")
    assert client.fetch_screener(force=True)["success"] is True
    row = client.get_row("AAA")
    assert row is not None
    assert row.provider_columns == ("Ticker", "Float")

    failed = client.fetch_screener(force=True)
    assert failed["success"] is False
    assert failed["error"] == "FINVIZ_EXPORT_LOGIN_PAGE"
    assert failed["rows"] == 1
    status = client.status()
    assert status["ttl_seconds"] > 0
    assert status["columns"] == ["Ticker", "Float"]
    assert status["last_success_at"]


def test_finviz_parses_current_shares_float_column(monkeypatch) -> None:
    responses = iter([FakeResponse(text="Ticker,Shares Float\nAAA,8M\n")])
    monkeypatch.setattr(
        "apps.research_screener.finviz_live.requests.get",
        lambda *args, **kwargs: next(responses),
    )

    client = FinvizClient("test-token")
    assert client.fetch_screener(force=True)["success"] is True
    row = client.get_row("AAA")

    assert row is not None
    assert row.float_shares == 8_000_000
    assert "Shares Float" in row.provider_columns


def test_finviz_duplicate_symbol_is_withheld_as_mapping_conflict(monkeypatch) -> None:
    response = FakeResponse(text="Ticker,Float\nAAA,8M\nAAA,9M\n")
    monkeypatch.setattr(
        "apps.research_screener.finviz_live.requests.get",
        lambda *args, **kwargs: response,
    )
    client = FinvizClient("finviz-secret")
    result = client.fetch_screener(force=True)
    assert result["success"] is True
    assert result["mapping_conflicts"] == 1
    assert client.get_row("AAA") is None
    assert client.status()["mapping_conflict_symbols"] == ["AAA"]


def test_newsapi_uses_params_and_retains_last_good_headlines(monkeypatch) -> None:
    captured: dict = {}
    calls = iter([
        FakeResponse(payload={"articles": [{
            "title": "AAA deterministic headline",
            "publishedAt": "2026-07-25T13:00:00Z",
            "url": "https://example.invalid/article",
        }]}),
        RuntimeError("request failed with apiKey=news-secret"),
    ])

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        response = next(calls)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("apps.research_screener.news_live.requests.get", fake_get)
    client = NewsApiClient("news-secret")
    first = client.fetch_news("AAA", force=True)
    second = client.fetch_news("AAA", force=True)
    assert len(first) == len(second) == 1
    assert "news-secret" not in captured["url"]
    assert captured["params"]["apiKey"] == "news-secret"
    assert "news-secret" not in str(client.status())


def test_bundle_does_not_report_swallowed_news_error_as_success() -> None:
    class FailingNews:
        configured = True

        def fetch_news(self, symbol: str, force: bool = False):
            return []

        def status(self):
            return {
                "provider": "FakeNews", "configured": True,
                "cached_symbols": 0, "last_error": "controlled outage",
            }

    bundle = ProviderBundle(news=FailingNews())
    result = bundle.refresh_all(["AAA"])
    assert bundle.status()["newsapi"]["fetched"] is False
    assert bundle.status()["newsapi"]["last_error"] == "controlled outage"
    assert result["errors"] == [{
        "provider": "NewsAPI", "symbol": "AAA", "error": "controlled outage",
    }]


def test_bundle_reports_actual_finnhub_sec_and_news_usage_without_accumulating() -> None:
    class FakeNews:
        configured = True

        def fetch_news(self, symbol: str, force: bool = False):
            return [{"headline": f"{symbol} update", "provider": "FakeNews"}]

        def status(self):
            return {"provider": "FakeNews", "configured": True, "last_error": None}

    class FakeFinnhub:
        configured = True

        def fetch_price(self, symbol: str):
            return 7.25

    class FakeSec:
        configured = True

        def has_recent_catalyst_filing(self, symbol: str):
            return {"available": True, "all_filings": [], "retrieved_at": "now"}

    bundle = ProviderBundle(news=FakeNews(), finnhub=FakeFinnhub(), sec=FakeSec())
    bundle.refresh_all(["AAA", "BBB"])
    first = bundle.status()
    result = bundle.refresh_all(["AAA", "BBB"])
    second = bundle.status()

    assert first["newsapi"]["headline_count"] == 2
    assert second["newsapi"]["headline_count"] == 2
    assert second["finnhub"]["fetched"] is True
    assert second["finnhub"]["price_count"] == 2
    assert second["sec_edgar"]["fetched"] is True
    assert second["sec_edgar"]["result_count"] == 2
    assert result["providers"]["newsapi"]["headline_count"] == 2
    assert result["providers"]["finnhub"]["price_count"] == 2
    assert result["providers"]["sec_edgar"]["result_count"] == 2
