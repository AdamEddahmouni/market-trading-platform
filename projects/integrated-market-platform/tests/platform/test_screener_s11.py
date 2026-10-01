"""S11 Screener News, Headlines, Sentiment & Analysis: feed, instrument panel, preview, synthesis.

All providers are injected fakes (no network, no model download, no live AI).
"""

from __future__ import annotations

import json
import sys
import unittest
from unittest import mock
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse  # noqa: E402
from market_platform_foundation.intelligence.inference.errors import InferenceErrorCode  # noqa: E402
from market_platform_foundation.intelligence.inference.screener_synthesis import (  # noqa: E402
    ScreenerSynthesizer, parse_synthesis, unsupported_certainty,
)
from market_platform_foundation.news.finbert_sentiment import FinbertSentiment, LoadedModel  # noqa: E402
from market_platform_foundation.news.providers import FinnhubNewsClient, NewsApiClient  # noqa: E402
from market_platform_foundation.news.rss_feeds import Feed, RssNewsSource  # noqa: E402
from market_platform_foundation.news.sec_filings_news import SecFilingNews  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.ui_api.screener_config import validate_panel_layout  # noqa: E402
from market_platform_foundation.ui_api.screener_news import ScreenerNewsService, provider_status  # noqa: E402
from market_platform_foundation.ui_api import screener_news  # noqa: E402
from market_platform_foundation.ui_api.screener_squeeze_sources import BackgroundCache  # noqa: E402
from market_platform_foundation.ui_api.screener_universes import UNIVERSES, universe_spec  # noqa: E402

NOW = datetime(2026, 9, 28, 14, 0, tzinfo=UTC).timestamp()
ROWS = {
    "US_EQUITIES": [{"instrument": {"instrument_id": "EQ:AAPL"}, "symbol": "AAPL", "company": "Apple Inc."},
                    {"instrument": {"instrument_id": "EQ:MSFT"}, "symbol": "MSFT", "company": "Microsoft Corp"}],
    "US_ETFS": [{"instrument": {"instrument_id": "ETF:SPY"}, "symbol": "SPY", "company": "SPDR S&P 500 ETF Trust"},
                {"instrument": {"instrument_id": "ETF:TLT"}, "symbol": "TLT", "company": "iShares 20+ Year Treasury Bond ETF"}],
    "FUTURES": [{"instrument": {"instrument_id": "FUT:CLZ6"}, "symbol": "CLZ6", "root": "CL", "company": "Crude Oil", "lead": True},
                {"instrument": {"instrument_id": "FUT:ESZ6"}, "symbol": "ESZ6", "root": "ES", "company": "E-mini S&P 500", "lead": True}],
    "BONDS": [{"instrument": {"instrument_id": "UST:1"}, "symbol": "91282CRF0", "cusip": "91282CRF0", "term": "10-Year",
               "company": "10-Year Note"}],
    "CRYPTO": [{"instrument": {"instrument_id": "CR:BTC"}, "symbol": "BTC/USD", "base_asset": "BTC", "quote_asset": "USD", "venue": "KRAKEN"},
               {"instrument": {"instrument_id": "CR:SOL"}, "symbol": "SOL/USD", "base_asset": "SOL", "quote_asset": "USD", "venue": "KRAKEN"}],
}


def finviz_row(title, tickers, date_et, url, source="Reuters"):
    return {"headline": title, "url": url, "tickers": tickers, "publisher_source": source, "provider": "FINVIZ_ELITE",
            "provider_news_id": "finviz:" + url.rsplit("/", 1)[-1], "published_time": date_et.replace(" ", "T") + "Z",
            "raw_fields": {"Date": date_et}, "received_time": "2026-09-28T13:59:00Z"}


