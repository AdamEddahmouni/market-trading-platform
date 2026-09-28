"""S11 news domain: contract/time semantics, dedupe + story clusters, taxonomy, cross-universe
matching, FinBERT sentiment, RSS/Atom, SEC filings, and provider adapters. Offline only."""

from __future__ import annotations

import json
import sys
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.news.contracts import PublicationTimeQuality  # noqa: E402
from market_platform_foundation.news.dedupe import dedupe_events  # noqa: E402
from market_platform_foundation.news.event_taxonomy import classify_text  # noqa: E402
from market_platform_foundation.news.finbert_sentiment import FinbertSentiment, LoadedModel, summarize  # noqa: E402
from market_platform_foundation.news.instrument_matching import (  # noqa: E402
    AMBIGUOUS, CONTEXT, EXACT, is_relevant, match_profile, profile_for_row,
)
from market_platform_foundation.news.normalize import normalize_raw_item  # noqa: E402
from market_platform_foundation.news.providers import FinnhubNewsClient, NewsApiClient  # noqa: E402
from market_platform_foundation.news.rss_feeds import Feed, RssNewsSource, aggregate_state, parse_feed, parse_feed_time  # noqa: E402
from market_platform_foundation.news.sec_filings_news import SecFilingNews, filing_headline  # noqa: E402
from market_platform_foundation.news.story_clusters import ClusterInput, canonical_url, cluster_stories  # noqa: E402

RETRIEVED = "2026-09-28T14:00:00Z"


def item(key, headline, url="", provider="finviz", native="", published="2026-09-28T13:00:00Z"):
    return ClusterInput(key=key, headline=headline, url=url, provider_id=provider, provider_native_id=native,
                        published_time=published, retrieved_time=RETRIEVED)


# ------------------------------------------------------------------ contract
class NewsContractTests(unittest.TestCase):
    def test_observed_article_keeps_source_url_summary_and_stable_id(self):
        raw = {"headline": "Apple unveils M5 chips", "url": "https://example.com/a", "summary": "Excerpt.",
               "published_time": "2026-09-28T13:30:00Z", "provider_news_id": "finviz:1", "publisher_source": "Reuters",
               "tickers": ["AAPL"]}
        first = normalize_raw_item(raw, provider_id="finviz", source_id="finviz_elite", retrieved_time=RETRIEVED)
        second = normalize_raw_item(raw, provider_id="finviz", source_id="finviz_elite", retrieved_time="2026-09-28T15:00:00Z")
        self.assertEqual(first.event_id, second.event_id)  # retrieval time never enters identity
        self.assertEqual((first.publisher_source, first.url, first.summary), ("Reuters", "https://example.com/a", "Excerpt."))
        self.assertEqual(first.published_time_quality, PublicationTimeQuality.KNOWN)
        serialized = first.to_dict()
        self.assertEqual(serialized["published_time"], "2026-09-28T13:30:00Z")
        self.assertEqual(serialized["retrieved_time"], RETRIEVED)
        self.assertTrue(serialized["raw_reference"])

    def test_unknown_publication_time_is_never_the_retrieval_time(self):
        event = normalize_raw_item({"headline": "Undated wire", "url": "https://x.test/u"}, provider_id="rss",
                                   source_id="cnbc_top", retrieved_time=RETRIEVED)
        self.assertEqual(event.published_time, "")
        self.assertEqual(event.published_time_quality, PublicationTimeQuality.UNKNOWN)
        self.assertIn("PUBLICATION_TIME_MISSING", event.quality_flags)

    def test_missing_identity_fails_closed(self):
        with self.assertRaises(ValueError):
            normalize_raw_item({"summary": "no identity"}, provider_id="rss", source_id="x", retrieved_time=RETRIEVED)


