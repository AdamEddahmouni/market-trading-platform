"""Snapshot engine core tests (BUILD 05)."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.contracts import IntelligenceScope, QualityState  # noqa: E402
from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
    RepositoryPutResult,
)
from market_platform_foundation.intelligence.quality.models import DecisionAction  # noqa: E402
from market_platform_foundation.intelligence.snapshots import (  # noqa: E402
    SnapshotBuilder,
    SnapshotCompositionPolicy,
    SnapshotQualityError,
    build_snapshot,
    compose_snapshot,
    inspect_snapshot_build,
)
from tests.intelligence.test_snapshot_fixtures import (  # noqa: E402
    T,
    INSTRUMENT,
    abstain_quality_decision,
    default_request,
    degrade_quality_decision,
    empty_repo_with_events,
    fail_closed_quality_decision,
    sample_event,
    sample_signal,
    use_quality_decision,
)


class SnapshotEngineTests(unittest.TestCase):
    def test_deterministic_identity(self) -> None:
        repo = empty_repo_with_events(
            sample_event("evt-1", available_time_ns=T),
            sample_event("evt-2", available_time_ns=T - 1),
        )
        request = default_request()
        first = build_snapshot(repo, request, quality_decision=use_quality_decision(), persist=False)
        second = build_snapshot(repo, request, quality_decision=use_quality_decision(), persist=False)
        self.assertEqual(first.content_fingerprint, second.content_fingerprint)
        self.assertEqual(first.snapshot.snapshot_id, second.snapshot.snapshot_id)

    def test_input_order_independence(self) -> None:
        events = (
            sample_event("evt-b", available_time_ns=T - 2),
            sample_event("evt-a", available_time_ns=T - 1),
        )
        repo1 = empty_repo_with_events(*events)
        repo2 = empty_repo_with_events(events[1], events[0])
        request = default_request()
        result1 = build_snapshot(repo1, request, quality_decision=use_quality_decision(), persist=False)
        result2 = build_snapshot(repo2, request, quality_decision=use_quality_decision(), persist=False)
        self.assertEqual(result1.content_fingerprint, result2.content_fingerprint)
        self.assertEqual(result1.selected_event_ids, ("evt-b", "evt-a"))

    def test_exact_temporal_boundary(self) -> None:
        repo = empty_repo_with_events(sample_event("evt-at", available_time_ns=T))
        result = build_snapshot(repo, default_request(), quality_decision=use_quality_decision(), persist=False)
        self.assertIn("evt-at", result.selected_event_ids)

    def test_future_excluded(self) -> None:
        repo = empty_repo_with_events(sample_event("evt-future", available_time_ns=T + 1))
        result = inspect_snapshot_build(repo, default_request(), quality_decision=use_quality_decision())
        self.assertNotIn("evt-future", result.selected_event_ids)

    def test_delayed_event_excluded(self) -> None:
        repo = empty_repo_with_events(
            sample_event(
                "evt-delayed",
                event_time_ns=T - 10,
                available_time_ns=T + 5,
            )
        )
        result = inspect_snapshot_build(repo, default_request(), quality_decision=use_quality_decision())
        self.assertNotIn("evt-delayed", result.selected_event_ids)

    def test_late_arrival_does_not_alter_old_snapshot(self) -> None:
        repo = empty_repo_with_events(sample_event("evt-1", available_time_ns=T))
        first = build_snapshot(repo, default_request(decision_time_ns=T), quality_decision=use_quality_decision())
        repo.put_event(
            sample_event(
                "evt-late",
                event_time_ns=T - 100,
                available_time_ns=T + 50,
            )
        )
        stored = repo.get_snapshot(first.snapshot.snapshot_id)
        self.assertEqual(stored.source_event_refs, first.snapshot.source_event_refs)
        self.assertEqual(
            stored.metadata["content_fingerprint"],
            first.snapshot.metadata["content_fingerprint"],
        )

    def test_quality_use(self) -> None:
        repo = empty_repo_with_events(sample_event())
        result = build_snapshot(repo, default_request(), quality_decision=use_quality_decision())
        self.assertIsNotNone(result.snapshot)
        self.assertEqual(repo.get_snapshot(result.snapshot.snapshot_id).snapshot_id, result.snapshot.snapshot_id)

    def test_quality_degrade(self) -> None:
        repo = empty_repo_with_events(sample_event())
        result = build_snapshot(repo, default_request(), quality_decision=degrade_quality_decision())
        self.assertEqual(result.snapshot.quality.state, QualityState.DEGRADED)

    def test_quality_abstain(self) -> None:
        repo = empty_repo_with_events(sample_event())
        with self.assertRaises(SnapshotQualityError):
            build_snapshot(repo, default_request(), quality_decision=abstain_quality_decision())
        self.assertIsNone(repo.get_snapshot("snap-1"))

    def test_quality_fail_closed(self) -> None:
        repo = empty_repo_with_events(sample_event())
        with self.assertRaises(SnapshotQualityError):
            build_snapshot(repo, default_request(), quality_decision=fail_closed_quality_decision())

    def test_no_persist_on_failure(self) -> None:
        repo = empty_repo_with_events(sample_event())
        before = len([key for key in repo._stores["snapshots"]])
        with self.assertRaises(SnapshotQualityError):
            build_snapshot(repo, default_request(), quality_decision=abstain_quality_decision())
        after = len([key for key in repo._stores["snapshots"]])
        self.assertEqual(before, after)

    def test_persistence_idempotency(self) -> None:
        repo = empty_repo_with_events(sample_event())
        first = build_snapshot(repo, default_request(), quality_decision=use_quality_decision(), persist=True)
        second = build_snapshot(repo, default_request(), quality_decision=use_quality_decision(), persist=True)
        self.assertEqual(first.snapshot.snapshot_id, second.snapshot.snapshot_id)
        self.assertEqual(repo.put_snapshot(first.snapshot), RepositoryPutResult.ALREADY_PRESENT)

    def test_bounded_selection(self) -> None:
        events = [sample_event(f"evt-{index}", available_time_ns=T - index) for index in range(5)]
        repo = empty_repo_with_events(*events)
        request = default_request(policy=SnapshotCompositionPolicy(max_events=2, max_signals=1))
        result = build_snapshot(repo, request, quality_decision=use_quality_decision(), persist=False)
        self.assertEqual(len(result.selected_event_ids), 2)

    def test_lookback_window(self) -> None:
        repo = empty_repo_with_events(
            sample_event("evt-old", available_time_ns=T - 1_000_000_000),
            sample_event("evt-new", available_time_ns=T - 10),
        )
        request = default_request(policy=SnapshotCompositionPolicy(max_events=10, lookback_ns=100))
        result = build_snapshot(repo, request, quality_decision=use_quality_decision(), persist=False)
        self.assertIn("evt-new", result.selected_event_ids)
        self.assertNotIn("evt-old", result.selected_event_ids)

    def test_other_instrument_excluded(self) -> None:
        other = sample_event("evt-other", available_time_ns=T)
        object.__setattr__(other, "instrument_id", "AAPL")
        repo = empty_repo_with_events(other)
        result = inspect_snapshot_build(repo, default_request(), quality_decision=use_quality_decision())
        self.assertEqual(result.selected_event_ids, ())

    def test_signal_as_of(self) -> None:
        repo = InMemoryIntelligenceRepository()
        repo.put_event(sample_event())
        repo.put_signal(sample_signal("sig-ok", as_of_time_ns=T))
        repo.put_signal(sample_signal("sig-future", as_of_time_ns=T + 1))
        result = build_snapshot(repo, default_request(), quality_decision=use_quality_decision(), persist=False)
        self.assertIn("sig-ok", result.selected_signal_ids)
        self.assertNotIn("sig-future", result.selected_signal_ids)

    def test_pure_compose_no_repo(self) -> None:
        events = (sample_event("evt-1", available_time_ns=T),)
        request = default_request()
        snapshot, fingerprint = compose_snapshot(
            request=request,
            quality_decision=use_quality_decision(),
            selected_events=events,
            selected_signals=(),
        )
        self.assertTrue(snapshot.snapshot_id.startswith("SNAP-"))
        self.assertEqual(snapshot.metadata["content_fingerprint"], fingerprint)

    def test_input_not_mutated(self) -> None:
        event = sample_event()
        decision = use_quality_decision()
        request = default_request()
        before_event = copy.deepcopy(event)
        before_decision = copy.deepcopy(decision)
        compose_snapshot(
            request=request,
            quality_decision=decision,
            selected_events=(event,),
            selected_signals=(),
        )
        self.assertEqual(event.event_id, before_event.event_id)
        self.assertEqual(decision.action, before_decision.action)

    def test_scope_changes_identity(self) -> None:
        events = (sample_event("evt-1", available_time_ns=T),)
        request_a = default_request(scope=IntelligenceScope(instrument_ids=(INSTRUMENT,)))
        request_b = default_request(scope=IntelligenceScope(instrument_ids=("AAPL",)))
        snap_a, fp_a = compose_snapshot(
            request=request_a,
            quality_decision=use_quality_decision(),
            selected_events=events,
            selected_signals=(),
        )
        snap_b, fp_b = compose_snapshot(
            request=request_b,
            quality_decision=use_quality_decision(),
            selected_events=events,
            selected_signals=(),
        )
        self.assertNotEqual(fp_a, fp_b)

    def test_decision_time_changes_identity(self) -> None:
        events = (sample_event("evt-1", available_time_ns=T),)
        snap_a, fp_a = compose_snapshot(
            request=default_request(decision_time_ns=T),
            quality_decision=use_quality_decision(T),
            selected_events=events,
            selected_signals=(),
        )
        snap_b, fp_b = compose_snapshot(
            request=default_request(decision_time_ns=T + 1),
            quality_decision=use_quality_decision(T + 1),
            selected_events=events,
            selected_signals=(),
        )
        self.assertNotEqual(fp_a, fp_b)

    def test_degrade_not_allowed_when_policy_disallows(self) -> None:
        repo = empty_repo_with_events(sample_event())
        request = default_request(
            policy=SnapshotCompositionPolicy(max_events=10, allow_degraded=False),
        )
        with self.assertRaises(SnapshotQualityError):
            build_snapshot(repo, request, quality_decision=degrade_quality_decision())

    def test_builder_class_api(self) -> None:
        repo = empty_repo_with_events(sample_event())
        builder = SnapshotBuilder(repo)
        result = builder.build(default_request(), quality_decision=use_quality_decision(), persist=False)
        self.assertIsNotNone(result.snapshot)


if __name__ == "__main__":
    unittest.main()
