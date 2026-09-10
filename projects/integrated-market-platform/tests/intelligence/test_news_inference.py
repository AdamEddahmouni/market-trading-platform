"""Comprehensive tests for canonical news intelligence inference boundary."""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.analyzer import NewsIntelligenceAnalyzer  # noqa: E402
from market_platform_foundation.intelligence.inference.config import (  # noqa: E402
    IntelligenceInferenceConfig,
    verify_inference_config,
)
from market_platform_foundation.intelligence.inference.contracts import (  # noqa: E402
    ImpactHorizon,
    InferenceStatus,
    IntelligenceTaskType,
    MarketImpactLevel,
    ParsingStatus,
    SentimentLabel,
)
from market_platform_foundation.intelligence.inference.errors import InferenceErrorCode  # noqa: E402
from market_platform_foundation.intelligence.inference.hashing import (  # noqa: E402
    compute_input_hash,
    prompt_hash,
)
from market_platform_foundation.intelligence.inference.input_builder import (  # noqa: E402
    build_input_packet,
    select_articles_deterministic,
)
from market_platform_foundation.intelligence.inference.parsing import parse_structured_output  # noqa: E402
from market_platform_foundation.intelligence.inference.prompts import PromptRegistry  # noqa: E402
from market_platform_foundation.intelligence.inference.provider import (  # noqa: E402
    AnthropicInferenceProvider,
    FixtureInferenceProvider,
    render_prompt_for_packet,
)
from market_platform_foundation.intelligence.inference.records import (  # noqa: E402
    InMemoryInferenceRecordRepository,
)
from market_platform_foundation.intelligence.inference.replay import IntelligenceReplayHarness  # noqa: E402
from market_platform_foundation.news.config import default_pipeline_config  # noqa: E402
from market_platform_foundation.news.contracts import (  # noqa: E402
    NewsArticleEvent,
    PublicationTimeQuality,
)
from market_platform_foundation.news.fixture_provider import FixtureNewsProvider  # noqa: E402
from market_platform_foundation.news.replay import NewsReplayHarness  # noqa: E402
from market_platform_foundation.news.service import NewsIntelligenceService  # noqa: E402
from market_platform_foundation.news.timestamps import epoch_ns_from_iso, is_observable_at  # noqa: E402


def _event(
    *,
    event_id: str = "evt-1",
    published: str = "2026-09-09T12:00:00Z",
    retrieved: str = "2026-09-09T12:01:00Z",
    headline: str = "ACME reports earnings beat",
    source_id: str = "fixture_wire",
) -> NewsArticleEvent:
    return NewsArticleEvent(
        event_id=event_id,
        provider_id="news.fixture",
        provider_native_id=event_id,
        source_id=source_id,
        published_time=published,
        published_time_quality=PublicationTimeQuality.KNOWN,
        retrieved_time=retrieved,
        headline=headline,
        summary="Quarterly earnings exceeded expectations.",
        instrument_linkages=(),
    )


class ContractTests(unittest.TestCase):
    def test_sentiment_enum_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            SentimentLabel("HYPER_BULLISH")

    def test_market_impact_and_horizon_enums(self) -> None:
        self.assertEqual(MarketImpactLevel.MODERATE.value, "MODERATE")
        self.assertEqual(ImpactHorizon.SHORT_TERM.value, "SHORT_TERM")

    def test_confidence_is_model_reported_only(self) -> None:
        payload = json.dumps(
            {
                "sentiment_label": "NEUTRAL",
                "sentiment_score": 0.0,
                "rationale": "neutral",
                "model_confidence": 0.5,
                "warnings": [],
            }
        )
        output, status, _ = parse_structured_output(payload)
        self.assertEqual(status, ParsingStatus.VALID)
        assert output is not None
        self.assertEqual(output.confidence_kind.value, "MODEL_REPORTED_CONFIDENCE")