# ------------------------------------------------------- dedupe + clusters
class DedupeAndClusterTests(unittest.TestCase):
    def test_exact_provider_duplicate_is_removed_by_canonical_dedupe(self):
        raw = {"headline": "Same", "url": "https://x.test/s", "provider_news_id": "finviz:9", "published_time": "2026-09-28T13:00:00Z"}
        # The same provider item seen on two polls (different retrieval times) is one event.
        events = [normalize_raw_item(raw, provider_id="finviz", source_id="finviz_elite", retrieved_time=RETRIEVED),
                  normalize_raw_item(raw, provider_id="finviz", source_id="finviz_elite", retrieved_time="2026-09-28T14:03:00Z")]
        kept, duplicates = dedupe_events(events)
        self.assertEqual(len(kept), 1)
        self.assertEqual(duplicates, {kept[0].event_id: kept[0].event_id})

    def test_normalized_url_groups_copies(self):
        self.assertEqual(canonical_url("https://www.Example.com/Story/?utm=1#frag"), canonical_url("http://example.com/story"))
        clusters = cluster_stories([item("a", "Headline one", "https://www.example.com/story?utm=a"),
                                    item("b", "Completely different wording", "https://example.com/story/", provider="newsapi")])
        self.assertEqual([sorted(cluster.member_keys) for cluster in clusters], [["a", "b"]])

    def test_syndicated_same_headline_is_one_story_with_all_sources(self):
        clusters = cluster_stories([
            item("a", "Fed holds rates steady, signals two cuts this year - Reuters", "https://r.test/1"),
            item("b", "Fed holds rates steady, signals two cuts this year", "https://y.test/2", provider="rss",
                 published="2026-09-28T13:04:00Z"),
            item("c", "Fed holds rates steady, signals two cuts this year | CNBC", "https://c.test/3", provider="rss",
                 published="2026-09-28T13:06:00Z"),
        ])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(sorted(clusters[0].member_keys), ["a", "b", "c"])

    def test_same_headline_on_different_days_is_two_stories(self):
        clusters = cluster_stories([item("a", "Weekly jobless claims fall", published="2026-09-24T12:30:00Z"),
                                    item("b", "Weekly jobless claims fall", published="2026-09-25T12:30:00Z")])
        self.assertEqual(len(clusters), 2)
        self.assertNotEqual(clusters[0].cluster_id, clusters[1].cluster_id)

    def test_similar_but_distinct_developments_are_not_merged(self):
        clusters = cluster_stories([item("a", "Apple beats earnings estimates on strong iPhone sales"),
                                    item("b", "Apple misses revenue estimates as China iPhone sales slump")])
        self.assertEqual(len(clusters), 2)

    def test_cluster_id_is_stable_across_input_order_and_later_copies(self):
        base = [item("a", "Nvidia unveils new data center chip lineup", "https://a.test/1"),
                item("b", "Nvidia unveils new data center chip lineup", "https://b.test/2", published="2026-09-28T13:10:00Z")]
        first = cluster_stories(base)[0].cluster_id
        self.assertEqual(cluster_stories(list(reversed(base)))[0].cluster_id, first)
        later = base + [item("c", "Nvidia unveils new data center chip lineup", "https://c.test/3", published="2026-09-28T15:00:00Z")]
        self.assertEqual(cluster_stories(later)[0].cluster_id, first)
        self.assertTrue(first.startswith("story:"))


# ---------------------------------------------------------------- taxonomy
class TaxonomyTests(unittest.TestCase):
    def test_macro_categories_use_whole_words(self):
        ids = {category.id for category in classify_text("Powell signals rate cut as CPI cools")}
        self.assertTrue({"macro.fed_policy", "macro.inflation"} <= ids)
        self.assertNotIn("macro.fed_policy", {c.id for c in classify_text("Federated Hermes reports assets")})

    def test_group_filter_keeps_crypto_regulation_out_of_equities(self):
        text = "SEC opens probe into exchange listing practices"
        self.assertIn("crypto.regulation", {c.id for c in classify_text(text, groups=frozenset({"CRYPTO"}))})
        self.assertNotIn("crypto.regulation", {c.id for c in classify_text(text, groups=frozenset({"CORPORATE", "REGULATORY"}))})

    def test_empty_text_has_no_category(self):
        self.assertEqual(classify_text("", ""), ())


