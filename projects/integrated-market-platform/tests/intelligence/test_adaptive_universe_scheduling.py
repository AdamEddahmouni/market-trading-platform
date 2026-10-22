"""AUTO-01 — the adaptive full-universe scheduling decision and its optional policy fields.

The scheduler's whole authority is one pure function. These tests pin the decision it makes for each
combination of facts, that identical facts give an identical decision, that a plan which cannot fit is
blocked rather than partially held, and that the adaptive policy fields are optional so a policy written
against the original schema keeps its exact identity and behaviour.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.paper_automation import (  # noqa: E402
    UniverseDecision, optional_fields, required_fields, should_run_universe, universe_fingerprint, universe_material_change,
)
from tests.intelligence.test_paper_automation_policy import body, policy

LEGACY_SCHEDULE = dict(sessions=['REGULAR'], cadence_seconds=300, universe_evaluation_interval_seconds=1800,
                       no_new_entries_minutes_before_close=30)
ADAPTIVE = dict(universe_max_age_seconds=3600, universe_material_change_trigger=True, universe_max_runs_per_day=4)


def facts(**overrides):
    """One complete set of scheduler facts. Every field is the fact's own name, so a test reads as a scenario."""
    schedule = dict(LEGACY_SCHEDULE, **overrides.pop('schedule', {}))
    value = dict(now=10_000.0, schedule=schedule, sessions=schedule['sessions'], session_label='REGULAR',
                 active_run_id=None, last_started_epoch=None, last_complete=None, material_change=[],
                 provider_gate=dict(allowed=True, reason=None), runs_today=dict(started=0), feasibility=None)
    value.update(overrides)
    return value


def decide(**overrides):
    return should_run_universe(facts(**overrides))


class AdaptivePolicyFieldTests(unittest.TestCase):
    def test_the_adaptive_fields_are_optional_and_are_named_apart_from_the_required_ones(self):
        self.assertNotIn('schedule.universe_max_age_seconds', required_fields())
        self.assertEqual(optional_fields(), ['schedule.universe_material_change_trigger', 'schedule.universe_max_age_seconds',
                                             'schedule.universe_max_runs_per_day'])
        legacy = policy()
        self.assertEqual([key for key in ADAPTIVE if key in legacy['schedule']], [])
        # A policy that supplies no adaptive field is byte-identical to one written before they existed, and so
        # keeps the same immutable identity: nothing is silently defaulted into it.
        self.assertEqual(legacy['policy_id'], policy()['policy_id'])
        self.assertEqual(legacy['policy_id'], policy(schedule=dict(sessions=['REGULAR']))['policy_id'])

    def test_supplying_an_adaptive_field_changes_the_identity_and_records_the_owner_value(self):
        legacy, adaptive = policy(), policy(schedule=dict(ADAPTIVE))
        self.assertNotEqual(legacy['policy_id'], adaptive['policy_id'])
        for field, value in ADAPTIVE.items():
            self.assertEqual(adaptive['schedule'][field], value)
        self.assertEqual(policy(schedule=dict(ADAPTIVE))['policy_id'], adaptive['policy_id'])

    def test_an_adaptive_field_is_validated_like_every_other_owner_value(self):
        for value in ('3600', 3600.0, True, None):
            with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_FIELD_INVALID:schedule.universe_max_age_seconds'):
                policy(schedule=dict(universe_max_age_seconds=value))
        for value in (299, 86_401, -1):
            with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_FIELD_OUT_OF_RANGE:schedule.universe_max_age_seconds'):
                policy(schedule=dict(universe_max_age_seconds=value))
        for value in ('4', 4.0, True):
            with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_FIELD_INVALID:schedule.universe_max_runs_per_day'):
                policy(schedule=dict(universe_max_runs_per_day=value))
        for value in (0, 101):
            with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_FIELD_OUT_OF_RANGE:schedule.universe_max_runs_per_day'):
                policy(schedule=dict(universe_max_runs_per_day=value))
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_POLICY_FIELD_INVALID:schedule.universe_material_change_trigger'):
            policy(schedule=dict(universe_material_change_trigger='yes'))

    def test_a_max_age_below_the_minimum_separation_is_a_contradiction_not_a_tighter_schedule(self):
        with self.assertRaisesRegex(ValueError, 'AUTOMATION_SCHEDULE_INVALID'):
            policy(schedule=dict(universe_evaluation_interval_seconds=1800, universe_max_age_seconds=1799))
        self.assertEqual(policy(schedule=dict(universe_evaluation_interval_seconds=1800, universe_max_age_seconds=1800))
                         ['schedule']['universe_max_age_seconds'], 1800)


