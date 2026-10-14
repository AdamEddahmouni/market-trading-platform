"""Offline session policy and bounded local-record inference planning."""
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from market_platform_foundation.intelligence.inference import paper_automation as policy
from market_platform_foundation.intelligence.inference import synthesis_engines

NY = ZoneInfo('America/New_York')


def record(key, revision='r1', tokens=10, at=1):
    return dict(record_id=key, revision_id=revision, estimated_tokens=tokens, available_at_ns=at,
                token_estimate_scope='REQUEST_AND_OUTPUT_BOUND')


def plan(records=None, **updates):
    options = dict(now=datetime(2026, 10, 13, 3, 30, tzinfo=NY),
                   schedule=dict(max_requests=2, max_tokens=30, max_backlog=4,
                                 universe_evaluation_interval_seconds=300),
                   session_is_trading_day=True, engine='anthropic', model='claude-haiku-5-5',
                   provider_configured=True, provider_available=True, resource_allowed=True,
                   budget_status=dict(requests=0, tokens=0, max_requests=10, max_tokens=100),
                   provider_gate=dict(allowed=True, reason=None), previous=None)
    options.update(updates)
    return policy.plan_local_inference_dry_run(records if records is not None else [record('a')], **options)


class LocalInferenceDryRunTests(unittest.TestCase):
    def test_content_only_or_unverified_estimate_is_not_budget_eligible(self):
        for scope in ('STORED_CONTENT_BYTES_ONLY', None):
            row = record('a')
            row['token_estimate_scope'] = scope
            result = plan([row])
            self.assertEqual(result['planned'], [])
            self.assertEqual(result['deferred'][0]['reason'], 'TOKEN_ESTIMATE_NOT_VERIFIED')

    def test_policy_is_integrated_in_existing_module(self):
        self.assertTrue(callable(getattr(policy, 'plan_local_inference_dry_run', None)))

    def test_exact_session_boundaries(self):
        for hour, minute, expected in ((19, 59, 'AFTER_HOURS'), (20, 0, 'INFERENCE_PAUSE'),
                                      (3, 29, 'INFERENCE_PAUSE'), (3, 30, 'CATCH_UP'),
                                      (4, 0, 'PREMARKET'), (9, 29, 'PREMARKET'),
                                      (9, 30, 'REGULAR'), (15, 59, 'REGULAR'), (16, 0, 'AFTER_HOURS')):
            with self.subTest(hour=hour, minute=minute):
                result = plan(now=datetime(2026, 10, 13, hour, minute, tzinfo=NY))
                self.assertEqual(result['session']['window'], expected)
                self.assertTrue(result['collection_independent'])
                self.assertFalse(result['inference_calls'])
                self.assertEqual(bool(result['planned']), expected != 'INFERENCE_PAUSE')

    def test_weekends_holidays_and_unverified_calendar_defer_truthfully(self):
        for now, calendar, reason in ((datetime(2026, 10, 17, 4, tzinfo=NY), True, 'WEEKEND'),
                                      (datetime(2026, 12, 25, 4, tzinfo=NY), False, 'MARKET_HOLIDAY'),
                                      (datetime(2026, 10, 13, 4, tzinfo=NY), None, 'MARKET_CALENDAR_NOT_VERIFIED')):
            result = plan(now=now, session_is_trading_day=calendar)
            self.assertEqual(result['planned'], [])
            self.assertEqual(result['deferred'][0]['reason'], reason)

    def test_dst_uses_new_york_instants_and_rejects_invalid_wall_time(self):
        # Local 03:30 is 07:30 UTC before spring transition and 08:30 after autumn transition.
        for instant in ('2026-03-09T07:30:00+00:00', '2026-11-02T08:30:00+00:00'):
            self.assertEqual(plan(now=datetime.fromisoformat(instant))['session']['window'], 'CATCH_UP')
        invalid = datetime(2026, 3, 8, 2, 30, tzinfo=NY)
        self.assertEqual(plan(now=invalid)['session']['reason'], 'INVALID_LOCAL_TIME')
        self.assertEqual(plan(now=datetime(2026, 10, 13, 3, 30))['session']['reason'], 'TIMEZONE_REQUIRED')
        # Both explicitly offset autumn folds are real instants, still the weekend pause.
        for fold in (0, 1):
            self.assertEqual(plan(now=datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=fold))['session']['reason'], 'WEEKEND')

    def test_restart_uses_revision_identity_not_watermark_or_article_identity(self):
        previous = dict(processed_revision_ids=[['a', 'r1']], watermark_ns=50)
        before = copy.deepcopy(previous)
        result = plan([record('a'), record('a', 'r2', at=2), record('a', 'r2', at=2), record('b', at=3)], previous=previous)
        self.assertEqual([r['revision_id'] for r in result['planned']], ['r2', 'r1'])
        self.assertEqual(result['restart_state'], before)
        self.assertEqual(previous, before)
        again = plan([record('a', 'r2', at=2)], previous=result['restart_state'])
        self.assertEqual(len(again['planned']), 1)  # a dry run never marks work processed

    def test_saturation_is_bounded_with_deferred_reasons_and_backlog_counts(self):
        result = plan([record(str(i)) for i in range(7)])
        self.assertEqual((len(result['planned']), result['planned_requests'], result['planned_tokens']), (2, 2, 20))
        self.assertEqual((result['scanned_count'], result['unscanned_count']), (4, 3))
        self.assertEqual([r['reason'] for r in result['deferred']], ['REQUEST_BOUND', 'REQUEST_BOUND'])
        self.assertEqual(result['unscanned_reason'], 'BACKLOG_BOUND')

    def test_token_bound_does_not_drop_later_smaller_record(self):
        result = plan([record('large', tokens=31), record('small')])
        self.assertEqual([r['record_id'] for r in result['planned']], ['small'])
        self.assertEqual(result['deferred'][0]['reason'], 'TOKEN_BOUND')

    def test_shared_budget_holds_are_not_counted_twice(self):
        result = plan(budget_status=dict(requests=9, tokens=90, held_requests=4, held_tokens=40,
                                        max_requests=10, max_tokens=100))
        self.assertEqual(len(result['planned']), 1)
        self.assertEqual(plan(budget_status=dict(requests=10, tokens=90, max_requests=10,
                                                max_tokens=100))['model_route']['state'], 'BUDGET_BLOCKED')

    def test_existing_dollar_and_provider_gate_refusals_cannot_be_overridden(self):
        for gate in (dict(allowed=False, reason='EXISTING_DOLLAR_CAP', kind='BUDGET'),
                     dict(allowed=False, reason='PROVIDER_OUTAGE', kind='DATA')):
            result = plan(provider_gate=gate)
            self.assertEqual(result['planned'], [])
            self.assertEqual(result['deferred'][0]['reason'], gate['reason'])
        self.assertEqual(plan(resource_allowed=False)['deferred'][0]['reason'], 'RESOURCE_BLOCKED')

    def test_model_identifier_never_proves_availability(self):
        self.assertEqual(plan(provider_available=None)['model_route']['state'], 'NOT_VERIFIED')
        self.assertEqual(plan(provider_available=False)['model_route']['state'], 'CONFIGURED_UNAVAILABLE')
        self.assertEqual(plan(provider_configured=False)['model_route']['state'], 'CONFIGURED_UNAVAILABLE')
        self.assertEqual(plan(model='Haiku5.5')['model_route']['state'], 'UNSUPPORTED')
        self.assertEqual(plan()['model_route']['state'], 'SUPPORTED')

    def test_offline_model_registry_route_is_callable_without_provider_construction(self):
        self.assertTrue(callable(getattr(synthesis_engines, 'offline_model_route', None)))

    def test_dry_run_cannot_construct_or_call_a_provider_even_when_all_supplied_gates_allow(self):
        from unittest.mock import patch
        with patch('market_platform_foundation.intelligence.inference.anthropic_synthesis.AnthropicSynthesisProvider',
                   side_effect=AssertionError('Provider construction prohibited')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('Network prohibited')):
            result = plan()
        self.assertEqual((len(result['planned']), result['inference_calls'], result['budget_reserved']), (1, 0, False))

    def test_catch_up_reuses_adaptive_cadence_and_existing_run_gate(self):
        facts = dict(now=1000, schedule=dict(universe_evaluation_interval_seconds=300),
                     session_label='REGULAR', sessions=['REGULAR'], provider_gate=dict(allowed=True),
                     last_started_epoch=900)
        result = plan(adaptive_facts=facts)
        self.assertEqual(result['planned'], [])
        self.assertEqual(result['adaptive_decision']['decision'], 'DEFER')
        self.assertEqual(result['deferred'][0]['reason'], 'UNIVERSE_MIN_SEPARATION')

    def test_invalid_budget_or_record_metadata_fail_closed(self):
        for budget in ({}, dict(requests=-1, tokens=0, max_requests=10, max_tokens=100)):
            self.assertEqual(plan(budget_status=budget)['model_route']['state'], 'BUDGET_BLOCKED')
        malformed = record('bad', tokens=-1)
        self.assertEqual(plan([malformed])['deferred'][0]['reason'], 'LOCAL_RECORD_INVALID')
        future = record('future', at=10**20)
        self.assertEqual(plan([future])['deferred'][0]['reason'], 'LOCAL_RECORD_NOT_AVAILABLE')

    def test_optional_session_guard_does_not_change_legacy_adaptive_decision(self):
        facts = dict(now=1000, schedule=dict(universe_evaluation_interval_seconds=300),
                     session_label='REGULAR', sessions=['REGULAR'], provider_gate=dict(allowed=True))
        self.assertEqual(policy.should_run_universe(facts)['decision'], 'RUN')
        facts['inference_session'] = dict(allowed=False, reason='INFERENCE_PAUSE')
        self.assertEqual(policy.should_run_universe(facts)['reason_codes'], ['INFERENCE_PAUSE'])
