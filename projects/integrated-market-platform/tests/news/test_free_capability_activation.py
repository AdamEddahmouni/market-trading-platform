"""Free-capability activation: local FinBERT, NewsAPI Developer terms, Finnhub free Company News.

No network and no model download: loaders, HTTP getters, and the transformers module are fakes.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state.external_cache import imp_cache_dir, write_json_atomic  # noqa: E402
from market_platform_foundation.news import finbert_sentiment as fb  # noqa: E402
from market_platform_foundation.news.finbert_sentiment import (  # noqa: E402
    BASIS, MANIFEST_RELATIVE, MAX_TEXT_CHARS, FinbertSentiment, LoadedModel, default_model_path, summarize,
)
from market_platform_foundation.news.providers import (  # noqa: E402
    FINNHUB_PLAN_TERMS, NEWSAPI_PLAN_TERMS, FinnhubNewsClient, NewsApiClient,
)

LABEL_WORDS = {"raises": "positive", "record": "positive", "fine": "negative", "plunge": "negative"}


def _loader(*, seen=None, calls=None, gate=None):
    def load(path):
        if gate is not None:
            gate.wait(5)

        def classify(texts):
            if calls is not None:
                calls.append(list(texts))
            if seen is not None:
                seen.extend(texts)
            rows = []
            for text in texts:
                label = next((value for key, value in LABEL_WORDS.items() if key in text.lower()), "neutral")
                probs = {"positive": 0.05, "neutral": 0.05, "negative": 0.05}
                probs[label] = 0.9
                rows.append([{"label": key, "score": value} for key, value in probs.items()])
            return rows
        return LoadedModel(classify, "ProsusAI/finbert", "cfg123", str(path))
    return load


class FinbertActivationTests(unittest.TestCase):
    def setUp(self):
        self.path = str(ROOT / "tests")

    def test_fixture_semantics_and_derived_basis(self):
        model = FinbertSentiment(model_path=self.path, loader=_loader())
        texts = ["Company raises dividend after record profit", "Regulator fines bank; shares plunge",
                 "Company will hold its annual meeting", "Revenue beat estimates but guidance disappointed", "  "]
        scores = model.score(texts)
        self.assertEqual([score["label"] for score in scores], ["POSITIVE", "NEGATIVE", "NEUTRAL", "NEUTRAL", None])
        self.assertEqual(scores[4]["state"], "NOT_SCORED")        # empty text: no label, never neutral
        self.assertEqual({score.get("basis") for score in scores[:4]}, {BASIS})
        self.assertEqual(BASIS, "IMP_DERIVED_FINBERT")
        for score in scores[:4]:
            self.assertEqual(set(score["probabilities"]), {"positive", "neutral", "negative"})

    def test_malformed_unicode_is_scored_not_raised(self):
        # A lone surrogate from a provider used to raise UnicodeEncodeError and fail the whole feed.
        scores = FinbertSentiment(model_path=self.path, loader=_loader()).score(["Caf\u00e9 profit \udcff record high"])
        self.assertEqual((scores[0]["state"], scores[0]["label"]), ("SCORED", "POSITIVE"))

    def test_long_text_is_truncated_and_batched_in_one_call(self):
        seen, calls = [], []
        model = FinbertSentiment(model_path=self.path, loader=_loader(seen=seen, calls=calls))
        model.score(["Earnings rose. " * 500] + [f"headline {index}" for index in range(30)])
        self.assertEqual(len(calls), 1)                            # one batch, not one call per story
        self.assertLessEqual(max(len(text) for text in seen), MAX_TEXT_CHARS)
        self.assertEqual(model.load_count, 1)

    def test_background_load_reports_model_loading_then_scores(self):
        gate = threading.Event()
        model = FinbertSentiment(model_path=self.path, loader=_loader(gate=gate), background_load=True)
        first = model.score(["Company raises guidance"])
        self.assertEqual((first[0]["state"], first[0]["label"], first[0]["reason"]), ("NOT_SCORED", None, "MODEL_LOADING"))
        self.assertEqual(model.status()["reason"], "MODEL_LOADING")
        summary = summarize(first, model_status=model.status())
        self.assertEqual((summary["state"], summary["reason"], summary["dominant"]), ("UNAVAILABLE", "MODEL_LOADING", None))
        gate.set()
        for _ in range(200):
            if model.status()["loaded"]:
                break
            threading.Event().wait(0.01)
        self.assertEqual(model.score(["Company raises guidance"])[0]["label"], "POSITIVE")
        self.assertEqual(model.load_count, 1)

    def test_model_unavailable_is_a_state(self):
        model = FinbertSentiment(model_path=self.path, loader=lambda path: (_ for _ in ()).throw(ImportError("torch")))
        self.assertEqual(model.score(["x"])[0]["state"], "UNAVAILABLE")
        self.assertEqual(model.status()["reason"], "TRANSFORMERS_NOT_INSTALLED")

    def test_default_loader_is_local_files_only(self):
        calls = []

        class Auto:
            @staticmethod
            def from_pretrained(path, **kwargs):
                calls.append(kwargs)
                config = types.SimpleNamespace(id2label={0: "positive", 1: "negative", 2: "neutral"}, _name_or_path="")
                return types.SimpleNamespace(config=config)

        fake = types.ModuleType("transformers")
        fake.AutoTokenizer = Auto
        fake.AutoModelForSequenceClassification = Auto
        fake.pipeline = lambda *args, **kwargs: (lambda texts, **kw: [])
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules, {"transformers": fake}):
            snapshot = Path(directory) / "models--ProsusAI--finbert" / "snapshots" / "4556d130"
            snapshot.mkdir(parents=True)
            (snapshot / "config.json").write_text("{}", encoding="utf-8")
            loaded = fb._default_loader(snapshot)
        self.assertEqual([call.get("local_files_only") for call in calls], [True, True])
        self.assertEqual(loaded.model_id, "ProsusAI/finbert")      # from the hub cache layout, not a path

    def test_default_model_path_resolution_order(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            model_dir = Path(directory) / "model"
            model_dir.mkdir()
            env = {"IMP_CACHE_DIR": str(cache), "IMP_PROVIDER_ENV": str(Path(directory) / "none.env")}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(default_model_path(), (None, None))
                write_json_atomic(imp_cache_dir() / MANIFEST_RELATIVE, {"path": str(model_dir)})
                self.assertEqual(default_model_path(), (str(model_dir), "SETUP_MANIFEST"))
                with mock.patch.dict(os.environ, {"IMP_FINBERT_MODEL_PATH": "C:/explicit"}):
                    self.assertEqual(default_model_path(), ("C:/explicit", "ENVIRONMENT"))
                status = FinbertSentiment(model_path=str(model_dir), model_source="SETUP_MANIFEST").status()
                self.assertEqual((status["runtime"], status["model_source"], status["loaded"]),
                                 ("LOCAL_MODEL", "SETUP_MANIFEST", False))


def _response(status, payload, headers=None):
    return type("R", (), {"status_code": status, "text": json.dumps(payload), "headers": headers or {}})()


class NewsApiDeveloperTests(unittest.TestCase):
    def test_success_is_delayed_never_current(self):
        article = {"title": "Apple unveils M5", "description": "The new laptops ship next week.",
                   "url": "https://n.test/a", "publishedAt": "2026-09-27T12:00:00Z", "source": {"name": "Wire"}}
        client = NewsApiClient(api_key="k", live_enabled=True, min_interval_s=0,
                               http_getter=lambda url, **kw: _response(200, {"status": "ok", "articles": [article]}))
        result = client.fetch_news("Apple")
        self.assertEqual((result["state"], result["reason"]), ("DELAYED", "NEWSAPI_DEVELOPER_PLAN_24H_DELAY"))
        self.assertEqual(result["items"][0]["summary"], "The new laptops ship next week.")
        self.assertEqual((NEWSAPI_PLAN_TERMS["restriction"], NEWSAPI_PLAN_TERMS["timing"], NEWSAPI_PLAN_TERMS["cost_usd"]),
                         ("DEVELOPMENT_ONLY", "DELAYED_24H", 0))

    def test_no_request_without_opt_in_or_key(self):
        calls = []
        getter = lambda url, **kw: calls.append(url) or _response(200, {"status": "ok", "articles": []})  # noqa: E731
        self.assertEqual(NewsApiClient(api_key="k", live_enabled=False, http_getter=getter).fetch_news("A")["error"], "LIVE_DISABLED")
        self.assertEqual(NewsApiClient(api_key="", live_enabled=True, http_getter=getter).fetch_news("A")["error"], "NOT_CONFIGURED")
        self.assertEqual(calls, [])

    def test_explicit_empty_key_never_falls_back_to_the_operators_key(self):
        # Regression: api_key="" used to resolve the configured key, so test services built "live, no key"
        # clients that called the real providers with the operator's keys.
        calls = []
        getter = lambda url, **kw: calls.append(url) or _response(200, [])  # noqa: E731
        with mock.patch.dict(os.environ, {"NEWSAPI_API_KEY": "operator-key", "FINNHUB_API_KEY": "operator-key"}):
            self.assertEqual(NewsApiClient(api_key="", live_enabled=True, http_getter=getter).fetch_news("A")["error"],
                             "NOT_CONFIGURED")
            self.assertEqual(FinnhubNewsClient(api_key="", live_enabled=True, http_getter=getter).fetch_news("A")["error"],
                             "NOT_CONFIGURED")
            self.assertEqual(FinnhubNewsClient(live_enabled=True, http_getter=getter, min_interval_s=0).fetch_news("A")["success"],
                             True)                                   # no key argument still resolves the configured one
        self.assertEqual(len(calls), 1)


class FinnhubFreeTierTests(unittest.TestCase):
    def test_company_news_only_with_summary_and_identity(self):
        urls = []

        def getter(url, **kw):
            urls.append(url)
            return _response(200, [{"id": 7, "headline": "Apple supplier expands", "summary": "Plant opens.", "url": "https://f.test/7",
                                    "datetime": 1790000000, "source": "Wire", "related": "AAPL,TSM"}])
        result = FinnhubNewsClient(api_key="k", live_enabled=True, http_getter=getter, min_interval_s=0).fetch_news("aapl")
        self.assertEqual(urls, ["https://finnhub.io/api/v1/company-news"])   # never the premium news-sentiment endpoint
        item = result["items"][0]
        self.assertEqual((item["provider_news_id"], item["tickers"][:1], item["summary"]), ("finnhub:7", ["AAPL"], "Plant opens."))
        self.assertTrue(item["published_time"].endswith("Z"))
        self.assertNotIn("sentiment", item)                                  # Finnhub supplies stories, not sentiment
        self.assertEqual(FINNHUB_PLAN_TERMS["endpoint"], "company-news")

    def test_rate_limit_and_auth_failures_are_states(self):
        for status in (429, 401, 403):
            client = FinnhubNewsClient(api_key="k", live_enabled=True, min_interval_s=0,
                                       http_getter=lambda url, status=status, **kw: _response(status, {"error": "x"}))
            self.assertEqual(client.fetch_news("AAPL")["error"], f"HTTP_{status}")


if __name__ == "__main__":
    unittest.main()