# ---------------------------------------------------------------- matching
class MatchingTests(unittest.TestCase):
    def test_equity_exact_ticker_entity_and_provider_tag(self):
        profile = profile_for_row("US_EQUITIES", {"instrument": {"instrument_id": "I:AAPL"}, "symbol": "AAPL", "company": "Apple Inc."})
        bases = {m.basis: m.confidence for m in match_profile(profile, headline="Apple (NASDAQ: AAPL) ships M5", tickers=["AAPL"])}
        self.assertEqual(bases["PROVIDER_TICKER"], EXACT)
        self.assertEqual(bases["EXACT_TICKER"], EXACT)
        self.assertEqual(bases["EXACT_ENTITY"], EXACT)

    def test_equity_bare_ticker_collision_is_ambiguous_only(self):
        profile = profile_for_row("US_EQUITIES", {"instrument": {"instrument_id": "I:ALL"}, "symbol": "ALL", "company": "Allstate Corp"})
        matches = match_profile(profile, headline="ALL eyes on the Fed this week")
        self.assertEqual({m.confidence for m in matches}, {AMBIGUOUS})
        self.assertFalse(is_relevant(matches))

    def test_equity_cik_filing_match(self):
        profile = profile_for_row("US_EQUITIES", {"instrument": {"instrument_id": "I:X"}, "symbol": "X", "company": "X Co", "cik": "0000320193"})
        self.assertIn("EXACT_ENTITY", {m.basis for m in match_profile(profile, headline="filed 8-K", cik="320193")})

    def test_etf_fund_ticker_and_underlying_theme(self):
        profile = profile_for_row("US_ETFS", {"instrument": {"instrument_id": "I:TLT"}, "symbol": "TLT",
                                              "company": "iShares 20+ Year Treasury Bond ETF"})
        matches = match_profile(profile, headline="Treasuries rally after soft CPI", categories=["macro.rates_treasury"])
        self.assertEqual({m.confidence for m in matches}, {CONTEXT})
        self.assertIn("UNDERLYING_MATCH", {m.basis for m in matches})
        self.assertIn("PROVIDER_TICKER", {m.basis for m in match_profile(profile, headline="x", tickers=["TLT"])})

    def test_futures_underlying_and_macro_context(self):
        profile = profile_for_row("FUTURES", {"instrument": {"instrument_id": "I:CL"}, "symbol": "CLZ6", "root": "CL"})
        matches = match_profile(profile, headline="Oil jumps as OPEC+ extends cuts", categories=["macro.energy"])
        self.assertEqual({m.basis for m in matches}, {"UNDERLYING_MATCH", "MACRO_CONTEXT"})
        self.assertTrue(all(m.confidence == CONTEXT for m in matches))
        unmapped = profile_for_row("FUTURES", {"instrument": {"instrument_id": "I:ZZ"}, "symbol": "ZZZ6", "root": "ZZ"})
        self.assertEqual(unmapped.capability, "PARTIAL")

    def test_treasury_issuer_and_cusip_match_without_materiality_claim(self):
        profile = profile_for_row("BONDS", {"instrument": {"instrument_id": "I:T"}, "symbol": "912828XX1", "cusip": "912828XX1",
                                            "term": "10-Year"})
        self.assertEqual(profile.capability, "PARTIAL")
        self.assertEqual(profile.capability_reason, "ISSUER_LEVEL_CONTEXT_ONLY")
        issuer = match_profile(profile, headline="Treasury auction of 10-year notes draws strong demand")
        self.assertEqual({m.confidence for m in issuer}, {CONTEXT})
        cusip = match_profile(profile, headline="Reopening of 912828XX1 announced")
        self.assertIn(("EXACT_CUSIP", EXACT), {(m.basis, m.confidence) for m in cusip})
        corporate = match_profile(profile, headline="Ford sells $2 billion of corporate bonds")
        self.assertEqual(corporate, [])

    def test_crypto_asset_pair_venue_and_collisions(self):
        sol = profile_for_row("CRYPTO", {"instrument": {"instrument_id": "I:SOL"}, "symbol": "SOL/USD", "base_asset": "SOL",
                                         "quote_asset": "USD", "venue": "KRAKEN"})
        self.assertEqual({m.basis for m in match_profile(sol, headline="Solana network upgrade goes live")}, {"ASSET_MATCH"})
        self.assertEqual({m.basis for m in match_profile(sol, headline="SOL/USD tops $200")}, {"PAIR_MATCH"})
        self.assertIn("EXACT_TICKER", {m.basis for m in match_profile(sol, headline="$SOL leads altcoins")})
        self.assertIn("VENUE_MATCH", {m.basis for m in match_profile(sol, headline="Kraken expands staking")})
        collision = match_profile(sol, headline="SOL Global Investments posts results")
        self.assertEqual({m.confidence for m in collision}, {AMBIGUOUS})
        self.assertFalse(is_relevant(collision))
        self.assertEqual(match_profile(sol, headline="Sol Meliá hotels expand"), [])
        btc = profile_for_row("CRYPTO", {"instrument": {"instrument_id": "I:BTC"}, "symbol": "BTC/USD", "base_asset": "BTC",
                                         "quote_asset": "USD", "venue": "KRAKEN"})
        self.assertEqual(match_profile(btc, headline="Bitcoin Cash hard fork scheduled"), [])
        self.assertIn(("ASSET_MATCH", EXACT), {(m.basis, m.confidence) for m in match_profile(btc, headline="Bitcoin tops $120,000")})

    def test_unmatched_headline(self):
        profile = profile_for_row("US_EQUITIES", {"instrument": {"instrument_id": "I:MSFT"}, "symbol": "MSFT", "company": "Microsoft Corp"})
        self.assertEqual(match_profile(profile, headline="Heat wave grips Europe"), [])


