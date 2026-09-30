"""Screener News with free capabilities active: delayed NewsAPI Developer data, the persisted daily quota,
provider terms, IMP-derived FinBERT sentiment, and local AI synthesis status. Injected fakes only."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider  # noqa: E402
from market_platform_foundation.intelligence.inference.screener_synthesis import ScreenerSynthesizer  # noqa: E402
from market_platform_foundation.news.finbert_sentiment import FinbertSentiment  # noqa: E402
from market_platform_foundation.news.providers import NewsApiClient  # noqa: E402
from market_platform_foundation.ui_api.screener_news import NEWSAPI_DAILY_GUARD, ScreenerNewsService  # noqa: E402
from tests.platform.test_screener_s11 import NOW, loader, service  # noqa: E402

ARTICLE = {"title": "Apple unveils M5 MacBook lineup in delayed wire copy", "description": "Ships next week.",
           "url": "https://n.test/apple", "publishedAt": "2026-09-27T12:00:00Z", "source": {"name": "Wire"}}


def newsapi(calls=None):
    def getter(url, **kw):
        if calls is not None:
            calls.append(url)
        return type("R", (), {"status_code": 200, "text": json.dumps({"status": "ok", "articles": [ARTICLE]}), "headers": {}})()
    return lambda: NewsApiClient(api_key="k", live_enabled=True, min_interval_s=0, http_getter=getter)


class DelayedNewsApiTests(unittest.TestCase):
    def test_delayed_source_contributes_but_is_never_current(self):
        payload = service(newsapi=newsapi()).instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")
        status = next(item for item in payload["providers"] if item["id"] == "newsapi")
        self.assertEqual((status["state"], status["reason"]), ("DELAYED", "NEWSAPI_DEVELOPER_PLAN_24H_DELAY"))
        self.assertEqual((status["terms"]["restriction"], status["terms"]["timing"], status["terms"]["cost_usd"]),
                         ("DEVELOPMENT_ONLY", "DELAYED_24H", 0))
        self.assertIn("newsapi", {source["provider_id"] for story in payload["stories"] for source in story["sources"]})
        self.assertNotEqual(payload["state"], "UNAVAILABLE")
        self.assertTrue(any("Delayed development-plan source" in item["text"] for item in payload["analysis"]["insufficient"]))

    def test_overall_state_semantics(self):
        overall = ScreenerNewsService._overall
        self.assertEqual(overall({"CURRENT", "DELAYED"}, None), ("CURRENT", None))
        self.assertEqual(overall({"DELAYED", "LIVE_DISABLED"}, None), ("PARTIAL", "ONLY_DELAYED_PROVIDERS"))
        self.assertEqual(overall({"CURRENT", "RATE_LIMITED"}, None), ("PARTIAL", "SOME_PROVIDERS_NOT_CURRENT"))

    def test_daily_quota_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            quota = Path(directory) / "quota" / "newsapi-developer.json"
            first = service(newsapi=newsapi())
            first._newsapi_quota_path = quota
            first._newsapi_guard()
            saved = json.loads(quota.read_text(encoding="utf-8"))
            self.assertEqual((saved["count"], saved["limit"]), (1, NEWSAPI_DAILY_GUARD))
            quota.write_text(json.dumps({"day": datetime.fromtimestamp(NOW, tz=UTC).date().isoformat(),
                                         "count": NEWSAPI_DAILY_GUARD}), encoding="utf-8")
            restarted = ScreenerNewsService(newsapi_quota_path=quota, clock=lambda: NOW,
                                            sentiment=FinbertSentiment(model_path=""))
            self.assertFalse(restarted._newsapi_guard())          # no request once today's budget is spent

    def test_one_instrument_view_costs_at_most_one_request_per_ttl(self):
        calls = []
        svc = service(newsapi=newsapi(calls))
        for _ in range(5):                                          # renders / refreshes within the TTL
            svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")
        self.assertEqual(len(calls), 1)


class DerivedSentimentTests(unittest.TestCase):
    def test_scores_are_imp_derived_and_status_names_the_local_runtime(self):
        model = FinbertSentiment(model_path=str(ROOT / "tests"), loader=loader({"M5": "positive"}), model_source="SETUP_MANIFEST")
        svc = service(sentiment=model)
        feed = svc.feed(universe="US_EQUITIES")
        self.assertEqual((feed["sentiment_model"]["runtime"], feed["sentiment_model"]["basis"], feed["sentiment_model"]["model_source"]),
                         ("LOCAL_MODEL", "IMP_DERIVED_FINBERT", "SETUP_MANIFEST"))
        scored = [story["sentiment"] for story in feed["stories"] if story["sentiment"]["state"] == "SCORED"]
        self.assertTrue(scored)
        self.assertEqual({item["basis"] for item in scored}, {"IMP_DERIVED_FINBERT"})
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")
        finbert = next(item for item in panel["providers"] if item["id"] == "finbert")
        self.assertEqual((finbert["terms"]["runtime"], finbert["terms"]["cost_usd"]), ("LOCAL_MODEL", 0))


class LocalAiStatusTests(unittest.TestCase):
    def test_local_provider_is_available_without_paid_credentials(self):
        provider = LocalChatInferenceProvider(base_url="http://127.0.0.1:1", model_id="Qwen/Qwen3-4B-GGUF:Q4_K_M",
                                              poster=lambda url, body, timeout: (500, b""))
        svc = service()
        svc._synthesizer = ScreenerSynthesizer(provider=provider)
        ai = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["ai"]
        self.assertEqual((ai["state"], ai["runtime"], ai["model_id"]), ("AVAILABLE", "LOCAL_MODEL", "Qwen/Qwen3-4B-GGUF:Q4_K_M"))

    def test_coverage_states_how_many_matched_stories_the_model_saw(self):
        seen = []

        class Capped:
            def synthesize(self, stories, **kwargs):
                seen.append(len(stories))
                return {"state": "CURRENT", "story_ids": [story.story_id for story in stories[:1]]}
        svc = service()
        svc._synthesizer = Capped()
        coverage = svc.synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")["coverage"]
        self.assertGreater(seen[0], 1)
        self.assertEqual((coverage["story_count"], coverage["synthesized_story_count"]), (seen[0], 1))

    def test_no_provider_reason_is_explicit(self):
        svc = service()
        svc._synthesizer = ScreenerSynthesizer(provider=None, not_configured_reason="NO_SYNTHESIS_PROVIDER_CONFIGURED")
        ai = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["ai"]
        self.assertEqual((ai["state"], ai["reason"]), ("NOT_CONFIGURED", "NO_SYNTHESIS_PROVIDER_CONFIGURED"))
        # News itself still works without any synthesis provider.
        self.assertTrue(svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["stories"])


if __name__ == "__main__":
    unittest.main()