class PromptTests(unittest.TestCase):
    def test_prompt_hash_stable(self) -> None:
        registry = PromptRegistry()
        prompt = registry.get_for_task(IntelligenceTaskType.NEWS_SENTIMENT)
        self.assertEqual(prompt.content_hash, prompt.content_hash)
        self.assertEqual(len(prompt.content_hash), 64)

    def test_prompt_includes_as_of_and_prohibitions(self) -> None:
        registry = PromptRegistry()
        prompt = registry.get_for_task(IntelligenceTaskType.NEWS_MARKET_IMPACT)
        self.assertIn("{{as_of}}", prompt.template)
        self.assertIn("Do NOT search the web", prompt.template)
        self.assertIn("Do NOT generate trading orders", prompt.template)
        self.assertIn("LIMIT_PRICE", prompt.template)

    def test_version_change_alters_hash(self) -> None:
        registry = PromptRegistry()
        prompt = registry.get_for_task(IntelligenceTaskType.NEWS_CATALYST_ANALYSIS)
        altered = prompt_hash(prompt_id=prompt.prompt_id, version="9.9.9", template=prompt.template)
        self.assertNotEqual(prompt.content_hash, altered)


class ProviderTests(unittest.TestCase):
    def test_fixture_provider_valid_response(self) -> None:
        provider = FixtureInferenceProvider()
        analyzer = NewsIntelligenceAnalyzer(provider=provider)
        outcome = analyzer.analyze(
            [_event()],
            as_of="2026-09-09T14:00:00Z",
            pipeline_config=default_pipeline_config(),
        )
        self.assertIsNotNone(outcome.result)
        assert outcome.result is not None
        self.assertEqual(outcome.result.status, InferenceStatus.SUCCESS)
        self.assertEqual(outcome.result.provider_id, "inference.fixture")

    def test_fixture_malformed_response_fails(self) -> None:
        provider = FixtureInferenceProvider(simulate_malformed=True)
        analyzer = NewsIntelligenceAnalyzer(provider=provider)
        outcome = analyzer.analyze(
            [_event()],
            as_of="2026-09-09T14:00:00Z",
            pipeline_config=default_pipeline_config(),
        )
        self.assertIsNotNone(outcome.failure)
        assert outcome.failure is not None
        self.assertEqual(outcome.failure.error_code, InferenceErrorCode.OUTPUT_SCHEMA_INVALID.value)

    def test_fixture_timeout(self) -> None:
        provider = FixtureInferenceProvider(simulate_timeout=True)
        analyzer = NewsIntelligenceAnalyzer(provider=provider)
        outcome = analyzer.analyze(
            [_event()],
            as_of="2026-09-09T14:00:00Z",
            pipeline_config=default_pipeline_config(),
        )
        assert outcome.failure is not None
        self.assertEqual(outcome.failure.error_code, InferenceErrorCode.PROVIDER_TIMEOUT.value)

    def test_invalid_enum_rejected(self) -> None:
        raw = json.dumps({"sentiment_label": "YOLO", "rationale": "bad"})
        _, status, _ = parse_structured_output(raw)
        self.assertEqual(status, ParsingStatus.INVALID_ENUM)

    def test_score_out_of_range_rejected(self) -> None:
        raw = json.dumps(
            {
                "sentiment_label": "NEUTRAL",
                "sentiment_score": 9.9,
                "rationale": "bad",
            }
        )
        _, status, _ = parse_structured_output(raw)
        self.assertEqual(status, ParsingStatus.SCORE_OUT_OF_RANGE)

    def test_trading_terms_rejected(self) -> None:
        raw = json.dumps({"sentiment_label": "BULLISH", "rationale": "Recommend BUY now"})
        _, status, _ = parse_structured_output(raw)
        self.assertEqual(status, ParsingStatus.INVALID_ENUM)

    def test_anthropic_provider_missing_key(self) -> None:
        provider = AnthropicInferenceProvider(api_key="")
        packet_builder = build_input_packet(
            events=[_event()],
            as_of="2026-09-09T14:00:00Z",
            as_of_ns=epoch_ns_from_iso("2026-09-09T14:00:00Z") or 0,
            task_type=IntelligenceTaskType.NEWS_SENTIMENT,
            pipeline_config=default_pipeline_config(),
            inference_config=IntelligenceInferenceConfig(provider_id=provider.provider_id),
        )
        response = provider.infer(
            packet_builder,
            rendered_prompt=render_prompt_for_packet(packet_builder),
            config=IntelligenceInferenceConfig(),
        )
        self.assertEqual(response.error_code, InferenceErrorCode.PROVIDER_AUTH_FAILURE)