class UniverseFingerprintTests(unittest.TestCase):
    def test_movement_is_only_reported_for_a_fact_that_was_actually_observed(self):
        base = universe_fingerprint(scope_hash='scope-1', session_date='2026-10-02', universe_count=4622)
        self.assertEqual(universe_material_change(None, base), [])
        self.assertEqual(universe_material_change(base, None), [])
        self.assertEqual(universe_material_change(base, base), [])
        self.assertEqual(universe_material_change(base, universe_fingerprint(scope_hash='scope-1', session_date='2026-10-02',
                                                                            universe_count=4622)), [])
        self.assertEqual(universe_material_change(base, universe_fingerprint(scope_hash='scope-1', session_date='2026-10-03',
                                                                            universe_count=4622)), ['NEW_SESSION'])
        self.assertEqual(universe_material_change(base, universe_fingerprint(scope_hash='scope-2', session_date='2026-10-02',
                                                                            universe_count=4622)), ['SCOPE_CHANGED'])
        self.assertEqual(universe_material_change(base, universe_fingerprint(scope_hash='scope-1', session_date='2026-10-02',
                                                                            universe_count=4600)), ['UNIVERSE_MEMBERSHIP_CHANGED'])
        # An unread row count is not evidence of movement: the controller does not query the Screener to decide
        # whether to query the Screener.
        unread = universe_fingerprint(scope_hash='scope-1', session_date='2026-10-02')
        self.assertEqual(universe_material_change(base, unread), [])
        self.assertEqual(universe_material_change(unread, base), [])
        self.assertEqual(universe_material_change(base, universe_fingerprint(scope_hash='scope-2', session_date='2026-10-03',
                                                                            universe_count=4600)),
                         ['NEW_SESSION', 'SCOPE_CHANGED', 'UNIVERSE_MEMBERSHIP_CHANGED'])