FINVIZ = {"success": True, "error": None, "received_at": "2026-09-28T13:59:00Z", "items": [
    finviz_row("Apple unveils M5 MacBook lineup", ["AAPL"], "2026-09-28 09:30:00", "https://r.test/apple-m5"),
    finviz_row("Apple unveils M5 MacBook lineup", ["AAPL"], "2026-09-28 09:33:00", "https://y.test/apple-m5-copy", source="Yahoo"),
    finviz_row("Microsoft signs cloud deal with OpenAI rival", ["MSFT"], "2026-09-28 08:00:00", "https://r.test/msft-cloud"),
    finviz_row("Apple supplier warns on margins " + "x" * 220, ["AAPL"], "2026-09-26 10:00:00", "https://r.test/old"),
    finviz_row("SPY sees record inflows", ["SPY"], "2026-09-28 09:00:00", "https://r.test/spy"),
    finviz_row("Unlisted co news", ["ZZZZ"], "2026-09-28 09:00:00", "https://r.test/zzzz"),
]}
RSS_BODY = b"""<?xml version="1.0"?><rss><channel>
<item><title>Oil jumps as OPEC+ extends production cuts</title><link>https://o.test/opec</link><pubDate>Mon, 28 Sep 2026 12:00:00 +0000</pubDate></item>
<item><title>Treasury yields fall after soft CPI print</title><link>https://o.test/cpi</link><pubDate>Mon, 28 Sep 2026 12:30:00 +0000</pubDate></item>
<item><title>Bitcoin tops $120,000 as ETF inflows surge</title><link>https://o.test/btc</link><pubDate>Mon, 28 Sep 2026 13:00:00 +0000</pubDate></item>
<item><title>SOL Global Investments posts quarterly results</title><link>https://o.test/solglobal</link><pubDate>Mon, 28 Sep 2026 13:10:00 +0000</pubDate></item>
<item><title>Crypto PAC spends $11M on Ohio Senate race</title><link>https://o.test/pac</link><pubDate>Mon, 28 Sep 2026 13:15:00 +0000</pubDate></item>
<item><title>Heat wave grips Europe</title><link>https://o.test/heat</link><pubDate>Mon, 28 Sep 2026 13:20:00 +0000</pubDate></item>
</channel></rss>"""
FEEDS = (Feed("macro", "Wire", "https://feed.test/macro", "NEWS", ("FUTURES", "BONDS", "CRYPTO", "US_ETFS")),)


def loader(labels):
    def load(path):
        def classify(texts):
            out = []
            for text in texts:
                label = next((value for key, value in labels.items() if key in text), "neutral")
                probs = {"positive": 0.05, "neutral": 0.05, "negative": 0.05}
                probs[label] = 0.9
                out.append([{"label": k, "score": v} for k, v in probs.items()])
            return out
        return LoadedModel(classify, "ProsusAI/finbert", "rev001", str(path))
    return load


class FakeProvider:
    provider_id, model_id = "inference.test", "test-model-1"

    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls, self.prompts = text, error, 0, []

    def infer(self, packet, *, rendered_prompt, config):
        self.calls += 1
        self.prompts.append(rendered_prompt)
        if self.error:
            return ProviderInferenceResponse("", self.provider_id, self.model_id, error_code=self.error, error_message="x")
        ids = [article.event_id for article in packet.articles]
        text = self.text or json.dumps({
            "summary": "Two stories report the same Apple launch.",
            "observed_facts": [{"text": "Apple unveiled M5 MacBooks.", "refs": ids[:1]}],
            "derived_context": [], "uncertainties": ["Single launch story."], "conflicting_evidence": [],
            "potential_market_relevance": [{"text": "Product cycle news can matter to hardware revenue.", "refs": ids[:1]}]})
        return ProviderInferenceResponse(text, self.provider_id, self.model_id)


def service(*, sentiment=None, provider=None, finviz=None, env=None, chart=None, rss_env=None, newsapi=None, finnhub=None,
            clock=None, rss_body=RSS_BODY):
    env = env if env is not None else {}
    fake = provider

    def chart_fn(instrument_id, universe):
        if chart is not None:
            return chart
        bars = [{"start": f"2026-09-28T13:{m - 5:02d}:00Z", "end": f"2026-09-28T13:{m:02d}:00Z", "close": 100 + m / 10}
                for m in range(5, 60, 5)]
        return {"bars": {"bars": bars, "reason": None}}
    rows = {row["instrument"]["instrument_id"]: (universe, row) for universe, items in ROWS.items() for row in items}
    return ScreenerNewsService(
        finviz=lambda: finviz if finviz is not None else FINVIZ,
        rss=RssNewsSource(fetch=lambda url, headers, timeout: rss_body, env=(rss_env if rss_env is not None else {"IMP_NEWS_RSS_LIVE": "1"}).get,
                          clock=lambda: NOW, feeds=FEEDS),
        newsapi_factory=newsapi or (lambda: NewsApiClient(api_key="", live_enabled=False)),
        finnhub_factory=finnhub or (lambda: FinnhubNewsClient(api_key="", live_enabled=True)),
        sec=SecFilingNews(env=env.get), sentiment=sentiment or FinbertSentiment(model_path=""),
        catalog=lambda universe: (ROWS[universe], None),
        row_for=lambda instrument, universe: rows.get(instrument, (None, None))[1] if rows.get(instrument, (None,))[0] == universe else None,
        chart=chart_fn, synthesizer_factory=lambda: ScreenerSynthesizer(provider=fake, clock=clock or (lambda: NOW)),
        cache=BackgroundCache(clock=clock or (lambda: NOW), spawn=lambda job: job()), clock=clock or (lambda: NOW), wait_s=0.0,
        env=env.get)


