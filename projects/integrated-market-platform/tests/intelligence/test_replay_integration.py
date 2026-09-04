"""Replay runtime integration and parity tests (BUILD 07)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
    require_normalized_event,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.quality import assess_capabilities, RequirementSet  # noqa: E402
from market_platform_foundation.intelligence.replay import (  # noqa: E402
    DelayRule,
    DropRule,
    ReplayDecisionSchedule,
    ReplayFaultProfile,
    ReplayIsolationError,
    ReplayMode,
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
from tests.intelligence.test_signal_integration import (  # noqa: E402
    _moomoo_quote_fixture,
    _moomoo_trade_fixture,
)
from tests.intelligence.test_snapshot_fixtures import INSTRUMENT, SCOPE, T  # noqa: E402

FIVE_SEC = 5 * 1_000_000_000
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
    for index in range(6):
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


class ReplayRuntimeIntegrationTests(unittest.TestCase):
    def _pipeline_config(self, decision_time: int) -> ReplayPipelineConfig:
        quality = assess_capabilities(
            events=(),
            decision_time_ns=decision_time,
            requirements=RequirementSet(),
        )
        return ReplayPipelineConfig(
            snapshot_request=SnapshotBuildRequest(
                decision_time_ns=decision_time,
                scope=SCOPE,
                composition_policy=SnapshotCompositionPolicy(max_events=50, max_signals=5),
                capability_requirements=RequirementSet(),
            ),
            signal_request=SignalComputationRequest(
                window_ns=WINDOW,
                signal_types=frozenset({"spread_abs", "spread_bps", "cvd"}),
                persist=True,
            ),
            quality_decision=quality,
            persist_outputs=True,
        )

    def test_source_output_isolation_guard(self) -> None:
        repo = InMemoryIntelligenceRepository()
        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=T + 100,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(T + 30,)),
        )
        runtime = ReplayRuntime()
        with self.assertRaises(ReplayIsolationError):
            runtime.run(scenario, repo, output_repository=repo)

    def test_observed_replay_determinism(self) -> None:
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
        runtime = ReplayRuntime()
        config = self._pipeline_config(decision_time)
        first = runtime.run(scenario, source, pipeline_config=config)
        second = runtime.run(scenario, source, pipeline_config=config)
        self.assertEqual(first.scenario_fingerprint, second.scenario_fingerprint)
        self.assertEqual(
            first.decision_results[0].snapshot_ref,
            second.decision_results[0].snapshot_ref,
        )
        self.assertEqual(
            first.decision_results[0].signal_refs,
            second.decision_results[0].signal_refs,
        )

    def test_observed_live_replay_parity(self) -> None:
        decision_time = T + 30 * 1_000_000_000
        quote, trades = _build_fixture_events(decision_time)
        all_events = (quote, *trades)
        source = InMemoryIntelligenceRepository()
        for event in all_events:
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
            all_events,
            live_output,
            decision_time_ns=decision_time,
            config=self._pipeline_config(decision_time),
        )

        self.assertEqual(
            replay_result.decision_results[0].snapshot_ref.id,
            live_result.snapshot_ref.id,
        )
        replay_signals = sorted(ref.id for ref in replay_result.decision_results[0].signal_refs)
        live_signals = sorted(ref.id for ref in live_result.signal_refs)
        self.assertEqual(replay_signals, live_signals)

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
        self.assertEqual(first.replay_mode, ReplayMode.COUNTERFACTUAL)
        self.assertEqual(
            first.decision_results[0].snapshot_ref,
            second.decision_results[0].snapshot_ref,
        )

    def test_counterfactual_differs_from_observed(self) -> None:
        decision_time = T + 30 * 1_000_000_000
        quote, trades = _build_fixture_events(decision_time)
        source = InMemoryIntelligenceRepository()
        for event in (quote, *trades):
            source.put_event(event)
        observed = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=decision_time,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(decision_time,)),
        )
        counterfactual = counterfactual_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=decision_time,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(decision_time,)),
            fault_profile=ReplayFaultProfile(
                drop_rules=(DropRule(rule_id="drop-quote", event_ids=(quote.event_id,)),),
            ),
        )
        config = self._pipeline_config(decision_time)
        observed_result = ReplayRuntime().run(observed, source, pipeline_config=config)
        counter_result = ReplayRuntime().run(counterfactual, source, pipeline_config=config)
        self.assertNotEqual(
            observed_result.decision_results[0].snapshot_ref,
            counter_result.decision_results[0].snapshot_ref,
        )

    def test_full_build_01_to_07_lifecycle(self) -> None:
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
        result = ReplayRuntime().run(
            scenario,
            source,
            output_repository=output,
            pipeline_config=self._pipeline_config(decision_time),
        )
        self.assertEqual(result.source_event_count, 7)
        self.assertTrue(result.decision_results[0].snapshot_ref.id.startswith("SNAP-"))
        manifest = output.get_run_manifest(result.run_id)
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.metadata["replay_classification"], "OBSERVED_REPLAY")
        for signal_ref in result.decision_results[0].signal_refs:
            signal = output.get_signal(signal_ref.id)
            self.assertTrue(signal.signal_id.startswith("SIG-"))

    def test_source_repository_unchanged_after_replay(self) -> None:
        decision_time = T + 30 * 1_000_000_000
        quote, trades = _build_fixture_events(decision_time)
        source = InMemoryIntelligenceRepository()
        for event in (quote, *trades):
            source.put_event(event)
        before = source.get_event(quote.event_id)
        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=decision_time,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(decision_time,)),
        )
        ReplayRuntime().run(
            scenario,
            source,
            output_repository=InMemoryIntelligenceRepository(),
            pipeline_config=self._pipeline_config(decision_time),
        )
        after = source.get_event(quote.event_id)
        self.assertEqual(before.available_time_ns, after.available_time_ns)
        self.assertEqual(before.payload, after.payload)


if __name__ == "__main__":
    unittest.main()