class EventTimeSafetyTests(unittest.TestCase):
    def test_future_retrieved_event_rejected(self) -> None:
        provider = FixtureInferenceProvider()
        analyzer = NewsIntelligenceAnalyzer(provider=provider)
        future = _event(event_id="future", retrieved="2026-09-09T16:00:00Z")
        outcome = analyzer.analyze(
            [future],
            as_of="2026-09-09T14:00:00Z",
            pipeline_config=default_pipeline_config(),
        )
        assert outcome.failure is not None
        self.assertEqual(outcome.failure.error_code, InferenceErrorCode.UNOBSERVABLE_EVENT.value)

    def test_replay_curated_set_matches_observable(self) -> None:
        provider = FixtureNewsProvider()
        events = provider.fetch_events()
        as_of = "2026-09-09T14:00:00Z"
        as_of_ns = epoch_ns_from_iso(as_of) or 0
        replay = NewsReplayHarness().replay(events, as_of=as_of, config=default_pipeline_config())
        for event in replay.accepted_events:
            self.assertTrue(is_observable_at(event, as_of_ns))


class ReplayTests(unittest.TestCase):
    def test_identical_replay_produces_identical_hashes(self) -> None:
        events = FixtureNewsProvider().fetch_events()
        config = default_pipeline_config()
        inf = IntelligenceInferenceConfig(max_articles=3)
        harness = IntelligenceReplayHarness()
        first = harness.replay(events, as_of="2026-09-09T14:00:00Z", pipeline_config=config, inference_config=inf)
        second = harness.replay(events, as_of="2026-09-09T14:00:00Z", pipeline_config=config, inference_config=inf)
        assert first.outcome.result is not None
        assert second.outcome.result is not None
        self.assertEqual(first.outcome.record.input_packet.input_hash, second.outcome.record.input_packet.input_hash)
        self.assertEqual(first.outcome.record.input_packet.prompt_hash, second.outcome.record.input_packet.prompt_hash)


class InputLimitTests(unittest.TestCase):
    def test_max_articles_truncation_recorded(self) -> None:
        events = [
            _event(event_id=f"evt-{idx}", retrieved=f"2026-09-09T12:{idx:02d}:00Z")
            for idx in range(10)
        ]
        as_of_ns = epoch_ns_from_iso("2026-09-09T14:00:00Z") or 0
        articles, truncated, reason = select_articles_deterministic(
            events,
            as_of_ns=as_of_ns,
            config=IntelligenceInferenceConfig(max_articles=3),
        )
        self.assertTrue(truncated)
        self.assertEqual(reason, "MAX_ARTICLES")
        self.assertEqual(len(articles), 3)

    def test_deterministic_ordering_stable(self) -> None:
        events = [
            _event(event_id="a", retrieved="2026-09-09T12:01:00Z"),
            _event(event_id="b", retrieved="2026-09-09T12:02:00Z"),
            _event(event_id="c", retrieved="2026-09-09T12:03:00Z"),
        ]
        as_of_ns = epoch_ns_from_iso("2026-09-09T14:00:00Z") or 0
        first, _, _ = select_articles_deterministic(events, as_of_ns=as_of_ns, config=IntelligenceInferenceConfig())
        second, _, _ = select_articles_deterministic(events, as_of_ns=as_of_ns, config=IntelligenceInferenceConfig())
        self.assertEqual([a.event_id for a in first], [a.event_id for a in second])