# ------------------------------------------------------------ architecture
class ArchitectureTests(unittest.TestCase):
    def test_news_is_not_a_sixth_universe(self):
        self.assertEqual(list(UNIVERSES), ["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"])
        self.assertNotIn("NEWS", UNIVERSES)

    def test_news_panel_is_available_in_every_universe(self):
        for universe in UNIVERSES:
            self.assertIn("news", universe_spec(universe).panels)
        layout = validate_panel_layout({"version": 1, "open_panels": ["news"], "active_panel": "news", "dock_height": 300,
                                        "dockview_layout": None})
        self.assertEqual(layout["open_panels"], ["news"])

    def test_routes(self):
        self.assertEqual(policy_for_route("GET", "/screener/news").capability, "state.read")
        self.assertEqual(policy_for_route("GET", "/screener/news/instrument").capability, "state.read")
        self.assertEqual(policy_for_route("POST", "/screener/news/synthesis").capability, "state.write")


# ------------------------------------------------------------------- feed
class FeedTests(unittest.TestCase):
    def test_equity_feed_clusters_syndication_and_keeps_universe_scope(self):
        payload = service().feed(universe="US_EQUITIES")
        self.assertEqual(payload["schema_version"], "screener-news/1.0.0")
        self.assertEqual(payload["universe"], "US_EQUITIES")
        headlines = [story["headline"] for story in payload["stories"]]
        self.assertEqual(headlines, ["Apple unveils M5 MacBook lineup", "Microsoft signs cloud deal with OpenAI rival"])
        apple = payload["stories"][0]
        self.assertEqual((apple["source_count"], len(apple["sources"])), (2, 2))  # one story · two sources
        self.assertEqual(apple["published_at"], "2026-09-28T13:30:00Z")  # 09:30 ET, never read as UTC
        self.assertEqual(apple["matches"][0]["basis"], "PROVIDER_TICKER")
        self.assertEqual((payload["result_count"], payload["headline_count"]), (2, 3))
        self.assertNotIn("Unlisted co news", headlines)  # not in the universe
        assert_no_secrets_in_payload(payload)

    def test_provider_health_is_independent(self):
        payload = service().feed(universe="US_EQUITIES")
        states = {status["id"]: status["state"] for status in payload["providers"]}
        self.assertEqual(states["finviz"], "CURRENT")
        self.assertEqual(states["rss"], "NOT_APPLICABLE")  # the fake catalog has no equity feed
        self.assertEqual(states["newsapi"], "NOT_APPLICABLE")
        self.assertEqual(payload["sentiment_model"]["state"], "NOT_CONFIGURED")
        self.assertEqual(payload["state"], "CURRENT")

    def test_not_configured_is_not_no_news(self):
        payload = service(finviz={"success": False, "error": "NOT_CONFIGURED", "items": []}, rss_env={}).feed(universe="FUTURES")
        self.assertEqual(payload["state"], "NOT_CONFIGURED")
        self.assertEqual({s["id"]: s["state"] for s in payload["providers"]}["rss"], "LIVE_DISABLED")
        self.assertEqual(payload["stories"], [])

    def test_partial_provider_state(self):
        payload = service(finviz={"success": False, "error": "HTTP_429", "items": []}).feed(universe="FUTURES")
        self.assertEqual(payload["state"], "PARTIAL")
        finviz = next(status for status in payload["providers"] if status["id"] == "finviz")
        self.assertEqual((finviz["state"], finviz["reason"]), ("RATE_LIMITED", "HTTP_429"))

    def test_futures_bonds_crypto_etf_matching(self):
        futures = service().feed(universe="FUTURES")
        oil = next(story for story in futures["stories"] if "OPEC" in story["headline"])
        self.assertIn(("CLZ6", "UNDERLYING_MATCH"), {(m["symbol"], m["basis"]) for m in oil["matches"]})
        self.assertNotIn("Heat wave grips Europe", [story["headline"] for story in futures["stories"]])
        bonds = service().feed(universe="BONDS")
        self.assertEqual([story["headline"] for story in bonds["stories"]], ["Treasury yields fall after soft CPI print"])
        self.assertEqual(bonds["stories"][0]["matches"][0]["confidence"], "CONTEXT")
        crypto = service().feed(universe="CRYPTO")
        crypto_headlines = [story["headline"] for story in crypto["stories"]]
        self.assertIn("Bitcoin tops $120,000 as ETF inflows surge", crypto_headlines)
        self.assertNotIn("SOL Global Investments posts quarterly results", crypto_headlines)  # collision, ambiguous only
        sector = next(story for story in crypto["stories"] if story["headline"].startswith("Crypto PAC"))
        self.assertEqual([(m["instrument_id"], m["symbol"], m["basis"]) for m in sector["matches"]],
                         [(None, "Crypto sector", "MACRO_CONTEXT")])  # one sector match, not one per pair
        etfs = service().feed(universe="US_ETFS")
        self.assertIn("SPY sees record inflows", [story["headline"] for story in etfs["stories"]])
        self.assertIn("Treasury yields fall after soft CPI print", [story["headline"] for story in etfs["stories"]])

    def test_universe_matches_are_memoized_per_index(self):
        svc = service()
        first = svc.feed(universe="CRYPTO")
        memo = svc._indexes["CRYPTO"].matches
        self.assertTrue(memo)
        size = len(memo)
        second = svc.feed(universe="CRYPTO")
        self.assertEqual(len(memo), size)  # the warm request re-uses every event's matches
        self.assertEqual([s["matches"] for s in first["stories"]], [s["matches"] for s in second["stories"]])

    def test_window_sort_filters_and_paging(self):
        svc = service()
        self.assertEqual(svc.feed(universe="US_EQUITIES", window="1h")["result_count"], 1)
        wide = svc.feed(universe="US_EQUITIES", window="72h")
        self.assertEqual(wide["result_count"], 3)
        oldest = svc.feed(universe="US_EQUITIES", window="72h", sort="oldest")
        self.assertTrue(oldest["stories"][0]["headline"].startswith("Apple supplier"))
        self.assertEqual(svc.feed(universe="US_EQUITIES", sort="sources")["stories"][0]["source_count"], 2)
        self.assertEqual([s["id"] for s in wide["sorts"]], ["newest", "oldest", "sources", "relevance"])
        page = svc.feed(universe="US_EQUITIES", window="72h", limit=2)
        self.assertEqual((len(page["stories"]), page["has_more"], page["result_count"]), (2, True, 3))
        second = svc.feed(universe="US_EQUITIES", window="72h", limit=2, offset=2)
        self.assertEqual((len(second["stories"]), second["has_more"]), (1, False))
        by_instrument = svc.feed(universe="US_EQUITIES", instrument="EQ:MSFT")
        self.assertEqual([story["headline"] for story in by_instrument["stories"]], ["Microsoft signs cloud deal with OpenAI rival"])
        by_source = svc.feed(universe="FUTURES", source="rss")
        self.assertTrue(by_source["stories"])
        category = svc.feed(universe="FUTURES", category="macro.energy")
        self.assertEqual([story["headline"] for story in category["stories"]], ["Oil jumps as OPEC+ extends production cuts"])
        self.assertIn("macro.energy", {item["id"] for item in category["filters"]["categories"]})
        for bad in ({"window": "2d"}, {"sort": "best"}, {"sentiment": "BULLISH"}, {"limit": 0}, {"view": "cards"}):
            with self.assertRaises(ValueError):
                svc.feed(universe="US_EQUITIES", **bad)
        with self.assertRaises(ValueError):
            svc.feed(universe="NEWS")

    def test_sentiment_filter_needs_a_current_model_and_a_scored_story(self):
        unscored = service().feed(universe="US_EQUITIES", sentiment="POSITIVE")
        self.assertFalse(unscored["filters"]["sentiment"]["enabled"])
        self.assertEqual((unscored["filters"]["sentiment"]["scored"], unscored["filters"]["sentiment"]["unscored"]), (0, 2))
        self.assertEqual(unscored["filters"]["sentiment"]["hidden_unscored"], 0)
        self.assertIsNone(unscored["filters"]["applied"]["sentiment"])
        self.assertEqual(unscored["result_count"], 2)  # not silently filtered to zero
        self.assertEqual(unscored["stories"][0]["sentiment"]["state"], "NOT_CONFIGURED")
        model = FinbertSentiment(model_path=str(ROOT / "tests"), loader=loader({"unveils": "positive"}))
        scored = service(sentiment=model).feed(universe="US_EQUITIES", sentiment="POSITIVE")
        self.assertTrue(scored["filters"]["sentiment"]["enabled"])
        self.assertEqual([story["headline"] for story in scored["stories"]], ["Apple unveils M5 MacBook lineup"])
        self.assertEqual(scored["stories"][0]["sentiment"]["model_id"], "ProsusAI/finbert")
        self.assertIsNone(scored["filters"]["sentiment"]["reason"])
        self.assertEqual(scored["filters"]["sentiment"]["counts"], {"positive": 1, "neutral": 1, "negative": 0})

    def test_partial_sentiment_filter_hides_and_counts_unscored_stories(self):
        model = FinbertSentiment(model_path=str(ROOT / "tests"), loader=loader({"unveils": "positive"}))
        with mock.patch.object(screener_news, "MAX_SCORED_STORIES", 1):
            everything = service(sentiment=model).feed(universe="US_EQUITIES")
            filtered = service(sentiment=model).feed(universe="US_EQUITIES", sentiment="POSITIVE")
        sentiment = everything["filters"]["sentiment"]
        self.assertTrue(sentiment["enabled"])
        self.assertEqual(sentiment["reason"], "PARTIAL_SCORING")
        self.assertEqual((sentiment["scored"], sentiment["unscored"], sentiment["hidden_unscored"]), (1, 1, 0))
        self.assertEqual(everything["result_count"], 2)  # no filter applied: unscored stories stay visible
        self.assertEqual(filtered["filters"]["applied"]["sentiment"], "POSITIVE")
        self.assertEqual(filtered["filters"]["sentiment"]["hidden_unscored"], 1)
        self.assertTrue(all(story["sentiment"]["state"] == "SCORED" for story in filtered["stories"]))

    def test_grid_activity_counts_stories_and_tone_per_instrument(self):
        model = FinbertSentiment(model_path=str(ROOT / "tests"), loader=loader({"unveils": "positive"}))
        svc = service(sentiment=model)
        activity = svc.activity(universe="US_EQUITIES", instrument_ids=["EQ:AAPL", "EQ:MSFT", "EQ:NOPE", "EQ:AAPL"])
        self.assertEqual(activity["schema_version"], "screener-news-activity/1.0.0")
        self.assertEqual(activity["window"]["id"], "24h")
        instruments = activity["instruments"]
        self.assertEqual(set(instruments), {"EQ:AAPL", "EQ:MSFT"})  # no story → absent, never a zero row invented
        self.assertEqual(instruments["EQ:MSFT"]["count"], 1)
        self.assertEqual(instruments["EQ:AAPL"]["tone"]["positive"], 1)
        # The counts agree with the feed's own instrument filter.
        for instrument_id, row in instruments.items():
            self.assertEqual(row["count"], svc.feed(universe="US_EQUITIES", instrument=instrument_id)["result_count"])
            self.assertEqual(row["count"], sum(row["tone"].values()) + row["unscored"])
        wide = svc.activity(universe="US_EQUITIES", instrument_ids=["EQ:AAPL"], window="72h")
        self.assertGreaterEqual(wide["instruments"]["EQ:AAPL"]["count"], instruments["EQ:AAPL"]["count"])
        unscored = service().activity(universe="US_EQUITIES", instrument_ids=["EQ:MSFT"])["instruments"]["EQ:MSFT"]
        self.assertEqual((unscored["unscored"], sum(unscored["tone"].values())), (1, 0))
        for bad in ({"instrument_ids": []}, {"instrument_ids": [f"EQ:X{i}" for i in range(201)]}, {"instrument_ids": ["EQ:AAPL"], "window": "2d"}):
            with self.assertRaises(ValueError):
                svc.activity(universe="US_EQUITIES", **bad)
        with self.assertRaises(ValueError):
            svc.activity(universe="NEWS", instrument_ids=["EQ:AAPL"])

    def test_new_count_since_last_view_uses_publication_time(self):
        svc = service()
        self.assertIsNone(svc.feed(universe="US_EQUITIES")["new_count"])
        # Apple M5 published 13:30Z, Microsoft 12:00Z.
        self.assertEqual(svc.feed(universe="US_EQUITIES", since="2026-09-28T12:30:00Z")["new_count"], 1)
        self.assertEqual(svc.feed(universe="US_EQUITIES", since="2026-09-28T11:00:00Z", limit=1)["new_count"], 2)
        with self.assertRaises(ValueError):
            svc.feed(universe="US_EQUITIES", since="yesterday")

    def test_brief_is_deterministic_and_shows_coverage(self):
        brief = service().feed(universe="FUTURES", view="brief")["brief"]
        self.assertIn("Deterministic brief", brief["method"])
        self.assertGreaterEqual(brief["story_count"], 2)
        self.assertIn("Sparse coverage", brief["coverage_note"])
        self.assertTrue(any(group["category"]["id"] == "macro.energy" for group in brief["groups"]))
        self.assertIsNone(service().feed(universe="FUTURES")["brief"])


