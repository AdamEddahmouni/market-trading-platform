"""OCT1-07 next-session snapshot: target session, lock immutability, no look-ahead, outcome split."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.ui_api.screener_next_session import (
    NextSessionService, content_hash, evaluation_policy, next_us_equity_session,
)
from tests.intelligence.test_reevaluation import T0, Clock, Harness, iso

OPEN = 1791293400.0  # 2026-10-06T13:30:00Z, Tuesday 09:30 ET


class TargetSessionTests(unittest.TestCase):
    def target(self, cutoff):
        return next_us_equity_session(cutoff)['target_session_date']

    def test_afternoon_decision_targets_next_market_session_not_plus_24h(self):
        session = next_us_equity_session('2026-10-05T19:55:12Z')  # Monday 15:55 ET
        self.assertEqual((session['target_session_date'], session['target_session_kind'], session['target_timezone']),
                         ('2026-10-06', 'US_EQUITY_RTH', 'America/New_York'))
        self.assertEqual((session['target_session_start'], session['target_session_end']), ('2026-10-06T13:30:00Z', '2026-10-06T20:00:00Z'))
        self.assertEqual(session['early_close_metadata'], 'UNAVAILABLE')

    def test_friday_targets_monday_not_saturday(self):
        self.assertEqual(self.target('2026-10-09T19:55:00Z'), '2026-10-12')
        self.assertEqual(self.target('2026-10-10T15:00:00Z'), '2026-10-12')  # Saturday decision

    def test_market_holiday_is_skipped_from_the_calendar_authority(self):
        self.assertEqual(self.target('2026-11-25T20:55:00Z'), '2026-11-27')  # Thanksgiving closed
        self.assertEqual(self.target('2026-12-24T20:55:00Z'), '2026-12-28')  # Christmas Friday + weekend
        self.assertEqual(self.target('2026-07-02T19:55:00Z'), '2026-07-06')  # observed Independence Day + weekend

    def test_premarket_decision_targets_the_same_day_session(self):
        self.assertEqual(self.target('2026-10-05T12:00:00Z'), '2026-10-05')
        self.assertEqual(self.target('2026-10-05T13:30:00Z'), '2026-10-06')  # at the open is no longer "before" it

    def test_outside_calendar_coverage_fails_visibly(self):
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_CALENDAR_UNAVAILABLE'): self.target('2026-12-31T20:55:00Z')
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_CLOCK_INVALID'): self.target('tomorrow')

    def test_evaluation_policy_is_an_allowlist_with_separate_horizon(self):
        session = next_us_equity_session('2026-10-05T19:55:00Z')
        opening = evaluation_policy('next-session-open-30m/1.0.0', session)
        self.assertEqual((opening['observation_start'], opening['observation_end']), ('2026-10-06T13:30:00Z', '2026-10-06T14:00:00Z'))
        self.assertEqual(evaluation_policy('next-session-close/1.0.0', session)['observation_end'], session['target_session_end'])
        with self.assertRaisesRegex(ValueError, 'UNAUTHORIZED'): evaluation_policy('best-looking-horizon', session)


class NextSessionTests(unittest.TestCase):
    def setUp(self, connection=None):
        self.h = Harness(connection=connection)
        self.quote = None
        self.service = NextSessionService(self.h.store, repository=self.h.repo, actions=self.h.actions, clock=self.h.clock,
                                          quote_reader=lambda instrument, now: self.quote)
        self.h.configure()
        self.h.service.run_once()
        self.decision = self.h.history()[0]

    def locked(self):
        draft = self.service.draft(dict(decision_id=self.decision['decision_id']))
        return self.service.lock(dict(snapshot_id=draft['snapshot']['snapshot_id']))['snapshot']

    def observe(self, at, price, source=None):
        self.h.clock.value = at
        self.quote = dict(price=price, as_of=iso(source if source is not None else at), source='CONTROLLED_FIXTURE', delivery_mode='REALTIME')
        return self.service.observe(dict(snapshot_id=self.snapshot_id))

    def test_draft_references_the_real_action_decision(self):
        view = self.service.draft(dict(decision_id=self.decision['decision_id']))
        snapshot = view['snapshot']
        self.assertEqual((snapshot['schema_version'], snapshot['lock_state'], snapshot['state']), ('next-session-decision/1.0.0', 'DRAFT', 'DRAFT'))
        self.assertEqual((snapshot['action_decision_id'], snapshot['action_state'], snapshot['direction']), (self.decision['decision_id'], 'ENTER', 'LONG'))
        self.assertEqual((snapshot['evidence_snapshot_ref'], snapshot['input_hash']), (self.decision['evidence_snapshot_id'], self.decision['input_hash']))
        self.assertEqual((snapshot['decision_cutoff'], snapshot['target_session_date'], snapshot['reference_price']), (iso(T0), '2026-10-06', 150.0))
        self.assertEqual((snapshot['position_state'], snapshot['account_id'], snapshot['run_kind'], snapshot['test_mode']), ('FLAT', 'controlled', 'FORWARD_TEST', 'SIGNAL_ONLY'))
        self.assertNotIn('evidence_snapshot', snapshot)  # reference, not a second copy of the payload
        self.assertEqual(view['integrity'], 'VERIFIED')

    def test_generic_or_unavailable_evaluations_cannot_be_frozen(self):
        with self.assertRaisesRegex(ValueError, 'ACTION_DECISION_NOT_FOUND'): self.service.draft(dict(decision_id='reduction-1'))
        self.h.ai.no_quote.add('US:NVDA')
        self.h.tick()
        with self.assertRaisesRegex(ValueError, 'ACTION_EVALUATION_UNAVAILABLE'): self.service.draft(dict(decision_id=self.h.history()[0]['decision_id']))
        crypto = dict(self.decision, decision_id='crypto', instrument=dict(instrument_id='KRAKEN:XBT', universe='CRYPTO'))
        self.h.action_repo.put('decision', 'crypto', crypto)
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_CALENDAR_UNAVAILABLE'): self.service.draft(dict(decision_id='crypto'))
        for bad in (None, {}, dict(decision_id=''), dict(decision_id='a', price=1), dict(decision_id='a', evaluation_policy=1)):
            with self.assertRaises(ValueError): self.service.draft(bad)

    def test_lock_makes_every_frozen_field_immutable(self):
        snapshot = self.locked()
        self.assertEqual((snapshot['lock_state'], snapshot['state'], snapshot['locked_at']), ('LOCKED', 'LOCKED', iso(T0)))
        for field, value in (('action_state', 'EXIT'), ('direction', 'SHORT'), ('evidence_snapshot_ref', 'AS-other'),
                             ('target_session_date', '2026-10-07'), ('reference_price', 1.0), ('model_id', 'other'), ('prompt_hash', 'x'),
                             ('evaluation_policy', dict(snapshot['evaluation_policy'], observation_end='2026-10-06T20:00:00Z')),
                             ('lock_state', 'DRAFT'), ('locked_at', iso(T0 + 1))):
            with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_LOCKED_IMMUTABLE'):
                self.h.repo.put_snapshot(dict(snapshot, **{field: value}))
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_LOCKED_IMMUTABLE'):
            self.service.draft(dict(decision_id=self.decision['decision_id'], evaluation_policy='next-session-close/1.0.0'))
        again = self.service.draft(dict(decision_id=self.decision['decision_id']))['snapshot']
        self.assertEqual(again, self.h.repo.get_snapshot(snapshot['snapshot_id']))
        self.assertEqual(self.service.lock(dict(snapshot_id=snapshot['snapshot_id']))['snapshot'], snapshot)  # idempotent
        self.assertEqual(content_hash(snapshot), snapshot['content_hash'])

    def test_draft_policy_can_change_only_before_lock(self):
        first = self.service.draft(dict(decision_id=self.decision['decision_id']))['snapshot']
        second = self.service.draft(dict(decision_id=self.decision['decision_id'], evaluation_policy='next-session-close/1.0.0'))['snapshot']
        self.assertEqual(first['snapshot_id'], second['snapshot_id'])
        self.assertEqual(second['evaluation_policy']['observation_end'], '2026-10-06T20:00:00Z')

    def test_lock_refuses_look_ahead(self):
        draft = self.service.draft(dict(decision_id=self.decision['decision_id']))['snapshot']
        self.h.clock.value = OPEN + 1  # the target observation window has started
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_LOCK_AFTER_OBSERVATION_START'): self.service.lock(dict(snapshot_id=draft['snapshot_id']))
        self.h.clock.value = T0
        tampered = copy.deepcopy(self.decision)
        tampered['evidence_snapshot']['evidence']['current_market_evidence'][0]['as_of'] = iso(T0 + 60)
        self.h.actions.repository = Mock(get=Mock(return_value=tampered))
        with self.assertRaisesRegex(ValueError, 'FORWARD_TEST_FUTURE_SOURCE_TIME'): self.service.lock(dict(snapshot_id=draft['snapshot_id']))

    def test_later_evidence_and_reevaluation_never_enter_the_frozen_snapshot(self):
        snapshot = self.locked()
        frozen_decision = copy.deepcopy(self.h.action_repo.get('decision', snapshot['action_decision_id']))
        self.h.ai.reference = [dict(evidence_id='late-news', capability='NEWS', role='REFERENCE_CONTEXT', source='RSS', delivery_mode='SNAPSHOT',
                                    freshness_status='CURRENT', decision_admissibility='ADMISSIBLE', as_of=iso(T0 + 60), valid_until=iso(T0 + 7200),
                                    policy='news-reference/1', basis='PUBLICATION', weak_reasons=[], facts=dict(headline='Arrived later'))]
        self.h.hold(10)
        self.h.tick()  # T0 + 60: a new decision linked to the late evidence
        later = self.h.history()[0]
        self.assertIn('late-news', [e['evidence_id'] for e in later['evidence_snapshot']['evidence']['reference_evidence']])
        self.assertEqual(self.h.repo.get_snapshot(snapshot['snapshot_id']), snapshot)
        self.assertEqual(self.h.action_repo.get('decision', snapshot['action_decision_id']), frozen_decision)
        self.assertEqual(frozen_decision['evidence_snapshot']['evidence']['reference_evidence'], [])
        self.assertLessEqual(snapshot['evidence_max_time'], snapshot['decision_cutoff'])
        self.assertEqual(self.service.read(snapshot['snapshot_id'])['integrity'], 'VERIFIED')

    def test_observation_clocks_are_guarded(self):
        self.snapshot_id = self.locked()['snapshot_id']
        with self.assertRaisesRegex(ValueError, 'FORWARD_TEST_TEMPORAL_VIOLATION'): self.observe(T0 + 60, 151.0, source=T0 - 1)
        with self.assertRaisesRegex(ValueError, 'FORWARD_TEST_FUTURE_INPUT_REJECTED'): self.observe(T0 + 60, 151.0, source=T0 + 120)
        self.h.clock.value = T0 - 5
        self.quote = dict(price=151.0, as_of=iso(T0 - 5))
        with self.assertRaisesRegex(ValueError, 'FORWARD_TEST_OBSERVATION_BEFORE_DECISION'): self.service.observe(dict(snapshot_id=self.snapshot_id))
        self.h.clock.value = T0 + 60
        self.quote = None
        with self.assertRaisesRegex(ValueError, 'OBSERVATION_QUOTE_UNAVAILABLE'): self.service.observe(dict(snapshot_id=self.snapshot_id))
        with self.assertRaises(ValueError): self.service.observe(dict(snapshot_id=self.snapshot_id, price=999))  # browser cannot supply a price
        self.assertEqual(self.h.repo.observations(self.snapshot_id), [])

    def test_unlocked_snapshot_cannot_be_observed_or_evaluated(self):
        draft = self.service.draft(dict(decision_id=self.decision['decision_id']))['snapshot']
        self.snapshot_id = draft['snapshot_id']
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_NOT_LOCKED'): self.observe(OPEN + 60, 151.0)
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_NOT_LOCKED'): self.service.evaluate(dict(snapshot_id=self.snapshot_id))

    def test_evaluation_before_frozen_horizon_is_rejected(self):
        snapshot = self.locked()
        self.snapshot_id = snapshot['snapshot_id']
        view = self.observe(OPEN + 300, 153.0)
        self.assertEqual(view['snapshot']['state'], 'OBSERVING')
        with self.assertRaisesRegex(ValueError, 'FORWARD_TEST_HORIZON_NOT_REACHED'): self.service.evaluate(dict(snapshot_id=self.snapshot_id))
        self.assertIsNone(self.h.repo.get_snapshot(self.snapshot_id)['evaluation'])

    def test_later_outcome_is_compared_and_original_is_unchanged(self):
        snapshot = self.locked()
        self.snapshot_id = snapshot['snapshot_id']
        self.observe(T0 + 3600, 149.0)  # same afternoon: retained but outside the frozen window
        self.observe(OPEN + 60, 151.5)
        self.h.hold(10)
        self.h.ai.rows['US:NVDA']['price'] = 153.0
        self.h.service.run_once()  # a later reevaluation: HOLD
        view = self.observe(OPEN + 1500, 153.0)
        self.assertEqual((view['snapshot']['state'], view['observation_count']), ('OBSERVING', 3))
        self.assertEqual([o['in_window'] for o in view['observations']], [False, True, True])
        self.h.clock.value = OPEN + 1800
        self.assertEqual(self.service.read(self.snapshot_id)['snapshot']['state'], 'EVALUABLE')
        evaluated = self.service.evaluate(dict(snapshot_id=self.snapshot_id))
        result = evaluated['snapshot']['evaluation']
        self.assertEqual(evaluated['snapshot']['state'], 'EVALUATED')
        self.assertEqual((result['frozen_action_state'], result['frozen_direction'], result['decision_reference_price']), ('ENTER', 'LONG', 150.0))
        self.assertEqual((result['first_observed_price'], result['last_observed_price'], result['change_pct']), (151.5, 153.0, 2.0))
        self.assertEqual((result['subsequent_action_state'], result['position_state_now'], result['in_window_observations']), ('HOLD', 'LONG', 2))
        self.assertEqual(result['elapsed_seconds'], int(OPEN + 1500 - T0))
        self.assertEqual(result['signal_outcome']['quality'], 'COMPLETE')
        self.assertEqual(result['basis'], 'OBSERVATION_ONLY_NOT_PERFORMANCE_EVIDENCE')
        frozen = lambda record: {k: v for k, v in record.items() if k not in ('state', 'evaluation', 'updated_at')}
        self.assertEqual(frozen(evaluated['snapshot']), frozen(snapshot))
        self.assertEqual(evaluated['integrity'], 'VERIFIED')
        self.assertEqual(self.service.evaluate(dict(snapshot_id=self.snapshot_id))['snapshot'], evaluated['snapshot'])  # idempotent, never re-picked
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_ALREADY_EVALUATED'): self.observe(OPEN + 5000, 200.0)
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_EVALUATION_IMMUTABLE'):
            self.h.repo.put_snapshot(dict(evaluated['snapshot'], evaluation=dict(result, change_pct=99)))

    def test_signal_without_paper_execution_is_not_applicable_not_zero(self):
        self.snapshot_id = self.locked()['snapshot_id']
        self.observe(OPEN + 60, 151.5)
        self.h.clock.value = OPEN + 1800
        outcome = self.service.evaluate(dict(snapshot_id=self.snapshot_id))['snapshot']['evaluation']['execution_outcome']
        self.assertEqual((outcome['quality'], outcome['realized_pnl_minor'], outcome['paper_order_id'], outcome['fill_count']), ('NOT_APPLICABLE', None, None, 0))

    def test_execution_outcome_requires_a_real_paper_order_for_this_decision(self):
        snapshot = self.locked()
        self.snapshot_id = snapshot['snapshot_id']
        self.h.ledger.project_orders = Mock(return_value=[dict(order_id='order-1', intent_id='intent-1', state='FILLED', instrument_id='US:NVDA',
            decision_source_snapshot=dict(reasons=[dict(code='ACTION_DECISION', label=snapshot['action_decision_id'])]))])
        self.observe(OPEN + 60, 151.5)
        self.h.clock.value = OPEN + 1800
        outcome = self.service.evaluate(dict(snapshot_id=self.snapshot_id))['snapshot']['evaluation']['execution_outcome']
        self.assertEqual((outcome['quality'], outcome['paper_order_id'], outcome['fill_count'], outcome['realized_pnl_minor']), ('COMPLETE', 'order-1', 1, None))

    def test_no_in_window_observation_is_insufficient_data(self):
        self.snapshot_id = self.locked()['snapshot_id']
        self.h.clock.value = OPEN + 1800
        evaluated = self.service.evaluate(dict(snapshot_id=self.snapshot_id))['snapshot']
        self.assertEqual((evaluated['state'], evaluated['evaluation']['signal_outcome']['quality']), ('INSUFFICIENT_DATA', 'INSUFFICIENT_DATA'))
        self.assertIsNone(evaluated['evaluation']['change_pct'])

    def test_account_isolation_and_history(self):
        snapshot = self.locked()
        self.assertEqual([v['snapshot']['snapshot_id'] for v in self.service.history('US:NVDA')], [snapshot['snapshot_id']])
        self.h.ledger.paper_account_id = 'another-account'
        with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_NOT_FOUND'): self.service.read(snapshot['snapshot_id'])
        self.assertEqual(self.service.history('US:NVDA'), [])

    def test_locked_snapshot_observations_and_config_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'state.sqlite'
            connection = LocalStateConnection(path)
            self.setUp(connection)
            snapshot = self.locked()
            self.snapshot_id = snapshot['snapshot_id']
            self.observe(OPEN + 60, 151.5)
            connection.close()

            connection = LocalStateConnection(path)
            restored = Harness(connection=connection, clock=Clock(OPEN + 120))
            service = NextSessionService(restored.store, repository=restored.repo, actions=restored.actions, clock=restored.clock)
            view = service.read(snapshot['snapshot_id'])
            self.assertEqual({k: v for k, v in view['snapshot'].items() if k not in ('state', 'updated_at')},
                             {k: v for k, v in snapshot.items() if k not in ('state', 'updated_at')})
            self.assertEqual((view['snapshot']['lock_state'], view['observation_count'], view['durability']), ('LOCKED', 1, 'SQLITE_LOCAL_STATE'))
            with self.assertRaisesRegex(ValueError, 'NEXT_SESSION_LOCKED_IMMUTABLE'):
                restored.repo.put_snapshot(dict(view['snapshot'], action_state='EXIT'))
            self.assertEqual(restored.service.status()['requested_cadence_seconds'], 60)
            self.assertEqual(len(restored.repo.cycles(restored.service._loop()['loop_id'])), 1)
            connection.close()


if __name__ == '__main__':
    unittest.main()
