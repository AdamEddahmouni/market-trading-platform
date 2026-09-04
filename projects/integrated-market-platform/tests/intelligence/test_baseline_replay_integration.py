"""Baseline live/replay parity integration tests (BUILD 08)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.baselines import (  # noqa: E402
    AlwaysUpBaseline,
    BaselinePredictionEngine,
    BaselinePredictionRequest,
    MomentumBaseline,
    direction_up_down_target,
    persist_forecast,
)
from market_platform_foundation.intelligence.contracts import TimeHorizonNs  # noqa: E402
from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
    require_normalized_event,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.quality import RequirementSet, assess_capabilities  # noqa: E402
from market_platform_foundation.intelligence.replay import (  # noqa: E402
    DelayRule,
    ReplayDecisionSchedule,
    ReplayFaultProfile,
    ReplayPipelineConfig,
    ReplayRuntime,
    counterfactual_replay_scenario,
    live_like_sequential_decision,
    observed_replay_scenario,
)
from market_platform_foundation.intelligence.signals import SignalComputationRequest  # noqa: E402
from market_platform_foundation.intelligence.snapshots import (  # noqa: E402
    SnapshotBuildRequest,
    SnapshotCompositionPolicy,
)
from tests.intelligence.test_baseline_fixtures import HORIZON_5M, INSTRUMENT  # noqa: E402
from tests.intelligence.test_signal_integration import (  # noqa: E402
    _moomoo_quote_fixture,
    _moomoo_trade_fixture,
)
from tests.intelligence.test_snapshot_fixtures import SCOPE, T  # noqa: E402

WINDOW = 300 * 1_000_000_000


def _build_fixture_events(decision_time: int):
    ctx = NormalizationContext(
        received_time_ns=decision_time,
        ingestion_mode=IngestionMode.LIVE_OBSERVED,
    )
    quote = require_normalized_event(
        _moomoo_quote_fixture(T + 2 * 1_000_000_000),
        context=ctx,
        source_key="moomoo.capture",
    )
    trades = []
    for index in range(12):
        event_time = T + (3 + index) * 1_000_000_000
        side = "BUY" if index % 2 == 0 else "SELL"
        trades.append(
            require_normalized_event(
                _moomoo_trade_fixture(event_time, sequence=index + 1, side=side, qty=10),
                context=ctx,
                source_key="moomoo.capture",
            )
        )
    return quote, tuple(trades)


class BaselineReplayIntegrationTests(unittest.TestCase):
    def _pipeline_config(self, decision_time: int) -> ReplayPipelineConfig:
        quality = assess_capabilities(events=(), decision_time_ns=decision_time, requirements=RequirementSet())
        return ReplayPipelineConfig(
            snapshot_request=SnapshotBuildRequest(
                decision_time_ns=decision_time,
                scope=SCOPE,
                composition_policy=SnapshotCompositionPolicy(max_events=50, max_signals=10),
                capability_requirements=RequirementSet(),
            ),
            signal_request=SignalComputationRequest(
                window_ns=WINDOW,
                signal_types=frozenset({"momentum_simple", "spread_bps", "net_signed_share"}),
                persist=True,
            ),
            quality_decision=quality,
            persist_outputs=True,
        )

    def _baseline_forecast(self, snapshot, signals):
        engine = BaselinePredictionEngine()
        target = direction_up_down_target(INSTRUMENT)
        horizon = TimeHorizonNs(duration_ns=HORIZON_5M)
        return engine.predict(
            BaselinePredictionRequest(
                snapshot=snapshot,
                signals=signals,
                target=target,
                horizon=horizon,
            ),
            AlwaysUpBaseline().bind_target(target),
        )

    def test_live_replay_parity(self) -> None:
        decision_time = T + 30 * 1_000_000_000
        quote, trades = _build_fixture_events(decision_time)
        source = InMemoryIntelligenceRepository()
        for event in (quote, *trades):
            source.put_event(event)

        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=decision_time,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(decision_time,)),
        )
        replay_output = InMemoryIntelligenceRepository()
        replay_result = ReplayRuntime().run(
            scenario,
            source,
            output_repository=replay_output,
            pipeline_config=self._pipeline_config(decision_time),
        )
        live_output = InMemoryIntelligenceRepository()
        live_result = live_like_sequential_decision(
            (quote, *trades),
            live_output,
            decision_time_ns=decision_time,
            config=self._pipeline_config(decision_time),
        )

        replay_snapshot = replay_output.get_snapshot(replay_result.decision_results[0].snapshot_ref.id)
        live_snapshot = live_output.get_snapshot(live_result.snapshot_ref.id)
        assert replay_snapshot is not None and live_snapshot is not None
        replay_signals = tuple(
            replay_output.get_signal(ref.id)
            for ref in replay_result.decision_results[0].signal_refs
            if replay_output.get_signal(ref.id) is not None
        )
        live_signals = tuple(
            live_output.get_signal(ref.id)
            for ref in live_result.signal_refs
            if live_output.get_signal(ref.id) is not None
        )

        replay_forecast = self._baseline_forecast(replay_snapshot, replay_signals)
        live_forecast = self._baseline_forecast(live_snapshot, live_signals)
        assert replay_forecast.forecast is not None and live_forecast.forecast is not None
        self.assertEqual(replay_forecast.forecast.forecast_id, live_forecast.forecast.forecast_id)
        self.assertEqual(
            replay_forecast.forecast.estimate.probability,
            live_forecast.forecast.estimate.probability,
        )

    def test_counterfactual_reproducibility(self) -> None:
        decision_time = T + 30 * 1_000_000_000
        quote, trades = _build_fixture_events(decision_time)
        source = InMemoryIntelligenceRepository()
        for event in (quote, *trades):
            source.put_event(event)
        scenario = counterfactual_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=decision_time,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(decision_time,)),
            fault_profile=ReplayFaultProfile(
                delay_rules=(
                    DelayRule(
                        rule_id="quote-delay",
                        delay_ns=10 * 1_000_000_000,
                        event_ids=(quote.event_id,),
                    ),
                ),
            ),
        )
        runtime = ReplayRuntime()
        config = self._pipeline_config(decision_time)
        first = runtime.run(scenario, source, pipeline_config=config)
        second = runtime.run(scenario, source, pipeline_config=config)
        self.assertEqual(
            first.decision_results[0].snapshot_ref,
            second.decision_results[0].snapshot_ref,
        )

    def test_full_build_01_to_08_lifecycle(self) -> None:
        decision_time = T + 30 * 1_000_000_000
        quote, trades = _build_fixture_events(decision_time)
        source = InMemoryIntelligenceRepository()
        for event in (quote, *trades):
            source.put_event(event)
        output = InMemoryIntelligenceRepository()
        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=decision_time,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(decision_time,)),
        )
        replay_result = ReplayRuntime().run(
            scenario,
            source,
            output_repository=output,
            pipeline_config=self._pipeline_config(decision_time),
        )
        snapshot = output.get_snapshot(replay_result.decision_results[0].snapshot_ref.id)
        assert snapshot is not None
        signals = tuple(
            output.get_signal(ref.id)
            for ref in replay_result.decision_results[0].signal_refs
            if output.get_signal(ref.id) is not None
        )
        target = direction_up_down_target(INSTRUMENT)
        horizon = TimeHorizonNs(duration_ns=HORIZON_5M)
        engine = BaselinePredictionEngine()
        result = engine.predict(
            BaselinePredictionRequest(snapshot=snapshot, signals=signals, target=target, horizon=horizon),
            MomentumBaseline().bind_target(target),
        )
        if result.forecast is not None:
            persist_forecast(output, result.forecast)
            loaded = output.get_forecast(result.forecast.forecast_id)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.snapshot_id, snapshot.snapshot_id)


if __name__ == "__main__":
    unittest.main()
