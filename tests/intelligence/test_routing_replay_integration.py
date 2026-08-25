"""BUILD 07 + BUILD 09 live/replay parity and leakage tests."""

from __future__ import annotations

import dataclasses
import unittest

from market_platform_foundation.intelligence.normalization import (
    IngestionMode,
    NormalizationContext,
    require_normalized_event,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence import IntelligenceRepository
from market_platform_foundation.intelligence.quality import IntelligenceCapability
from market_platform_foundation.intelligence.replay import (
    DropRule,
    ReplayDecisionSchedule,
    ReplayFaultProfile,
    ReplayPipelineConfig,
    ReplayRuntime,
    counterfactual_replay_scenario,
    live_like_sequential_decision,
    observed_replay_scenario,
    ReplayVisibilityIndex,
    ReplayVisibleRepository,
)
from market_platform_foundation.intelligence.routing import EventDetectorEngine, SmartRouter
from market_platform_foundation.intelligence.signals import SignalComputationRequest
from market_platform_foundation.intelligence.snapshots import (
    SnapshotBuildRequest,
    SnapshotCompositionPolicy,
)
from tests.intelligence.routing_fixtures import T, WINDOW_NS, quality_decision
from tests.intelligence.test_signal_integration import _moomoo_quote_fixture, _moomoo_trade_fixture
from tests.intelligence.test_snapshot_fixtures import SCOPE

ONE_SECOND = 1_000_000_000
D1 = T + 4 * ONE_SECOND
D2 = T + 8 * ONE_SECOND


def _normalize(raw: dict[str, object], received_time_ns: int):
    return require_normalized_event(
        raw,
        context=NormalizationContext(
            received_time_ns=received_time_ns,
            ingestion_mode=IngestionMode.LIVE_OBSERVED,
        ),
        source_key="moomoo.capture",
    )


def _events():
    quote_time = T + ONE_SECOND
    sell_time = T + 2 * ONE_SECOND
    buy_time = T + 6 * ONE_SECOND
    quote = _normalize(_moomoo_quote_fixture(quote_time), quote_time)
    sell = _normalize(_moomoo_trade_fixture(sell_time, sequence=1, side="SELL", qty=100), sell_time)
    buy = _normalize(_moomoo_trade_fixture(buy_time, sequence=2, side="BUY", qty=300), buy_time)
    return quote, sell, buy


def _config() -> ReplayPipelineConfig:
    return ReplayPipelineConfig(
        snapshot_request=SnapshotBuildRequest(
            decision_time_ns=D1,
            scope=SCOPE,
            composition_policy=SnapshotCompositionPolicy(max_events=50, max_signals=5),
        ),
        signal_request=SignalComputationRequest(
            window_ns=WINDOW_NS,
            signal_types=frozenset({"net_signed_share"}),
            persist=True,
        ),
        quality_decisions=(
            quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.TRADES,
                decision_time_ns=D1,
            ),
            quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.TRADES,
                decision_time_ns=D2,
            ),
        ),
        enable_build_09=True,
        persist_outputs=True,
    )


def _source(events) -> InMemoryIntelligenceRepository:
    repo = InMemoryIntelligenceRepository()
    for row in events:
        repo.put_event(row)
    return repo