# ------------------------------------------------------------- instrument
class InstrumentTests(unittest.TestCase):
    def test_equity_instrument_panel(self):
        payload = service().instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")
        self.assertEqual(payload["schema_version"], "screener-news-instrument/1.0.0")
        self.assertEqual(payload["instrument"]["symbol"], "AAPL")
        self.assertEqual([story["headline"][:20] for story in payload["stories"]], ["Apple unveils M5 Mac", "Apple supplier warns"])
        self.assertEqual(payload["coverage"]["headline_count"], 3)
        providers = {status["id"]: status for status in payload["providers"]}
        self.assertEqual(providers["newsapi"]["state"], "LIVE_DISABLED")
        self.assertEqual(providers["finnhub"]["state"], "NOT_CONFIGURED")
        self.assertEqual(providers["sec_filings"]["state"], "LIVE_DISABLED")
        self.assertEqual(providers["finbert"]["state"], "NOT_CONFIGURED")
        self.assertEqual(providers["ai"]["state"], "NOT_CONFIGURED")
        self.assertEqual(payload["ai"]["state"], "NOT_CONFIGURED")
        self.assertEqual(payload["state"], "PARTIAL")
        self.assertEqual(payload["capability"]["state"], "PARTIAL")
        self.assertIn("PROVIDER_TICKER", payload["capability"]["match_bases"])
        self.assertEqual(payload["sentiment"]["state"], "NOT_CONFIGURED")
        self.assertIsNone(payload["sentiment"]["dominant"])
        texts = [item["text"] for item in payload["analysis"]["insufficient"]]
        self.assertTrue(any("No causal link" in text for text in texts))
        self.assertTrue(any("NewsAPI" in text for text in texts))
        assert_no_secrets_in_payload(payload)

    def test_sentiment_timeline_is_hourly_by_tone(self):
        sentiment = service().instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL", compact=True)["sentiment"]
        timeline = sentiment["timeline"]
        self.assertEqual(len(timeline), 72)
        self.assertEqual((timeline[0]["start"], timeline[-1]["start"]), ("2026-09-25T15:00:00Z", "2026-09-28T14:00:00Z"))
        self.assertEqual(timeline[70]["unscored"], 1)  # Apple M5, 13:30Z; model not configured
        self.assertEqual(timeline[23]["unscored"], 1)  # supplier story, Sep 26 14:00Z
        self.assertEqual(sum(sum(b[k] for k in ("positive", "neutral", "negative", "unscored")) for b in timeline), 2)
        self.assertEqual(sentiment["timeline_untimed"], 0)
        model = FinbertSentiment(model_path=str(ROOT / "tests"), loader=loader({"unveils": "positive"}))
        scored = service(sentiment=model).instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["sentiment"]["timeline"]
        self.assertEqual((scored[70]["positive"], scored[23]["neutral"]), (1, 1))

    def test_attention_windows_and_prior(self):
        attention = service().instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["attention"]
        windows = {item["id"]: item for item in attention["windows"]}
        self.assertEqual((windows["1h"]["headline_count"], windows["1h"]["story_count"]), (2, 1))
        self.assertEqual(windows["24h"]["prior_headline_count"], 1)  # the Sep 26 14:00Z story opens the prior 24h window
        self.assertEqual(attention["class"], "DERIVED")
        self.assertEqual(attention["state"], "PARTIAL")  # outage is coverage, never zero attention
        self.assertIn("outage", attention["method"])

    def test_post_headline_reaction_is_temporal_association(self):
        reaction = service().instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")["reaction"]
        self.assertEqual(reaction["state"], "CURRENT")
        item = reaction["items"][0]
        self.assertEqual(item["published_at"], "2026-09-28T13:30:00Z")
        self.assertEqual(item["reference"]["price"], 103.0)
        horizons = {h["id"]: h for h in item["horizons"]}
        self.assertEqual((horizons["+5m"]["state"], horizons["+5m"]["price"]), ("OBSERVED", 103.5))
        self.assertAlmostEqual(horizons["+15m"]["change_pct"], round((104.5 / 103.0 - 1) * 100, 3))
        self.assertEqual(horizons["+1h"]["state"], "PENDING")
        self.assertIn("not evidence that the story caused", reaction["note"])
        futures = service().instrument(universe="FUTURES", instrument_id="FUT:CLZ6")["reaction"]
        self.assertEqual(futures["state"], "NOT_SUPPORTED")
        no_bars = service(chart={"bars": {"bars": [], "reason": "BAR_SOURCE_UNAVAILABLE"}}).instrument(
            universe="US_EQUITIES", instrument_id="EQ:AAPL")["reaction"]
        self.assertEqual((no_bars["state"], no_bars["reason"]), ("UNAVAILABLE", "BAR_SOURCE_UNAVAILABLE"))

    def test_compact_preview_is_bounded_and_skips_reaction(self):
        compact = service().instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL", compact=True)
        self.assertLessEqual(len(compact["stories"]), 5)
        self.assertEqual(compact["reaction"]["state"], "NOT_SUPPORTED")

    def test_cross_universe_instruments(self):
        oil = service().instrument(universe="FUTURES", instrument_id="FUT:CLZ6")
        self.assertEqual([story["headline"] for story in oil["stories"]], ["Oil jumps as OPEC+ extends production cuts"])
        self.assertTrue(any("not contract-specific" in item["text"] for item in oil["analysis"]["insufficient"]))
        bond = service().instrument(universe="BONDS", instrument_id="UST:1")
        self.assertEqual(bond["capability"]["reason"], "ISSUER_LEVEL_CONTEXT_ONLY")
        self.assertEqual([story["headline"] for story in bond["stories"]], ["Treasury yields fall after soft CPI print"])
        sol = service().instrument(universe="CRYPTO", instrument_id="CR:SOL")
        self.assertEqual(sol["stories"], [])  # the SOL Global headline is a collision
        body = RSS_BODY.replace(b"</channel>", b"<item><title>SEC sues crypto exchange over unregistered listings</title>"
                                b"<link>https://o.test/sec</link><pubDate>Mon, 28 Sep 2026 13:40:00 +0000</pubDate></item></channel>")
        sol_regulation = service(rss_body=body).instrument(universe="CRYPTO", instrument_id="CR:SOL")
        self.assertEqual([story["headline"] for story in sol_regulation["stories"]],
                         ["SEC sues crypto exchange over unregistered listings"])  # sector regulatory event only
        btc = service().instrument(universe="CRYPTO", instrument_id="CR:BTC")
        self.assertIn("Bitcoin tops $120,000 as ETF inflows surge", [story["headline"] for story in btc["stories"]])

    def test_unknown_instrument_and_universe_mismatch(self):
        self.assertIsNone(service().instrument(universe="US_EQUITIES", instrument_id="EQ:NOPE"))
        self.assertIsNone(service().instrument(universe="CRYPTO", instrument_id="EQ:AAPL"))
        with self.assertRaises(ValueError):
            service().instrument(universe="US_EQUITIES", instrument_id="")

    def test_sentiment_summary_when_model_is_available(self):
        model = FinbertSentiment(model_path=str(ROOT / "tests"), loader=loader({"unveils": "positive", "warns": "negative"}))
        payload = service(sentiment=model).instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")
        summary = payload["sentiment"]
        self.assertEqual((summary["state"], summary["counts"], summary["dominant"]),
                         ("CURRENT", {"positive": 1, "neutral": 0, "negative": 1}, "MIXED"))
        self.assertEqual(summary["latest"]["label"], "POSITIVE")
        self.assertTrue(any("language, not a forecast" in item["text"] for item in payload["analysis"]["derived"]))

    def test_per_symbol_providers_are_cached_not_refetched(self):
        calls = []

        def getter(url, **kwargs):
            calls.append(url)
            return type("R", (), {"status_code": 200, "text": json.dumps([
                {"headline": "Apple expands buyback", "url": "https://f.test/1", "datetime": 1790600000, "id": 1,
                 "source": "Finnhub", "related": "AAPL"}]), "headers": {}})()
        svc = service(finnhub=lambda: FinnhubNewsClient(api_key="k", live_enabled=True, http_getter=getter, min_interval_s=0))
        svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")
        svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL", compact=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(svc.provider_requests["finviz"], 1)