# --------------------------------------------------------------- sentiment
def _loader(outputs=None, *, fail=None, calls=None):
    def load(path):
        if fail:
            raise fail
        if calls is not None:
            calls.append(path)

        def classify(texts):
            rows = []
            for text in texts:
                label = (outputs or {}).get(text, "neutral")
                probs = {"positive": 0.1, "neutral": 0.1, "negative": 0.1}
                probs[label] = 0.8
                rows.append([{"label": key, "score": value} for key, value in probs.items()])
            return rows
        return LoadedModel(classify, "ProsusAI/finbert", "abc123def456", str(path))
    return load


class SentimentTests(unittest.TestCase):
    def setUp(self):
        self.path = str(ROOT / "tests")  # any existing directory; the loader is injected

    def test_not_configured_is_not_neutral_or_negative(self):
        model = FinbertSentiment(model_path="", loader=_loader())
        self.assertEqual(model.status()["state"], "NOT_CONFIGURED")
        scores = model.score(["Stock falls"])
        self.assertEqual((scores[0]["state"], scores[0]["label"]), ("NOT_CONFIGURED", None))
        summary = summarize(scores, model_status=model.status())
        self.assertEqual(summary["state"], "NOT_CONFIGURED")
        self.assertIsNone(summary["dominant"])
        self.assertEqual(summary["counts"], {"positive": 0, "neutral": 0, "negative": 0})

    def test_lazy_batch_probabilities_and_model_identity(self):
        calls = []
        model = FinbertSentiment(model_path=self.path, loader=_loader({"Beats estimates": "positive", "Shares plunge": "negative"}, calls=calls))
        self.assertEqual(calls, [])  # nothing loads until first use
        self.assertFalse(model.status()["loaded"])
        scores = model.score(["Beats estimates", "Shares plunge", "Company holds meeting"])
        self.assertEqual(len(calls), 1)
        self.assertEqual([score["label"] for score in scores], ["POSITIVE", "NEGATIVE", "NEUTRAL"])
        self.assertAlmostEqual(sum(scores[0]["probabilities"].values()), 1.0, places=3)
        self.assertEqual(scores[0]["model_id"], "ProsusAI/finbert")
        self.assertEqual(model.status()["model_revision"], "abc123def456")
        self.assertEqual(model.inference_calls, 1)
        model.score(["Beats estimates"])
        self.assertEqual(model.inference_calls, 1)  # cached

    def test_empty_text_is_not_scored(self):
        model = FinbertSentiment(model_path=self.path, loader=_loader())
        self.assertEqual(model.score(["   "])[0]["state"], "NOT_SCORED")

    def test_missing_runtime_and_load_failure_are_unavailable(self):
        missing = FinbertSentiment(model_path=self.path, loader=_loader(fail=ImportError("torch")))
        self.assertEqual(missing.score(["x"])[0]["state"], "UNAVAILABLE")
        self.assertEqual(missing.status()["reason"], "TRANSFORMERS_NOT_INSTALLED")
        broken = FinbertSentiment(model_path=self.path, loader=_loader(fail=OSError("corrupt")))
        broken.score(["x"])
        self.assertEqual((broken.status()["state"], broken.status()["reason"]), ("UNAVAILABLE", "MODEL_LOAD_FAILED"))
        self.assertEqual(FinbertSentiment(model_path=str(ROOT / "no-such-dir")).status()["reason"], "MODEL_PATH_NOT_FOUND")

    def test_inference_failure_is_error_not_label(self):
        def load(path):
            def classify(texts):
                raise RuntimeError("oom")
            return LoadedModel(classify, "finbert", "r", str(path))
        scores = FinbertSentiment(model_path=self.path, loader=load).score(["a", "b"])
        self.assertEqual({score["state"] for score in scores}, {"ERROR"})
        self.assertEqual({score["label"] for score in scores}, {None})

    def test_summary_counts_dominant_and_mixed(self):
        status = {"state": "CURRENT", "model_id": "finbert"}
        scored = lambda label: {"state": "SCORED", "label": label}  # noqa: E731
        summary = summarize([scored("POSITIVE"), scored("POSITIVE"), scored("NEGATIVE")], model_status=status)
        self.assertEqual((summary["dominant"], summary["counts"]["positive"], summary["state"]), ("POSITIVE", 2, "CURRENT"))
        tie = summarize([scored("POSITIVE"), scored("NEGATIVE"), {"state": "NOT_SCORED", "label": None}], model_status=status)
        self.assertEqual((tie["dominant"], tie["state"], tie["unscored"]), ("MIXED", "PARTIAL", 1))
        self.assertEqual(summarize([], model_status=status)["state"], "INSUFFICIENT_DATA")
        self.assertIn("not a return forecast", summary["method"])


