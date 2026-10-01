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


class InstrumentRelevanceTests(unittest.TestCase):
    def test_provider_tag_without_the_instrument_in_the_text_is_not_instrument_news(self):
        from types import SimpleNamespace

        from market_platform_foundation.news.provider_linkage_quality import FLAG_TICKER_NOT_IN_TEXT
        from market_platform_foundation.ui_api.screener_news import _tag_only_unnamed

        def record(flags, *bases):
            return SimpleNamespace(event=SimpleNamespace(quality_flags=tuple(flags)),
                                   matches=[SimpleNamespace(basis=basis) for basis in bases])
        # A broad market piece the provider tagged with the ticker, never naming the company: dropped.
        self.assertTrue(_tag_only_unnamed(record([FLAG_TICKER_NOT_IN_TEXT], "PROVIDER_TICKER")))
        # The text itself names the instrument, or the tag is corroborated: kept.
        self.assertFalse(_tag_only_unnamed(record([FLAG_TICKER_NOT_IN_TEXT], "PROVIDER_TICKER", "EXACT_ENTITY")))
        self.assertFalse(_tag_only_unnamed(record([], "PROVIDER_TICKER")))


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

    def test_paid_provider_states_its_daily_budget_and_exhaustion(self):
        from market_platform_foundation.intelligence.inference.anthropic_synthesis import (
            AnthropicSynthesisProvider, BudgetedProvider, DailyBudget,
        )

        budget = DailyBudget(None, max_requests=2, max_tokens=100_000, clock=lambda: NOW)
        svc = service()
        svc._synthesizer = ScreenerSynthesizer(provider=BudgetedProvider(AnthropicSynthesisProvider(
            api_key="k", poster=lambda *args: (500, b"")), budget))
        ai = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["ai"]
        self.assertEqual((ai["state"], ai["runtime"], ai["budget"]["requests"], ai["budget"]["max_requests"]),
                         ("AVAILABLE", "PAID_API", 0, 2))
        budget.reserve(10)
        budget.reserve(10)
        ai = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["ai"]
        self.assertEqual((ai["state"], ai["reason"]), ("UNAVAILABLE", "SYNTHESIS_DAILY_BUDGET_EXHAUSTED"))

    def test_synthesis_response_carries_budget_after_the_call(self):
        from market_platform_foundation.intelligence.inference.anthropic_synthesis import (
            AnthropicSynthesisProvider, BudgetedProvider, DailyBudget,
        )

        budget = DailyBudget(None, max_requests=5, max_tokens=100_000, clock=lambda: NOW)
        svc = service()
        svc._synthesizer = ScreenerSynthesizer(provider=BudgetedProvider(AnthropicSynthesisProvider(
            api_key="k", poster=lambda *args: (500, b"")), budget), clock=lambda: NOW)
        result = svc.synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual((result["budget"]["requests"], result["budget"]["max_requests"]), (1, 5))
        self.assertEqual([item["story_id"] for item in result["stories"]], result["story_ids"])
        self.assertTrue(all("headline" in item and "url" in item for item in result["stories"]))
        # A local model states no budget.
        local = service(provider=None)
        self.assertIsNone(local.synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")["budget"])

    def test_preview_states_paid_cost_without_calling_the_model(self):
        from market_platform_foundation.intelligence.inference.anthropic_synthesis import (
            AnthropicSynthesisProvider, BudgetedProvider, DailyBudget,
        )

        calls = []
        budget = DailyBudget(None, clock=lambda: NOW)
        svc = service()
        svc._synthesizer = ScreenerSynthesizer(provider=BudgetedProvider(AnthropicSynthesisProvider(
            api_key="k", poster=lambda *args: calls.append(args) or (500, b"")), budget), clock=lambda: NOW)
        preview = svc.synthesis_preview(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual((preview["ai"]["runtime"], preview["estimate"]["cached"]), ("PAID_API", False))
        self.assertGreater(preview["estimate"]["story_count"], 0)
        self.assertGreater(preview["estimate"]["tokens"], 1_500)
        universe = svc.synthesis_preview(universe="US_EQUITIES", scope="UNIVERSE", window="72h")
        self.assertGreaterEqual(universe["estimate"]["story_count"], preview["estimate"]["story_count"])
        # The pre-click estimate states how many matched stories exist beyond those it would send.
        self.assertGreaterEqual(universe["estimate"]["available_story_count"], universe["estimate"]["story_count"])
        self.assertIsNone(svc.synthesis_preview(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:NOPE"))
        self.assertEqual((calls, budget.status()["requests"]), ([], 0))

    def test_preview_has_no_estimate_for_a_local_model(self):
        provider = LocalChatInferenceProvider(base_url="http://127.0.0.1:1", model_id="Qwen/Qwen3-4B-GGUF:Q4_K_M",
                                              poster=lambda url, body, timeout: (500, b""))
        svc = service()
        svc._synthesizer = ScreenerSynthesizer(provider=provider)
        preview = svc.synthesis_preview(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual((preview["ai"]["runtime"], preview["estimate"]), ("LOCAL_MODEL", None))

    def test_preview_route_is_a_read(self):
        from market_platform_foundation.platform.security.route_policy import policy_for_route

        self.assertEqual(policy_for_route("GET", "/screener/news/synthesis/preview").capability, "state.read")

    def test_no_provider_reason_is_explicit(self):
        svc = service()
        svc._synthesizer = ScreenerSynthesizer(provider=None, not_configured_reason="NO_SYNTHESIS_PROVIDER_CONFIGURED")
        ai = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["ai"]
        self.assertEqual((ai["state"], ai["reason"]), ("NOT_CONFIGURED", "NO_SYNTHESIS_PROVIDER_CONFIGURED"))
        # News itself still works without any synthesis provider.
        self.assertTrue(svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["stories"])


class EngineChoiceTests(unittest.TestCase):
    """The operator's engine picker: listed in every AI status, switched without a restart, never a model call."""

    def setUp(self):
        from market_platform_foundation.intelligence.inference.synthesis_engines import SynthesisSettings
        from market_platform_foundation.ui_api.screener_news import _default_synthesizer

        self._directory = tempfile.TemporaryDirectory()
        values = {"ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o"}
        self.settings = SynthesisSettings(values.get, Path(self._directory.name))
        self.svc = service()
        self.svc._synthesis_settings = self.settings
        self.svc._synthesizer_factory = lambda: _default_synthesizer(self.settings)

    def tearDown(self):
        self._directory.cleanup()

    def test_status_lists_engines_and_the_automatic_choice(self):
        ai = self.svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["ai"]
        self.assertEqual((ai["engine"], ai["engine_source"], ai["model_id"]), ("auto", "AUTOMATIC", "claude-sonnet-5-5"))
        self.assertEqual([item["id"] for item in ai["engines"]], ["local", "anthropic", "openai", "gemini"])
        preview = self.svc.synthesis_preview(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual(preview["ai"]["engines"], ai["engines"])

    def test_switching_rebuilds_the_provider_and_is_saved(self):
        before = self.svc._get_synthesizer()
        ai = self.svc.select_synthesis_engine("openai", "gpt-6.1-sol")
        self.assertEqual((ai["engine"], ai["engine_model"], ai["engine_source"]), ("openai", "gpt-6.1-sol", "OPERATOR"))
        self.assertEqual((ai["state"], ai["runtime"], ai["provider_id"], ai["model_id"]),
                         ("AVAILABLE", "PAID_API", "openai.chat_completions", "gpt-6.1-sol"))
        self.assertIsNot(self.svc._get_synthesizer(), before)
        # A chosen engine without its key is stated, never silently replaced by another vendor.
        ai = self.svc.select_synthesis_engine("gemini")
        self.assertEqual((ai["state"], ai["reason"]), ("NOT_CONFIGURED", "GEMINI_API_KEY_NOT_SET"))

    def test_invalid_choices_are_rejected_and_change_nothing(self):
        for engine, model in (("nope", None), ("openai", "not-in-catalog")):
            with self.subTest(engine=engine), self.assertRaises(ValueError):
                self.svc.select_synthesis_engine(engine, model)
        self.assertEqual(self.svc.ai_status()["engine"], "auto")
        with self.assertRaisesRegex(ValueError, "SYNTHESIS_ENGINE_NOT_SELECTABLE"):
            service().select_synthesis_engine("local")

    def test_status_with_engines_passes_the_leak_audit(self):
        from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload

        self.svc.select_synthesis_engine("anthropic", "claude-haiku-4-5-20251001")
        assert_no_secrets_in_payload(self.svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL"))
        assert_no_secrets_in_payload(self.svc.select_synthesis_engine("openai"))
        self.assertNotIn('"a"', json.dumps(self.svc.ai_status()))              # key values never appear

    def test_engine_route_is_an_operator_write(self):
        from market_platform_foundation.platform.security.route_policy import policy_for_route

        self.assertEqual(policy_for_route("POST", "/screener/news/synthesis/engine").capability, "state.write")


if __name__ == "__main__":
    unittest.main()