# -------------------------------------------------------------- synthesis
class SynthesisTests(unittest.TestCase):
    def test_not_configured_without_a_provider_and_no_call(self):
        result = service().synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual((result["state"], result["reason"], result["synthesis"]), ("NOT_CONFIGURED", "ANTHROPIC_API_KEY_NOT_SET", None))
        self.assertEqual(result["epistemic_class"], "AI_SYNTHESIS")

    def test_structured_grounded_result_and_cache(self):
        provider = FakeProvider()
        svc = service(provider=provider)
        first = svc.synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual((first["state"], first["cache"], first["model_id"]), ("CURRENT", "MISS", "test-model-1"))
        self.assertTrue(set(first["synthesis"]["observed_facts"][0]["refs"]) <= set(first["story_ids"]))
        self.assertEqual(first["coverage"]["story_count"], 2)
        self.assertIn("newsapi", first["coverage"]["missing_providers"])
        second = svc.synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual((second["cache"], provider.calls), ("HIT", 1))
        self.assertIn("NEWS_SCREENER_SYNTHESIS", provider.prompts[0])
        self.assertIn("never proof that it caused", provider.prompts[0])

    def test_cache_invalidates_when_stories_change(self):
        provider = FakeProvider()
        svc = service(provider=provider)
        svc.synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        svc._cache = BackgroundCache(clock=lambda: NOW, spawn=lambda job: job())
        changed = {**FINVIZ, "items": FINVIZ["items"] + [finviz_row("Apple faces EU probe", ["AAPL"], "2026-09-28 09:50:00", "https://r.test/eu")]}
        svc._finviz = lambda: changed
        result = svc.synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual((result["cache"], provider.calls), ("MISS", 2))

    def test_malformed_ungrounded_and_unsupported_output_is_rejected(self):
        for text, reason in (("not json", "MALFORMED_JSON"),
                             (json.dumps({"summary": "x", "observed_facts": [{"text": "a", "refs": ["story:unknown"]}]}), "INVALID_OBSERVED_FACTS"),
                             (json.dumps({"summary": "AAPL will rally tomorrow.", "observed_facts": []}), "UNSUPPORTED_CERTAINTY")):
            result = service(provider=FakeProvider(text=text)).synthesis(universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
            self.assertEqual((result["state"], result["reason"], result["synthesis"]), ("INVALID_OUTPUT", reason, None))

    def test_provider_failure_and_insufficient_evidence(self):
        failed = service(provider=FakeProvider(error=InferenceErrorCode.PROVIDER_TIMEOUT)).synthesis(
            universe="US_EQUITIES", scope="INSTRUMENT", instrument_id="EQ:AAPL")
        self.assertEqual(failed["state"], "UNAVAILABLE")
        empty = service(provider=FakeProvider()).synthesis(universe="CRYPTO", scope="INSTRUMENT", instrument_id="CR:SOL")
        self.assertEqual(empty["state"], "INSUFFICIENT_EVIDENCE")
        universe = service(provider=FakeProvider()).synthesis(universe="FUTURES", scope="UNIVERSE")
        self.assertEqual(universe["state"], "CURRENT")
        # A universe synthesis reads one capped feed page; coverage still counts every matched story.
        with mock.patch.object(screener_news, "MAX_LIMIT", 1):
            capped = service(provider=FakeProvider()).synthesis(universe="FUTURES", scope="UNIVERSE")
        self.assertGreater(capped["coverage"]["story_count"], 1)
        self.assertLessEqual(capped["coverage"]["synthesized_story_count"], 1)
        self.assertEqual(service().feed(universe="FUTURES")["filters"]["sentiment"]["scored_cap"], screener_news.MAX_SCORED_STORIES)

    def test_certainty_guard(self):
        self.assertFalse(unsupported_certainty("Analysts upgraded Apple to Buy after the launch."))
        self.assertFalse(unsupported_certainty("A broad sell-off hit tech; the company expanded its buyback."))
        self.assertFalse(unsupported_certainty('The article says the stock "will rally" on demand.'))
        for text in ("BUY AAPL", "Investors should sell", "Returns are guaranteed", "Bitcoin will crash"):
            self.assertTrue(unsupported_certainty(text), text)
        synthesis, reason = parse_synthesis("```json\n" + json.dumps({"summary": "ok", "observed_facts": [{"text": "a", "refs": ["s1"]}]}) + "\n```", {"s1"})
        self.assertIsNone(reason)
        self.assertEqual(synthesis["observed_facts"], [{"text": "a", "refs": ["s1"]}])


class ProviderStatusTests(unittest.TestCase):
    def test_status_mapping(self):
        cases = {"LIVE_DISABLED": "LIVE_DISABLED", "NOT_CONFIGURED": "NOT_CONFIGURED", "HTTP_429": "RATE_LIMITED",
                 "DAILY_QUOTA_GUARD": "RATE_LIMITED", "HTTP_403": "AUTH_FAILED", "FINVIZ_NEWS_LOGIN_PAGE": "AUTH_FAILED",
                 "INVALID_JSON": "ERROR", "NETWORK_ERROR": "ERROR"}
        for error, state in cases.items():
            self.assertEqual(provider_status("newsapi", {"success": False, "error": error}, scope="INSTRUMENT")["state"], state, error)
        self.assertEqual(provider_status("newsapi", {"success": False, "error": "NOT_CONFIGURED"}, scope="INSTRUMENT")["reason"],
                         "NEWSAPI_API_KEY_NOT_SET")
        self.assertEqual(provider_status("x", None, scope="UNIVERSE", pending=True)["state"], "PENDING")

    def test_newsapi_daily_quota_guard(self):
        svc = service(newsapi=lambda: NewsApiClient(api_key="k", live_enabled=True, min_interval_s=0,
                                                    http_getter=lambda url, **kw: type("R", (), {"status_code": 200, "text": json.dumps({"status": "ok", "articles": []}), "headers": {}})()))
        svc._newsapi_day = (datetime.fromtimestamp(NOW, tz=UTC).date().isoformat(), 90)
        payload = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AAPL")
        newsapi = next(status for status in payload["providers"] if status["id"] == "newsapi")
        self.assertEqual((newsapi["state"], newsapi["reason"]), ("RATE_LIMITED", "DAILY_QUOTA_GUARD"))


if __name__ == "__main__":
    unittest.main()