class AdaptiveDecisionTests(unittest.TestCase):
    def assertDecision(self, expected, codes, **overrides):
        result = decide(**overrides)
        self.assertEqual(result['decision'], str(expected))
        self.assertEqual(result['reason_codes'], codes)
        return result

    def test_a_first_ever_evaluation_runs(self):
        self.assertEqual(decide(), dict(decision='RUN', reason_codes=['UNIVERSE_NO_COMPLETE_SELECTION'],
                                        next_eligible_epoch=None, detail={}))

    def test_an_active_run_defers_and_never_starts_a_second_one(self):
        result = self.assertDecision(UniverseDecision.DEFER, ['UNIVERSE_RUN_ACTIVE'], active_run_id='PAR-1')
        self.assertEqual(result['detail'], dict(run_id='PAR-1'))

    def test_a_closed_session_is_blocked(self):
        self.assertDecision(UniverseDecision.BLOCK, ['UNIVERSE_SESSION_NOT_ELIGIBLE'], session_label='CLOSED')

    def test_a_failed_run_backs_off_instead_of_retrying_every_cycle(self):
        result = self.assertDecision(UniverseDecision.DEFER, ['UNIVERSE_RETRY_BACKOFF'], now=10_000.0, backoff_until=10_500.0,
                                     consecutive_failures=3, last_failure_code='PROVIDER_5XX')
        self.assertEqual(result['next_eligible_epoch'], 10_500.0)
        self.assertEqual(result['detail']['consecutive_failures'], 3)
        # Once the backoff has elapsed the ordinary schedule decides again.
        self.assertEqual(decide(now=10_500.0, backoff_until=10_500.0)['decision'], 'RUN')

    def test_an_exhausted_daily_allowance_blocks_and_an_unhealthy_provider_defers(self):
        budget = self.assertDecision(UniverseDecision.BLOCK, ['AUTONOMOUS_SPENDING_LIMIT_REACHED'],
                                     provider_gate=dict(allowed=False, reason='AUTONOMOUS_SPENDING_LIMIT_REACHED', kind='BUDGET'))
        self.assertEqual(budget['detail'], dict(gate='DAILY_ALLOWANCE'))
        health = self.assertDecision(UniverseDecision.DEFER, ['LIVE_FEED_UNHEALTHY'],
                                     provider_gate=dict(allowed=False, reason='LIVE_FEED_UNHEALTHY', kind='DATA'))
        self.assertEqual(health['detail'], dict(gate='PROVIDER_HEALTH'))

    def test_the_owners_daily_run_ceiling_blocks_a_run_that_would_otherwise_be_due(self):
        result = self.assertDecision(UniverseDecision.BLOCK, ['UNIVERSE_DAILY_RUN_LIMIT_REACHED'],
                                     schedule=dict(universe_max_runs_per_day=2), runs_today=dict(started=2),
                                     last_started_epoch=1_000.0)
        self.assertEqual(result['detail'], dict(runs_started=2, runs_per_day=2))
        # Under the ceiling the same facts are allowed through to the ordinary schedule.
        self.assertEqual(decide(schedule=dict(universe_max_runs_per_day=3), runs_today=dict(started=2),
                                last_started_epoch=1_000.0)['decision'], 'RUN')

    def test_a_whole_reservation_that_cannot_fit_is_blocked_never_partially_held(self):
        # Negative control: the previous full run needed 104 requests / 12.5M tokens; 30 / 2M remain.
        result = self.assertDecision(UniverseDecision.BLOCK, ['UNIVERSE_PLAN_INFEASIBLE'],
                                     feasibility=dict(feasible=False, required_requests=104, required_tokens=12_504_440,
                                                      available_requests=30, available_tokens=2_000_000))
        self.assertEqual((result['detail']['required_requests'], result['detail']['available_requests']), (104, 30))
        self.assertEqual(decide(feasibility=dict(feasible=True, required_requests=104, required_tokens=12_504_440,
                                                 available_requests=240, available_tokens=20_000_000))['decision'], 'RUN')

    def test_the_minimum_separation_only_delays_a_run_and_names_when_it_becomes_eligible(self):
        result = self.assertDecision(UniverseDecision.DEFER, ['UNIVERSE_MIN_SEPARATION'], now=10_000.0, last_started_epoch=9_000.0)
        self.assertEqual(result['next_eligible_epoch'], 10_800.0)
        self.assertEqual(result['detail']['remaining_seconds'], 800)
        self.assertEqual(decide(now=10_800.0, last_started_epoch=9_000.0)['decision'], 'RUN')

    def test_a_selection_inside_its_useful_age_and_unchanged_is_skipped(self):
        result = self.assertDecision(UniverseDecision.SKIP, ['UNIVERSE_SELECTION_FRESH_AND_UNCHANGED'],
                                     schedule=dict(universe_max_age_seconds=3600), now=10_000.0, last_started_epoch=8_000.0,
                                     last_complete=dict(finished_at_epoch=9_000.0))
        self.assertEqual(result['next_eligible_epoch'], 12_600.0)
        self.assertEqual(result['detail']['selection_age_seconds'], 1000)
        self.assertEqual(result['detail']['material_change'], ['NO_MATERIAL_CHANGE_OBSERVED'])

    def test_a_material_change_starts_a_run_even_though_the_selection_is_still_fresh(self):
        common = dict(schedule=dict(universe_max_age_seconds=3600, universe_material_change_trigger=True),
                      now=10_000.0, last_started_epoch=8_000.0, last_complete=dict(finished_at_epoch=9_900.0))
        self.assertEqual(decide(**common)['decision'], 'SKIP')
        result = self.assertDecision(UniverseDecision.RUN, ['UNIVERSE_MATERIAL_CHANGE', 'NEW_SESSION'], **common,
                                     material_change=['NEW_SESSION'])
        self.assertEqual(result['detail']['material_change'], ['NEW_SESSION'])
        # The trigger is an owner choice: with it off, the same movement is observed but does not start a run.
        without = dict(common, schedule=dict(common['schedule'], universe_material_change_trigger=False))
        self.assertEqual(decide(**without, material_change=['NEW_SESSION'])['decision'], 'SKIP')

    def test_a_selection_past_its_maximum_useful_age_starts_a_run(self):
        result = self.assertDecision(UniverseDecision.RUN, ['UNIVERSE_SELECTION_MAX_AGE_EXCEEDED'],
                                     schedule=dict(universe_max_age_seconds=3600), now=10_000.0, last_started_epoch=8_000.0,
                                     last_complete=dict(finished_at_epoch=6_000.0))
        self.assertEqual((result['detail']['selection_age_seconds'], result['detail']['max_age_seconds']), (4000, 3600))

    def test_a_legacy_policy_keeps_its_exact_original_behaviour(self):
        # No maximum useful age was configured, so the minimum separation is the whole schedule: wait it out,
        # then run. This is precisely what the fixed timer did, and it is preserved, not relabelled.
        self.assertDecision(UniverseDecision.DEFER, ['UNIVERSE_MIN_SEPARATION'], now=10_000.0, last_started_epoch=9_000.0,
                            last_complete=dict(finished_at_epoch=8_500.0))
        self.assertDecision(UniverseDecision.RUN, ['UNIVERSE_MIN_SEPARATION_ELAPSED'], now=10_800.0, last_started_epoch=9_000.0,
                            last_complete=dict(finished_at_epoch=8_500.0))

    def test_identical_facts_give_an_identical_decision_and_each_result_is_independent(self):
        scenario = facts(schedule=dict(universe_max_age_seconds=3600), now=10_000.0, last_started_epoch=8_000.0,
                         last_complete=dict(finished_at_epoch=9_000.0), material_change=['NEW_SESSION'])
        first, second = should_run_universe(scenario), should_run_universe(scenario)
        self.assertEqual(first, second)
        first['reason_codes'].append('MUTATED')
        self.assertEqual(should_run_universe(scenario), second)

    def test_no_decision_ever_admits_a_run_when_the_resources_or_the_evidence_are_not_there(self):
        # Every refusal is a refusal to pay: none of these may come back as RUN.
        for overrides in (dict(active_run_id='PAR-1'), dict(session_label='CLOSED'),
                          dict(provider_gate=dict(allowed=False, reason='AUTONOMOUS_SPENDING_NOT_AUTHORIZED', kind='BUDGET')),
                          dict(provider_gate=dict(allowed=False, reason='LIVE_FEED_UNHEALTHY', kind='DATA')),
                          dict(feasibility=dict(feasible=False, required_requests=104, available_requests=29)),
                          dict(last_started_epoch=9_999.0), dict(backoff_until=10_001.0)):
            self.assertNotEqual(decide(**overrides)['decision'], 'RUN')


if __name__ == '__main__':
    unittest.main()