class ProvenanceTests(unittest.TestCase):
    def test_inference_record_contains_provenance(self) -> None:
        provider = FixtureInferenceProvider()
        analyzer = NewsIntelligenceAnalyzer(provider=provider)
        event = _event()
        outcome = analyzer.analyze(
            [event],
            as_of="2026-09-09T14:00:00Z",
            pipeline_config=default_pipeline_config(),
        )
        assert outcome.result is not None
        result = outcome.result
        self.assertIn(event.event_id, result.source_event_ids)
        self.assertTrue(result.prompt_id)
        self.assertTrue(result.prompt_hash)
        self.assertTrue(result.input_hash)
        self.assertEqual(result.provider_id, "inference.fixture")
        self.assertFalse(result.execution_authority)


class SafetyTests(unittest.TestCase):
    def test_analyzer_has_no_broker_imports(self) -> None:
        module = importlib.import_module("market_platform_foundation.intelligence.inference.analyzer")
        forbidden_modules = (
            "market_platform_foundation.paper",
            "market_platform_foundation.broker",
            "market_platform_foundation.execution",
        )
        for name, value in vars(module).items():
            if isinstance(value, type) or callable(value):
                mod = getattr(value, "__module__", "")
                for forbidden in forbidden_modules:
                    self.assertNotIn(forbidden, mod)

    def test_news_service_still_read_only(self) -> None:
        payload = NewsIntelligenceService().query_fixture_pack(
            as_of="2026-09-09T14:00:00Z",
            config=default_pipeline_config(),
        )
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["execution_authority"])
        self.assertFalse(payload["ai_authority"])


class CacheTests(unittest.TestCase):
    def test_cache_reuses_prior_inference(self) -> None:
        repo = InMemoryInferenceRecordRepository()
        provider = FixtureInferenceProvider()
        analyzer = NewsIntelligenceAnalyzer(provider=provider, repository=repo)
        config = IntelligenceInferenceConfig(enable_cache=True)
        pipeline = default_pipeline_config()
        event = _event()
        first = analyzer.analyze([event], as_of="2026-09-09T14:00:00Z", pipeline_config=pipeline, inference_config=config)
        second = analyzer.analyze([event], as_of="2026-09-09T14:00:00Z", pipeline_config=pipeline, inference_config=config)
        self.assertFalse(first.record.cache_hit)
        self.assertTrue(second.record.cache_hit)


class ConfigTests(unittest.TestCase):
    def test_verify_inference_config(self) -> None:
        issues = verify_inference_config(IntelligenceInferenceConfig(max_articles=0))
        self.assertIn("MAX_ARTICLES_INVALID", issues)


class InputHashTests(unittest.TestCase):
    def test_input_hash_changes_with_content(self) -> None:
        as_of_ns = epoch_ns_from_iso("2026-09-09T14:00:00Z") or 0
        base = build_input_packet(
            events=[_event()],
            as_of="2026-09-09T14:00:00Z",
            as_of_ns=as_of_ns,
            task_type=IntelligenceTaskType.NEWS_SENTIMENT,
            pipeline_config=default_pipeline_config(),
            inference_config=IntelligenceInferenceConfig(),
        )
        changed = build_input_packet(
            events=[_event(headline="Different headline")],
            as_of="2026-09-09T14:00:00Z",
            as_of_ns=as_of_ns,
            task_type=IntelligenceTaskType.NEWS_SENTIMENT,
            pipeline_config=default_pipeline_config(),
            inference_config=IntelligenceInferenceConfig(),
        )
        self.assertNotEqual(base.input_hash, changed.input_hash)
        self.assertEqual(base.input_hash, compute_input_hash(base))


if __name__ == "__main__":
    unittest.main()