class RoutingReplayIntegrationTests(unittest.TestCase):
    def test_replay_visible_repository_retains_repository_protocol(self) -> None:
        visible = ReplayVisibleRepository(
            source_repository=InMemoryIntelligenceRepository(),
            output_repository=InMemoryIntelligenceRepository(),
            visibility_index=ReplayVisibilityIndex(envelopes=()),
            decision_time_ns=D1,
        )
        self.assertIsInstance(visible, IntelligenceRepository)

    def test_full_build_01_to_09_lifecycle_preserves_lineage(self) -> None:
        events = _events()
        source = _source(events)
        output = InMemoryIntelligenceRepository()
        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=D2,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(D1, D2)),
        )
        result = ReplayRuntime().run(
            scenario,
            source,
            output_repository=output,
            pipeline_config=_config(),
        )
        decision = result.decision_results[1]
        snapshot_record = output.get_snapshot(decision.snapshot_ref.id)
        detection = output.get_detection(decision.detection_refs[0].id)
        route = output.get_routing_decision(decision.routing_decision_refs[0].id)
        self.assertEqual(detection.source_snapshot_ref.id, snapshot_record.snapshot_id)
        self.assertEqual(
            {ref.id for ref in detection.source_signal_refs},
            {result.decision_results[0].signal_refs[0].id, decision.signal_refs[0].id},
        )
        self.assertEqual(route.detection_ref.id, detection.detection_id)
        self.assertEqual(route.decision_time_ns, snapshot_record.decision_time_ns)
        self.assertIsNone(output.get_forecast("build-09-generated-forecast"))
        self.assertIsNone(output.get_evidence("build-09-generated-evidence"))
        self.assertIsNone(output.get_hypothesis("build-09-generated-hypothesis"))

    def test_observed_replay_is_reproducible_and_future_safe(self) -> None:
        events = _events()
        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=D2,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(D1, D2)),
        )
        first = ReplayRuntime().run(scenario, _source(events), pipeline_config=_config())
        second = ReplayRuntime().run(scenario, _source(events), pipeline_config=_config())
        self.assertEqual(first.decision_results, second.decision_results)
        self.assertEqual(first.decision_results[0].detection_refs, ())
        self.assertEqual(first.decision_results[0].routing_decision_refs, ())
        self.assertEqual(len(first.decision_results[1].detection_refs), 1)
        self.assertEqual(len(first.decision_results[1].routing_decision_refs), 1)

    def test_live_like_and_observed_replay_outputs_match(self) -> None:
        events = _events()
        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=D2,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(D1, D2)),
        )
        replay = ReplayRuntime().run(scenario, _source(events), pipeline_config=_config())

        live_repo = InMemoryIntelligenceRepository()
        engine = EventDetectorEngine()
        router = SmartRouter()
        live = (
            live_like_sequential_decision(
                events,
                live_repo,
                decision_time_ns=D1,
                config=_config(),
                detector_engine=engine,
                smart_router=router,
            ),
            live_like_sequential_decision(
                events,
                live_repo,
                decision_time_ns=D2,
                config=_config(),
                detector_engine=engine,
                smart_router=router,
            ),
        )
        self.assertEqual(
            tuple(row.detection_refs for row in replay.decision_results),
            tuple(row.detection_refs for row in live),
        )
        self.assertEqual(
            tuple(row.routing_decision_refs for row in replay.decision_results),
            tuple(row.routing_decision_refs for row in live),
        )

        route_ref = live[1].routing_decision_refs[0]
        replay_output = InMemoryIntelligenceRepository()
        replay_again = ReplayRuntime().run(
            scenario,
            _source(events),
            output_repository=replay_output,
            pipeline_config=_config(),
        )
        replay_route = replay_output.get_routing_decision(replay_again.decision_results[1].routing_decision_refs[0].id)
        live_route = live_repo.get_routing_decision(route_ref.id)
        self.assertEqual(replay_route, live_route)

    def test_counterfactual_drop_is_reproducible_and_can_remove_route(self) -> None:
        events = _events()
        buy = events[-1]
        scenario = counterfactual_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=D2,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(D1, D2)),
            fault_profile=ReplayFaultProfile(
                drop_rules=(DropRule(rule_id="drop-buy", event_ids=(buy.event_id,)),),
            ),
        )
        first = ReplayRuntime().run(scenario, _source(events), pipeline_config=_config())
        second = ReplayRuntime().run(scenario, _source(events), pipeline_config=_config())
        self.assertEqual(first.decision_results, second.decision_results)
        self.assertEqual(first.decision_results[1].detection_refs, ())
        self.assertEqual(first.decision_results[1].routing_decision_refs, ())

    def test_build_09_uses_quality_decision_created_during_snapshot_build(self) -> None:
        events = _events()
        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=D2,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(D1, D2)),
        )
        config = dataclasses.replace(_config(), quality_decisions=())
        result = ReplayRuntime().run(scenario, _source(events), pipeline_config=config)
        self.assertIsNotNone(result.decision_results[0].quality_decision)
        self.assertEqual(len(result.decision_results[1].detection_refs), 1)
        self.assertEqual(len(result.decision_results[1].routing_decision_refs), 1)


if __name__ == "__main__":
    unittest.main()
