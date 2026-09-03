"""BUILD 02 — temporal integrity and point-in-time rules."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    ContractReference,
    EventV1,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SignalV1,
    SnapshotV1,
    SourceReference,
)
from market_platform_foundation.intelligence.temporal import (  # noqa: E402
    DEFAULT_TEMPORAL_POLICY,
    DuplicateClassification,
    TemporalIntegrityError,
    TemporalIntegrityPolicy,
    TemporalStreamState,
    TemporalViolationCode,
    TemporalViolationSeverity,
    classify_duplicate_events,
    eligible_as_of,
    inspect_event_temporal_integrity,
    inspect_signal_temporal_integrity,
    inspect_temporal_integrity,
    is_temporally_eligible,
    mapping_resolver,
    require_snapshot_temporally_valid,
    require_temporally_usable,
    select_events_as_of,
    temporal_eligibility,
    usable_as_of,
    validate_snapshot_temporal_integrity,
)

T0 = 1_000_000_000_000
FIVE_SEC = 5 * 1_000_000_000
QUALITY = QualitySummary(state=QualityState.GOOD)
SOURCE = SourceReference(provider_id="TEST", source_type="unit", source_record_id="r1")
SCOPE = IntelligenceScope(instrument_ids=("NVDA",))


def _event(
    event_id: str = "evt-1",
    *,
    event_time_ns: int = T0,
    available_time_ns: int = T0,
    received_time_ns: int | None = None,
    provider_time_ns: int | None = None,
    payload: dict | None = None,
) -> EventV1:
    return EventV1(
        event_id=event_id,
        schema_version="1",
        event_type="TRADE",
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload or {"px": 100},
        quality=QUALITY,
        source=SOURCE,
        instrument_id="NVDA",
        received_time_ns=received_time_ns,
        provider_time_ns=provider_time_ns,
    )


class EligibilityBoundaryTests(unittest.TestCase):
    def test_exact_decision_boundary_eligible(self) -> None:
        event = _event(available_time_ns=T0)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0)
        self.assertTrue(report.eligible)
        self.assertTrue(report.usable)

    def test_one_nanosecond_future_rejected(self) -> None:
        event = _event(available_time_ns=T0 + 1)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0)
        self.assertFalse(report.eligible)
        self.assertFalse(report.usable)
        self.assertEqual(report.hard_failures[0].code, TemporalViolationCode.FUTURE_INFORMATION)

    def test_delayed_information_not_eligible_by_event_time(self) -> None:
        event = _event(event_time_ns=T0, available_time_ns=T0 + FIVE_SEC)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0 + 2 * 1_000_000_000)
        self.assertFalse(report.eligible)
        self.assertEqual(report.hard_failures[0].code, TemporalViolationCode.FUTURE_INFORMATION)

    def test_late_arrival_after_economic_event(self) -> None:
        event = _event(
            event_time_ns=T0,
            received_time_ns=T0 + FIVE_SEC,
            available_time_ns=T0 + FIVE_SEC,
        )
        early = inspect_event_temporal_integrity(event, decision_time_ns=T0 + 2 * 1_000_000_000)
        late = inspect_event_temporal_integrity(event, decision_time_ns=T0 + 6 * 1_000_000_000)
        self.assertFalse(early.eligible)
        self.assertTrue(late.eligible)


class EligibilityVsUsabilityTests(unittest.TestCase):
    def test_eligible_but_stale(self) -> None:
        policy = TemporalIntegrityPolicy(max_age_ns=100)
        event = _event(available_time_ns=T0)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0 + 1000, policy=policy)
        self.assertTrue(report.eligible)
        self.assertFalse(report.usable)
        codes = {v.code for v in report.violations}
        self.assertIn(TemporalViolationCode.STALE_INFORMATION, codes)

    def test_fresh_information_usable(self) -> None:
        policy = TemporalIntegrityPolicy(max_age_ns=100)
        event = _event(available_time_ns=T0)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0 + 50, policy=policy)
        self.assertTrue(report.eligible)
        self.assertTrue(report.usable)

    def test_future_is_not_stale(self) -> None:
        policy = TemporalIntegrityPolicy(max_age_ns=100)
        event = _event(available_time_ns=T0 + 1)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0, policy=policy)
        self.assertFalse(report.eligible)
        codes = {v.code for v in report.violations}
        self.assertIn(TemporalViolationCode.FUTURE_INFORMATION, codes)
        self.assertNotIn(TemporalViolationCode.STALE_INFORMATION, codes)


class ClockSkewTests(unittest.TestCase):
    def test_clock_skew_within_tolerance(self) -> None:
        policy = TemporalIntegrityPolicy(
            max_provider_clock_ahead_ns=1_000_000_000,
            max_provider_clock_behind_ns=1_000_000_000,
        )
        event = _event(
            provider_time_ns=T0 + 500_000_000,
            received_time_ns=T0,
            available_time_ns=T0,
        )
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0 + 1, policy=policy)
        self.assertNotIn(TemporalViolationCode.CLOCK_SKEW, {v.code for v in report.violations})

    def test_clock_skew_outside_tolerance_warning(self) -> None:
        policy = TemporalIntegrityPolicy(max_provider_clock_ahead_ns=100)
        event = _event(
            provider_time_ns=T0 + 500,
            received_time_ns=T0,
            available_time_ns=T0,
        )
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0 + 1, policy=policy)
        skew = [v for v in report.violations if v.code == TemporalViolationCode.CLOCK_SKEW]
        self.assertEqual(len(skew), 1)
        self.assertEqual(skew[0].severity, TemporalViolationSeverity.WARNING)


class DuplicateTests(unittest.TestCase):
    def test_exact_duplicate(self) -> None:
        first = _event("evt-dup")
        second = _event("evt-dup")
        self.assertEqual(
            classify_duplicate_events(first, second),
            TemporalViolationCode.EXACT_DUPLICATE,
        )
        state = TemporalStreamState()
        obs1 = state.observe(first)
        obs2 = state.observe(second)
        self.assertEqual(obs1.duplicate, DuplicateClassification.NEW)
        self.assertEqual(obs2.duplicate, DuplicateClassification.EXACT_DUPLICATE)

    def test_conflicting_duplicate(self) -> None:
        first = _event("evt-dup", payload={"px": 100})
        second = _event("evt-dup", payload={"px": 101})
        self.assertEqual(
            classify_duplicate_events(first, second),
            TemporalViolationCode.CONFLICTING_DUPLICATE,
        )
        state = TemporalStreamState()
        state.observe(first)
        obs = state.observe(second)
        self.assertEqual(obs.duplicate, DuplicateClassification.CONFLICTING_DUPLICATE)


class OutOfOrderTests(unittest.TestCase):
    def test_out_of_order_received_time_detected(self) -> None:
        state = TemporalStreamState()
        state.observe(_event("e1", received_time_ns=T0 + 10, available_time_ns=T0 + 10))
        obs = state.observe(_event("e2", received_time_ns=T0 + 5, available_time_ns=T0 + 5))
        codes = {v.code for v in obs.violations}
        self.assertIn(TemporalViolationCode.OUT_OF_ORDER, codes)

    def test_late_arrival_usable_only_after_available(self) -> None:
        late = _event("late", event_time_ns=T0, available_time_ns=T0 + FIVE_SEC)
        before = select_events_as_of([late], T0 + 2 * 1_000_000_000)
        after = select_events_as_of([late], T0 + 6 * 1_000_000_000)
        self.assertEqual(before, ())
        self.assertEqual(len(after), 1)


class SelectionTests(unittest.TestCase):
    def test_input_order_independence(self) -> None:
        events = [
            _event("c", available_time_ns=T0 + 30),
            _event("a", available_time_ns=T0 + 10),
            _event("b", available_time_ns=T0 + 20),
        ]
        forward = eligible_as_of(events, T0 + 100)
        reverse = eligible_as_of(list(reversed(events)), T0 + 100)
        self.assertEqual(forward, reverse)
        self.assertEqual([e.event_id for e in forward], ["a", "b", "c"])

    def test_usable_as_of_respects_max_age(self) -> None:
        policy = TemporalIntegrityPolicy(max_age_ns=50)
        events = [_event("fresh", available_time_ns=T0), _event("stale", available_time_ns=T0 - 100)]
        selected = usable_as_of(events, T0, policy=policy)
        self.assertEqual([e.event_id for e in selected], ["fresh"])


class SnapshotValidationTests(unittest.TestCase):
    def _snapshot(self, decision: int, event_refs: tuple[ContractReference, ...]) -> SnapshotV1:
        return SnapshotV1(
            snapshot_id="snap-1",
            schema_version="1",
            decision_time_ns=decision,
            scope=SCOPE,
            quality=QUALITY,
            source_event_refs=event_refs,
        )

    def test_snapshot_future_source_rejection(self) -> None:
        event = _event("evt-future", available_time_ns=T0 + 1)
        snapshot = self._snapshot(T0, (ContractReference(kind="event", id=event.event_id),))
        resolver = mapping_resolver(events={event.event_id: event})
        report = validate_snapshot_temporal_integrity(snapshot, resolver=resolver)
        self.assertFalse(report.eligible)
        self.assertIn(TemporalViolationCode.FUTURE_INFORMATION, {v.code for v in report.violations})

    def test_snapshot_legal_sources(self) -> None:
        event = _event("evt-ok", available_time_ns=T0)
        snapshot = self._snapshot(T0, (ContractReference(kind="event", id=event.event_id),))
        resolver = mapping_resolver(events={event.event_id: event})
        report = validate_snapshot_temporal_integrity(snapshot, resolver=resolver)
        self.assertTrue(report.eligible)
        self.assertTrue(report.usable)

    def test_snapshot_not_mutated_by_validation(self) -> None:
        event = _event("evt-ok", available_time_ns=T0)
        snapshot = self._snapshot(T0, (ContractReference(kind="event", id=event.event_id),))
        before = copy.deepcopy(snapshot)
        resolver = mapping_resolver(events={event.event_id: event})
        validate_snapshot_temporal_integrity(snapshot, resolver=resolver)
        self.assertEqual(snapshot, before)
        late = _event("evt-late", event_time_ns=T0 - 10, available_time_ns=T0 + 100)
        resolver_late = mapping_resolver(events={event.event_id: event, late.event_id: late})
        validate_snapshot_temporal_integrity(snapshot, resolver=resolver_late)
        self.assertEqual(snapshot.source_event_refs, before.source_event_refs)


class SignalValidationTests(unittest.TestCase):
    def test_signal_as_of_valid(self) -> None:
        signal = SignalV1(
            signal_id="sig-1",
            schema_version="1",
            signal_type="CVD",
            scope=SCOPE,
            as_of_time_ns=T0,
            value=1.0,
            quality=QUALITY,
        )
        report = inspect_signal_temporal_integrity(signal, decision_time_ns=T0)
        self.assertTrue(report.eligible)

    def test_signal_as_of_invalid(self) -> None:
        signal = SignalV1(
            signal_id="sig-1",
            schema_version="1",
            signal_type="CVD",
            scope=SCOPE,
            as_of_time_ns=T0 + 1,
            value=1.0,
            quality=QUALITY,
        )
        report = inspect_signal_temporal_integrity(signal, decision_time_ns=T0)
        self.assertFalse(report.eligible)
        self.assertEqual(
            report.hard_failures[0].code,
            TemporalViolationCode.SIGNAL_AS_OF_AFTER_DECISION,
        )


class StrictApiTests(unittest.TestCase):
    def test_require_temporally_usable_raises_structured_error(self) -> None:
        event = _event(available_time_ns=T0 + 1)
        with self.assertRaises(TemporalIntegrityError) as ctx:
            require_temporally_usable(event, decision_time_ns=T0)
        err = ctx.exception
        self.assertEqual(err.code, TemporalViolationCode.FUTURE_INFORMATION)
        self.assertEqual(err.record_id, event.event_id)
        self.assertEqual(err.decision_time_ns, T0)
        self.assertEqual(err.relevant_time_ns, T0 + 1)
        payload = err.to_dict()
        self.assertNotIn("payload", payload)

    def test_inspect_does_not_throw(self) -> None:
        event = _event(available_time_ns=T0 + 1)
        report = inspect_temporal_integrity(event, decision_time_ns=T0)
        self.assertFalse(report.eligible)


class PolicyImmutabilityTests(unittest.TestCase):
    def test_policy_defaults_not_mutated(self) -> None:
        policy = TemporalIntegrityPolicy(max_age_ns=100)
        inspect_event_temporal_integrity(_event(), decision_time_ns=T0 + 1000, policy=policy)
        self.assertEqual(policy.max_age_ns, 100)
        self.assertIsNone(DEFAULT_TEMPORAL_POLICY.max_age_ns)


class ReplayParityTests(unittest.TestCase):
    def test_identical_results_for_live_and_replay_labels(self) -> None:
        events = [
            _event("a", available_time_ns=T0),
            _event("b", available_time_ns=T0 + 10),
            _event("c", available_time_ns=T0 + 20),
        ]
        decision = T0 + 15
        live = eligible_as_of(events, decision)
        replay = eligible_as_of(tuple(events), decision)
        self.assertEqual(live, replay)


class P6CompatiblePolicyTests(unittest.TestCase):
    def test_require_event_time_before_decision(self) -> None:
        policy = TemporalIntegrityPolicy(require_event_time_before_decision=True)
        event = _event(event_time_ns=T0 + 1, available_time_ns=T0)
        report = inspect_event_temporal_integrity(event, decision_time_ns=T0, policy=policy)
        self.assertFalse(report.eligible)


class SnapshotStrictApiTests(unittest.TestCase):
    def test_require_snapshot_temporally_valid(self) -> None:
        event = _event("evt-future", available_time_ns=T0 + 1)
        snapshot = SnapshotV1(
            snapshot_id="snap-1",
            schema_version="1",
            decision_time_ns=T0,
            scope=SCOPE,
            quality=QUALITY,
            source_event_refs=(ContractReference(kind="event", id=event.event_id),),
        )
        with self.assertRaises(TemporalIntegrityError):
            require_snapshot_temporally_valid(
                snapshot,
                resolver=mapping_resolver(events={event.event_id: event}),
            )


class HelperApiTests(unittest.TestCase):
    def test_is_temporally_eligible(self) -> None:
        self.assertTrue(is_temporally_eligible(_event(available_time_ns=T0), decision_time_ns=T0))
        self.assertFalse(is_temporally_eligible(_event(available_time_ns=T0 + 1), decision_time_ns=T0))

    def test_temporal_eligibility_tuple(self) -> None:
        result = temporal_eligibility(_event(available_time_ns=T0), decision_time_ns=T0)
        self.assertTrue(result.eligible)
        self.assertTrue(result.usable)


if __name__ == "__main__":
    unittest.main()
