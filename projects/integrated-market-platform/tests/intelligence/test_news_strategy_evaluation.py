"""Comprehensive tests for news intelligence strategy evaluation laboratory."""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.contracts import (  # noqa: E402
    InferenceRecord,
    InferenceStatus,
    IntelligenceInputPacket,
    IntelligenceResult,
    IntelligenceTaskType,
    ParsingStatus,
    SentimentLabel,
    StructuredIntelligenceOutput,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.config import (  # noqa: E402
    EvaluationConfig,
    verify_evaluation_config,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.contracts import (  # noqa: E402
    EvaluationDecision,
    EvaluationShadowRecord,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.errors import (  # noqa: E402
    EvaluationError,
    EvaluationErrorCode,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.evaluator import (  # noqa: E402
    NewsStrategyEvaluator,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.features import (  # noqa: E402
    assert_events_observable_at,
    assert_inference_observable_at,
    build_feature_snapshot,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.fixture_loader import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
    load_fixture_pack,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.market_data import (  # noqa: E402
    FixtureMarketDataProvider,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.policies import (  # noqa: E402
    PolicyRegistry,
    decision_to_units,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.replay import (  # noqa: E402
    EvaluationReplayHarness,
)
from market_platform_foundation.intelligence.news_strategy_evaluation.shadow import (  # noqa: E402
    assert_not_executable,
    build_shadow_record,
)
from market_platform_foundation.news.contracts import (  # noqa: E402
    NewsArticleEvent,
    PublicationTimeQuality,
)
from market_platform_foundation.news.timestamps import epoch_ns_from_iso, is_observable_at  # noqa: E402


def _event(
    *,
    event_id: str = "evt-1",
    published: str = "2026-09-09T12:00:00Z",
    retrieved: str = "2026-09-09T12:01:00Z",
    headline: str = "US CPI inflation cooler than expected",
) -> NewsArticleEvent:
    return NewsArticleEvent(
        event_id=event_id,
        provider_id="news.fixture",
        provider_native_id=event_id,
        source_id="globe_newswire",
        published_time=published,
        published_time_quality=PublicationTimeQuality.KNOWN,
        retrieved_time=retrieved,
        headline=headline,
        summary=headline,
        instrument_linkages=(),
    )


class ContractTests(unittest.TestCase):
    def test_evaluation_decision_non_executable_fields(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        decision = next(
            s.baseline_decision for s in report.sample_results if s.baseline_decision is not None
        )
        body = decision.to_dict()
        self.assertTrue(body["simulation_only"])
        self.assertFalse(body["execution_authority"])
        self.assertNotIn("order_id", body)
        self.assertNotIn("submit", body)

    def test_shadow_record_safety(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        decision = next(
            s.enhanced_decision for s in report.sample_results if s.enhanced_decision is not None
        )
        shadow = build_shadow_record(decision, recorded_at=decision.as_of)
        assert_not_executable(shadow)
        self.assertFalse(shadow.execution_authority)
        self.assertTrue(shadow.simulation_only)


class EventTimeSafetyTests(unittest.TestCase):
    def test_future_news_rejected(self) -> None:
        future = _event(retrieved="2026-09-09T15:00:00Z")
        with self.assertRaises(EvaluationError) as ctx:
            assert_events_observable_at([future], "2026-09-09T14:00:00Z")
        self.assertEqual(ctx.exception.code, EvaluationErrorCode.FUTURE_NEWS_LEAK)

    def test_future_inference_rejected(self) -> None:
        packet = IntelligenceInputPacket(
            input_id="inp",
            task_type=IntelligenceTaskType.NEWS_MARKET_IMPACT,
            as_of="2026-09-09T14:00:00Z",
            articles=(),
            instrument_ids=("ES",),
            prompt_id="news.market_impact.v1",
            prompt_version="1.0.0",
            prompt_hash="X",
            output_schema_version="intelligence/inference/output/1.0.0",
            model_policy_id="fixture",
        )
        result = IntelligenceResult(
            result_id="res",
            input_id="inp",
            status=InferenceStatus.SUCCESS,
            task_type=IntelligenceTaskType.NEWS_MARKET_IMPACT,
            as_of="2026-09-09T14:00:00Z",
            output=StructuredIntelligenceOutput(sentiment_label=SentimentLabel.BULLISH),
            parsing_status=ParsingStatus.VALID,
            completed_time="2026-09-09T15:00:00Z",
        )
        record = InferenceRecord(record_id="rec", input_packet=packet, result=result)
        with self.assertRaises(EvaluationError) as ctx:
            assert_inference_observable_at(record, "2026-09-09T14:00:00Z")
        self.assertEqual(ctx.exception.code, EvaluationErrorCode.FUTURE_INFERENCE_LEAK)

    def test_fixture_excludes_future_news_sample(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        sample = next(s for s in report.sample_results if s.sample_id == "eval-007")
        self.assertTrue(sample.excluded)


class BaselineComparabilityTests(unittest.TestCase):
    def test_policies_registered(self) -> None:
        registry = PolicyRegistry()
        baseline = registry.get("news_deterministic_baseline", "1.0.0")
        enhanced = registry.get("news_ai_enhanced", "1.0.0")
        self.assertEqual(enhanced.comparable_baseline_for, baseline.policy_id)

    def test_baseline_differs_from_enhanced_on_fixture(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        sample = next(s for s in report.sample_results if s.sample_id == "eval-010")
        self.assertFalse(sample.excluded)
        self.assertIsNotNone(sample.baseline_decision)
        self.assertIsNotNone(sample.enhanced_decision)
        self.assertEqual(sample.baseline_decision.decision, EvaluationDecision.NEUTRAL)
        self.assertEqual(
            sample.enhanced_decision.decision,
            EvaluationDecision.POSITIVE_DIRECTIONAL_BIAS,
        )


class PolicyTests(unittest.TestCase):
    def test_config_hash_stable(self) -> None:
        config = EvaluationConfig()
        self.assertEqual(config.config_hash(), config.config_hash())

    def test_decision_to_units(self) -> None:
        self.assertEqual(decision_to_units(EvaluationDecision.POSITIVE_DIRECTIONAL_BIAS), 1)
        self.assertEqual(decision_to_units(EvaluationDecision.NEGATIVE_DIRECTIONAL_BIAS), -1)
        self.assertEqual(decision_to_units(EvaluationDecision.NEUTRAL), 0)


class ReplayTests(unittest.TestCase):
    def test_fixture_replay_deterministic(self) -> None:
        result = EvaluationReplayHarness().replay(iterations=3)
        self.assertTrue(result.to_dict()["deterministic"])
        self.assertEqual(len(set(result.report_hashes)), 1)

    def test_report_hash_present(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        self.assertTrue(report.report_hash)
        self.assertTrue(report.run.run_hash)


class ShadowSafetyTests(unittest.TestCase):
    def test_evaluator_path_has_no_broker_imports(self) -> None:
        forbidden = (
            "market_platform_foundation.paper.submit",
            "market_platform_foundation.broker",
            "market_platform_foundation.execution.submit",
        )
        modules = [
            "market_platform_foundation.intelligence.news_strategy_evaluation.evaluator",
            "market_platform_foundation.intelligence.news_strategy_evaluation.shadow",
            "market_platform_foundation.intelligence.news_strategy_evaluation.decisions",
        ]
        for module_name in modules:
            module = importlib.import_module(module_name)
            source = Path(module.__file__).read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, source)

    def test_shadow_not_order_type(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        decision = next(
            s.enhanced_decision for s in report.sample_results if s.enhanced_decision is not None
        )
        shadow = build_shadow_record(decision, recorded_at=decision.as_of)
        self.assertIn("shadow_id", shadow.to_dict())
        self.assertTrue(shadow.shadow_hash)


class MultiAssetTests(unittest.TestCase):
    def test_equity_sample_evaluated(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        sample = next(s for s in report.sample_results if s.sample_id == "eval-013")
        self.assertFalse(sample.excluded)
        self.assertEqual(sample.instrument_id, "ACME")
        self.assertEqual(sample.asset_class, "EQUITY")


class FixtureIntegrityTests(unittest.TestCase):
    def test_fixture_pack_loads(self) -> None:
        pack = load_fixture_pack(DEFAULT_FIXTURE_PATH)
        self.assertGreaterEqual(len(pack.samples), 13)

    def test_exclusion_scenarios(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        excluded_ids = {s.sample_id for s in report.sample_results if s.excluded}
        self.assertIn("eval-007", excluded_ids)
        self.assertIn("eval-008", excluded_ids)
        self.assertIn("eval-009", excluded_ids)


class MetricTests(unittest.TestCase):
    def test_metrics_computed(self) -> None:
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        self.assertIsNotNone(report.baseline_metrics.evaluated_count)
        self.assertIn("directional_accuracy_delta", report.ai_incremental_delta)
        self.assertTrue(report.calibration.terminology == "EMPIRICAL_CONFIDENCE_ANALYSIS")


class ConfigValidationTests(unittest.TestCase):
    def test_verify_evaluation_config(self) -> None:
        config = EvaluationConfig()
        warnings = verify_evaluation_config(config, instrument_ids=("ES",))
        self.assertIsInstance(warnings, list)


class NoLookAheadPoisonTests(unittest.TestCase):
    def test_poison_future_market_bar_rejected(self) -> None:
        pack = load_fixture_pack()
        market = FixtureMarketDataProvider.from_fixture_payload(pack.raw_payload)
        event = _event(retrieved="2026-09-09T13:59:00Z")
        with self.assertRaises(EvaluationError):
            build_feature_snapshot(
                as_of="2026-09-09T12:00:00Z",
                instrument_id="ES",
                asset_class="FUTURES",
                events=[event],
                market_provider=market,
            )


if __name__ == "__main__":
    unittest.main()
