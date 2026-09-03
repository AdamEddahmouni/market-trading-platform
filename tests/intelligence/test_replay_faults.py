"""Replay scenario, schedule, and fault engine tests (BUILD 07)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.replay import (  # noqa: E402
    DelayRule,
    DisconnectPolicy,
    DisconnectWindow,
    DropRule,
    ReplayConfigurationError,
    ReplayDecisionSchedule,
    ReplayFaultProfile,
    ReplayMode,
    ThrottleOverflowAction,
    ThrottleRule,
    build_delivery_schedule,
    counterfactual_replay_scenario,
    observed_replay_scenario,
)
from tests.intelligence.test_persistence_fixtures import sample_event  # noqa: E402

T = 1_700_000_000_000_000_000


class ReplayScenarioTests(unittest.TestCase):
    def test_fixed_cadence_schedule(self) -> None:
        schedule = ReplayDecisionSchedule.fixed_cadence(
            start_time_ns=T,
            end_time_ns=T + 30,
            interval_ns=10,
        )
        self.assertEqual(schedule.decision_times_ns, (T, T + 10, T + 20, T + 30))

    def test_invalid_interval_rejected(self) -> None:
        with self.assertRaises(ReplayConfigurationError):
            ReplayDecisionSchedule.fixed_cadence(
                start_time_ns=T,
                end_time_ns=T + 10,
                interval_ns=0,
            )

    def test_scenario_fingerprint_stable(self) -> None:
        schedule = ReplayDecisionSchedule(decision_times_ns=(T, T + 10))
        scenario = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=T + 100,
            decision_schedule=schedule,
        )
        self.assertEqual(scenario.fingerprint(), scenario.fingerprint())

    def test_meaningful_change_changes_fingerprint(self) -> None:
        base = observed_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=T + 100,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(T,)),
        )
        delayed = counterfactual_replay_scenario(
            source_start_time_ns=T,
            source_end_time_ns=T + 100,
            decision_schedule=ReplayDecisionSchedule(decision_times_ns=(T,)),
            fault_profile=ReplayFaultProfile(
                delay_rules=(DelayRule(rule_id="d1", delay_ns=5, event_ids=("evt-1",)),),
            ),
        )
        self.assertNotEqual(base.fingerprint(), delayed.fingerprint())

    def test_observed_with_faults_rejected(self) -> None:
        with self.assertRaises(ReplayConfigurationError):
            from market_platform_foundation.intelligence.replay.scenario import ReplayScenario

            ReplayScenario(
                scenario_version="1",
                mode=ReplayMode.OBSERVED_REPLAY,
                source_start_time_ns=T,
                source_end_time_ns=T + 100,
                decision_start_time_ns=T,
                decision_end_time_ns=T,
                decision_schedule=ReplayDecisionSchedule(decision_times_ns=(T,)),
                fault_profile=ReplayFaultProfile(
                    drop_rules=(DropRule(rule_id="drop", event_ids=("evt-1",)),),
                ),
            )


class ReplayFaultTests(unittest.TestCase):
    def test_observed_delivery_equals_available(self) -> None:
        event = sample_event("evt-1", available_time_ns=T)
        envelopes = build_delivery_schedule(
            (event,),
            mode=ReplayMode.OBSERVED_REPLAY,
            fault_profile=ReplayFaultProfile(),
            replay_end_ns=T + 100,
        )
        self.assertEqual(envelopes[0].effective_delivery_time_ns, T)

    def test_delay_rule(self) -> None:
        event = sample_event("evt-1", available_time_ns=T)
        profile = ReplayFaultProfile(
            delay_rules=(DelayRule(rule_id="delay", delay_ns=5, event_ids=("evt-1",)),),
        )
        envelopes = build_delivery_schedule(
            (event,),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        self.assertEqual(envelopes[0].effective_delivery_time_ns, T + 5)

    def test_drop_rule(self) -> None:
        event = sample_event("evt-1", available_time_ns=T)
        profile = ReplayFaultProfile(
            drop_rules=(DropRule(rule_id="drop", event_ids=("evt-1",)),),
        )
        envelopes = build_delivery_schedule(
            (event,),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        self.assertEqual(envelopes[0].delivery_action.value, "DROP")

    def test_disconnect_drop_boundaries(self) -> None:
        event_start = sample_event("evt-start", available_time_ns=T)
        event_before_end = sample_event("evt-before-end", available_time_ns=T + 9)
        event_at_end = sample_event("evt-end", available_time_ns=T + 10)
        profile = ReplayFaultProfile(
            disconnect_windows=(
                DisconnectWindow(
                    rule_id="disc",
                    provider_id="TEST",
                    start_time_ns=T,
                    end_time_ns=T + 10,
                    policy=DisconnectPolicy.DROP,
                ),
            ),
        )
        envelopes = build_delivery_schedule(
            (event_start, event_before_end, event_at_end),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        by_id = {row.event_id: row for row in envelopes}
        self.assertEqual(by_id["evt-start"].delivery_action.value, "DISCONNECT_DROP")
        self.assertEqual(by_id["evt-before-end"].delivery_action.value, "DISCONNECT_DROP")
        self.assertEqual(by_id["evt-end"].delivery_action.value, "DELIVER")

    def test_out_of_order_via_delay(self) -> None:
        e1 = sample_event("e1", event_time_ns=T, available_time_ns=T)
        e2 = sample_event("e2", event_time_ns=T + 1, available_time_ns=T + 2)
        profile = ReplayFaultProfile(
            delay_rules=(DelayRule(rule_id="delay-e1", delay_ns=5, event_ids=("e1",)),),
        )
        envelopes = build_delivery_schedule(
            (e1, e2),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        by_id = {row.event_id: row for row in envelopes}
        self.assertLess(by_id["e2"].effective_delivery_time_ns, by_id["e1"].effective_delivery_time_ns)

    def test_source_input_order_independence(self) -> None:
        events = (
            sample_event("b", available_time_ns=T + 2),
            sample_event("a", available_time_ns=T + 1),
            sample_event("c", available_time_ns=T + 3),
        )
        shuffled = (events[2], events[0], events[1])
        profile = ReplayFaultProfile(
            delay_rules=(DelayRule(rule_id="d", delay_ns=1, provider_id="TEST"),),
        )
        first = build_delivery_schedule(
            events,
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        second = build_delivery_schedule(
            shuffled,
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        self.assertEqual(
            tuple(row.event_id for row in first),
            tuple(row.event_id for row in second),
        )

    def test_throttle_deterministic(self) -> None:
        events = tuple(sample_event(f"evt-{index}", available_time_ns=T + index) for index in range(4))
        profile = ReplayFaultProfile(
            throttle_rules=(
                ThrottleRule(
                    rule_id="throttle",
                    provider_id="TEST",
                    max_deliveries=2,
                    window_ns=10,
                    overflow_action=ThrottleOverflowAction.DROP,
                ),
            ),
        )
        first = build_delivery_schedule(
            events,
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        second = build_delivery_schedule(
            tuple(reversed(events)),
            mode=ReplayMode.COUNTERFACTUAL,
            fault_profile=profile,
            replay_end_ns=T + 100,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
