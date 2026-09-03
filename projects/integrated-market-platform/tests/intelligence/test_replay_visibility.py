"""Replay visibility layer tests (BUILD 07)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.replay import (  # noqa: E402
    DelayRule,
    DeliveryAction,
    DropRule,
    ReplayFaultProfile,
    ReplayMode,
    ReplayVisibilityIndex,
    ReplayVisibleRepository,
    build_delivery_schedule,
    recompose_snapshot_at,
)
from market_platform_foundation.intelligence.snapshots import (  # noqa: E402
    SnapshotBuildRequest,
    SnapshotCompositionPolicy,
)
from market_platform_foundation.intelligence.contracts import IntelligenceScope  # noqa: E402
from market_platform_foundation.intelligence.quality.models import RequirementSet  # noqa: E402
from tests.intelligence.test_persistence_fixtures import INSTRUMENT, sample_event  # noqa: E402

T = 1_700_000_000_000_000_000
SCOPE = IntelligenceScope(instrument_ids=(INSTRUMENT,))


class ReplayVisibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = InMemoryIntelligenceRepository()
        self.output = InMemoryIntelligenceRepository()
        self.event = sample_event("evt-1", available_time_ns=T)
        self.source.put_event(self.event)

    def _visible_repo(self, decision_time_ns: int, envelopes) -> ReplayVisibleRepository:
        return ReplayVisibleRepository(
            source_repository=self.source,
            output_repository=self.output,
            visibility_index=ReplayVisibilityIndex.from_envelopes(envelopes),
            decision_time_ns=decision_time_ns,
        )

    def test_event_visible_at_decision_equality(self) -> None:
        envelopes = build_delivery_schedule(
            (self.event,),
            mode=ReplayMode.OBSERVED_REPLAY,
            fault_profile=ReplayFaultProfile(),
            replay_end_ns=T + 100,
        )
        repo = self._visible_repo(T, envelopes)
        ids = [event.event_id for event in repo.query_events_as_of(T)]
        self.assertEqual(ids, ["evt-1"])

    def test_event_one_ns_after_decision_hidden(self) -> None:
        envelopes = build_delivery_schedule(
            (sample_event("evt-future", available_time_ns=T + 1),),
            mode=ReplayMode.OBSERVED_REPLAY,
            fault_profile=ReplayFaultProfile(),
            replay_end_ns=T + 100,
        )
        repo = self._visible_repo(T, envelopes)
        self.assertEqual(repo.query_events_as_of(T), ())

    def test_delayed_event_not_visible_early(self) -> None:
        profile = ReplayFaultProfile(
            delay_rules=(DelayRule(rule_id="delay", delay_ns=5, event_ids=("evt-1",)),),
        )
        envelopes = build_delivery_schedule(
            (self.event,),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        repo_early = self._visible_repo(T + 2, envelopes)
        self.assertEqual(repo_early.query_events_as_of(T + 2), ())
        repo_late = self._visible_repo(T + 6, envelopes)
        self.assertEqual(len(repo_late.query_events_as_of(T + 6)), 1)

    def test_source_event_unchanged_after_delay(self) -> None:
        profile = ReplayFaultProfile(
            delay_rules=(DelayRule(rule_id="delay", delay_ns=5, event_ids=("evt-1",)),),
        )
        build_delivery_schedule(
            (self.event,),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        stored = self.source.get_event("evt-1")
        self.assertEqual(stored.available_time_ns, T)
        self.assertEqual(stored.event_id, "evt-1")

    def test_post_run_counterfactual_recomposition(self) -> None:
        profile = ReplayFaultProfile(
            delay_rules=(DelayRule(rule_id="delay", delay_ns=5, event_ids=("evt-1",)),),
        )
        envelopes = build_delivery_schedule(
            (self.event,),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        # After full run delivery at T+5, recompose at T+2 must still exclude event.
        result = recompose_snapshot_at(
            source_repository=self.source,
            visibility_index=ReplayVisibilityIndex.from_envelopes(envelopes),
            decision_time_ns=T + 2,
            snapshot_request_builder=lambda decision_time_ns: SnapshotBuildRequest(
                decision_time_ns=decision_time_ns,
                scope=SCOPE,
                composition_policy=SnapshotCompositionPolicy(max_events=10, max_signals=5),
                capability_requirements=RequirementSet(),
            ),
        )
        self.assertEqual(result.selected_event_ids, ())
        if result.snapshot is not None:
            self.assertEqual(result.snapshot.source_event_refs, ())

    def test_dropped_event_not_visible_but_source_exists(self) -> None:
        profile = ReplayFaultProfile(
            drop_rules=(DropRule(rule_id="drop", event_ids=("evt-1",)),),
        )
        envelopes = build_delivery_schedule(
            (self.event,),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        repo = self._visible_repo(T + 10, envelopes)
        self.assertEqual(repo.query_events_as_of(T + 10), ())
        self.assertIsNotNone(self.source.get_event("evt-1"))

    def test_get_event_resolves_source_for_snapshot_refs(self) -> None:
        envelopes = build_delivery_schedule(
            (self.event,),
            mode=ReplayMode.OBSERVED_REPLAY,
            fault_profile=ReplayFaultProfile(),
            replay_end_ns=T + 100,
        )
        repo = self._visible_repo(T, envelopes)
        resolved = repo.get_event("evt-1")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.event_id, "evt-1")


if __name__ == "__main__":
    unittest.main()