# ------------------------------------------------------------------ RSS
RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
<item><title>Fed announces discount rate action</title><link>https://www.federalreserve.gov/a</link>
<pubDate>Mon, 28 Sep 2026 14:30:00 -0400</pubDate><description><![CDATA[<p>The Board <b>approved</b> ...</p>]]></description><guid>g1</guid></item>
<item><title>Undated notice here</title><link>https://www.federalreserve.gov/b</link></item>
<item><title>Bad date item</title><link>https://www.federalreserve.gov/c</link><pubDate>someday</pubDate></item>
<item><title>abc</title></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>A</title>
<entry><title>Crypto exchange halts withdrawals</title><link href="https://x.test/e1"/><updated>2026-09-28T10:00:00Z</updated><id>e1</id></entry>
</feed>"""
FEED = Feed("t", "Tester", "https://feed.test/rss", "NEWS", ("FUTURES",))


class RssTests(unittest.TestCase):
    def test_rss_and_atom_parse_with_utc_times_and_excerpts(self):
        items = parse_feed(RSS, FEED, retrieved_time=RETRIEVED)
        self.assertEqual([i["headline"] for i in items], ["Fed announces discount rate action", "Undated notice here", "Bad date item"])
        self.assertEqual(items[0]["published_time"], "2026-09-28T18:30:00Z")
        self.assertEqual(items[0]["summary"], "The Board approved ...")
        self.assertEqual((items[1]["published_time"], items[1]["quality_flags"]), ("", ["PUBLICATION_TIME_MISSING"]))
        self.assertEqual(items[2]["quality_flags"], ["PUBLICATION_TIME_MALFORMED"])
        atom = parse_feed(ATOM, FEED, retrieved_time=RETRIEVED)
        self.assertEqual((atom[0]["url"], atom[0]["published_time"]), ("https://x.test/e1", "2026-09-28T10:00:00Z"))

    def test_malformed_and_oversized_feeds_raise_classified_errors(self):
        with self.assertRaisesRegex(ValueError, "RSS_MALFORMED"):
            parse_feed(b"<rss><channel><item>", FEED, retrieved_time=RETRIEVED)
        with self.assertRaisesRegex(ValueError, "RSS_RESPONSE_TOO_LARGE"):
            parse_feed(b"x" * 2_000_001, FEED, retrieved_time=RETRIEVED)
        self.assertEqual(parse_feed_time("2026-09-28T10:00:00"), ("", ("PUBLICATION_TIME_NO_TIMEZONE",)))

    def test_source_gates_caches_and_reports_each_feed(self):
        calls = []

        def fetch(url, headers, timeout):
            calls.append((url, headers["User-Agent"]))
            if "bad" in url:
                raise urllib.error.HTTPError(url, 429, "slow down", {}, None)
            return RSS
        feeds = (FEED, Feed("bad", "Bad", "https://bad.test/rss", "NEWS", ("FUTURES",)),
                 Feed("sec", "SEC", "https://www.sec.gov/x.rss", "OFFICIAL_RELEASE", ("FUTURES",), requires_sec_user_agent=True))
        env = {"IMP_NEWS_RSS_LIVE": "1"}
        source = RssNewsSource(fetch=fetch, env=env.get, clock=lambda: 1000.0, feeds=feeds)
        result = source.collect("FUTURES")
        states = {feed["feed_id"]: feed["state"] for feed in result["feeds"]}
        self.assertEqual(states, {"t": "CURRENT", "bad": "RATE_LIMITED", "sec": "NOT_CONFIGURED"})
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(aggregate_state(result["feeds"])[0], "CURRENT")
        self.assertIn("PARTIAL_FEEDS", aggregate_state(result["feeds"])[1])
        source.collect("FUTURES")
        self.assertEqual(len(calls), 2)  # cached: no second request for either fetched feed
        disabled = RssNewsSource(fetch=fetch, env={}.get, feeds=feeds).collect("FUTURES")
        self.assertEqual(aggregate_state(disabled["feeds"]), ("LIVE_DISABLED", "IMP_NEWS_RSS_LIVE_NOT_SET"))

    def test_failed_refresh_keeps_last_good_items_marked_stale(self):
        clock = [1000.0]
        responses = [RSS, OSError("down")]

        def fetch(url, headers, timeout):
            value = responses.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        source = RssNewsSource(fetch=fetch, env={"IMP_NEWS_RSS_LIVE": "1"}.get, clock=lambda: clock[0], feeds=(FEED,))
        self.assertEqual(source.fetch(FEED).state, "CURRENT")
        clock[0] += 10_000
        stale = source.fetch(FEED)
        self.assertEqual((stale.state, stale.reason, len(stale.items)), ("STALE", "NETWORK_ERROR", 3))


# ------------------------------------------------------------------ SEC
class _FakeTransport:
    def __init__(self):
        self.urls = []

    def get(self, url, immutable=False):
        self.urls.append(url)
        if url.endswith("company_tickers.json"):
            return json.dumps({"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}).encode()
        return json.dumps({"cik": "320193", "name": "Apple Inc.", "filings": {"recent": {
            "accessionNumber": ["0000320193-26-000100", "0000320193-26-000099"], "form": ["8-K", "SD"],
            "filingDate": ["2026-09-28", "2026-09-27"], "reportDate": ["", ""],
            "acceptanceDateTime": ["2026-09-28T16:05:00.000Z", "2026-09-27T10:00:00.000Z"],
            "items": ["2.02,9.01", ""], "primaryDocument": ["a.htm", "b.htm"], "isXBRL": [0, 0]}}}).encode()


class SecFilingTests(unittest.TestCase):
    def test_gates(self):
        self.assertEqual(SecFilingNews(env={}.get).fetch("AAPL")["state"], "LIVE_DISABLED")
        self.assertEqual(SecFilingNews(env={"IMP_EDGAR_LIVE": "1"}.get).fetch("AAPL")["state"], "NOT_CONFIGURED")

    def test_recent_event_filings_are_official_filings_not_news(self):
        transport = _FakeTransport()
        sec = SecFilingNews(transport_factory=lambda: transport,
                            env={"IMP_EDGAR_LIVE": "1", "SEC_USER_AGENT": "IMP Test ops@example.com"}.get)
        result = sec.fetch("AAPL")
        self.assertEqual(len(result["items"]), 1)  # SD is not an event form
        filing = result["items"][0]
        self.assertEqual((filing["source_type"], filing["form_type"]), ("OFFICIAL_FILING", "8-K"))
        self.assertEqual(filing["published_time"], "2026-09-28T16:05:00Z")
        self.assertIn("filed 8-K", filing["headline"])
        self.assertTrue(filing["url"].startswith("https://www.sec.gov/Archives/"))
        sec.fetch("AAPL")
        self.assertEqual(len(transport.urls), 2)  # ticker map + submissions, both cached
        self.assertEqual(sec.fetch("ZZZZ")["reason"], "TICKER_NOT_IN_SEC_MAP")


# -------------------------------------------------------------- providers
class _Resp:
    def __init__(self, status, text):
        self.status_code, self.text, self.headers = status, text, {}


def _getter(status, body):
    def get(url, **kwargs):
        if isinstance(body, Exception):
            raise body
        return _Resp(status, body if isinstance(body, str) else json.dumps(body))
    return get


class ProviderAdapterTests(unittest.TestCase):
    def newsapi(self, status, body, **kw):
        return NewsApiClient(api_key=kw.get("key", "k"), live_enabled=kw.get("live", True), http_getter=_getter(status, body),
                             min_interval_s=0).fetch_news("AAPL")

    def finnhub(self, status, body):
        return FinnhubNewsClient(api_key="k", live_enabled=True, http_getter=_getter(status, body), min_interval_s=0).fetch_news("AAPL")

    def test_normal_bad_timestamp_and_empty(self):
        result = self.newsapi(200, {"status": "ok", "articles": [
            {"title": "Apple news", "url": "https://n.test/1", "publishedAt": "2026-09-28T13:00:00Z", "source": {"name": "Wire"}},
            {"title": "Odd time", "url": "https://n.test/2", "publishedAt": "not a date"}]})
        self.assertTrue(result["success"])
        self.assertEqual(result["items"][0]["published_time"], "2026-09-28T13:00:00Z")
        event = normalize_raw_item(result["items"][1], provider_id="newsapi", source_id="newsapi", retrieved_time=RETRIEVED)
        self.assertEqual(event.published_time_quality, PublicationTimeQuality.UNKNOWN)
        self.assertEqual(self.newsapi(200, {"status": "ok", "articles": []})["items"], [])
        finnhub = self.finnhub(200, [{"headline": "Hi", "url": "https://f.test/1", "datetime": "bad", "id": 7}])
        self.assertEqual(finnhub["items"][0]["published_time"], "")

    def test_rate_limit_auth_missing_malformed_and_failure(self):
        self.assertEqual(self.newsapi(429, "{}")["error"], "HTTP_429")
        self.assertEqual(self.newsapi(200, {}, key="")["error"], "NOT_CONFIGURED")
        self.assertEqual(self.newsapi(200, {}, live=False)["error"], "LIVE_DISABLED")
        self.assertEqual(self.newsapi(200, "{not json")["error"], "INVALID_JSON")
        self.assertEqual(self.newsapi(200, {"status": "error"})["error"], "API_ERROR")
        self.assertEqual(self.newsapi(200, OSError("down"))["error"], "NETWORK_ERROR")
        self.assertEqual(self.finnhub(200, {"error": "x"})["error"], "API_ERROR")


if __name__ == "__main__":
    unittest.main()
