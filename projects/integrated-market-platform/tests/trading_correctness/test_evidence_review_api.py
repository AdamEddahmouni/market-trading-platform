"""Operator evidence review: stored news, catch-up dry run, decision journal and as-of replay.

SOFTWARE_CONTROLLED. Articles are synthetic, the store is a disposable schema-13 file, the model
facts and budget are supplied fixtures, and decisions come from the controlled lifecycle base.
Nothing here is market evidence, a model call or a profitability claim.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.evaluations import EvaluationRepository
from market_platform_foundation.local_state.reevaluation import ReevaluationRepository
from market_platform_foundation.news.collection import CollectionJob, NewsCollector
from market_platform_foundation.news.normalize import normalize_raw_item
from market_platform_foundation.platform.security.route_policy import policy_for_route
from market_platform_foundation.ui_api.evidence_review import EvidenceReviewService
from market_platform_foundation.ui_api.prospective_evaluation import ProspectiveEvaluationService
from market_platform_foundation.ui_api.server import UiApiHandler
from tests.trading_correctness.test_trade_lifecycle import _Lifecycle, iso


# The payloads the UI tests parse. The Python tests below hold this file to the service's real output.
UI_FIXTURE = Path(__file__).resolve().parents[2] / 'ui/src/components/evaluation/evidenceReviewFixture.json'


def epoch(text):
    return datetime.fromisoformat(text).timestamp()


def reasons(plan):
    return {row['reason']: row['count'] for row in plan['deferred_reasons']}


class Settings:
    """The saved engine choice as the Screener exposes it; configuration only."""

    def __init__(self, *, engine='anthropic', model='claude-haiku-4-5-20251001', configured=True):
        self.choice = dict(engine=engine, model=model, source='OPERATOR')
        self.configured = configured

    def current(self):
        return dict(self.choice)

    def options(self):
        return [dict(id='local', runtime='LOCAL_MODEL', default_model=None, state='NOT_CONFIGURED',
                     reason='NO_SYNTHESIS_PROVIDER_CONFIGURED'),
                dict(id='anthropic', runtime='PAID_API', default_model='claude-sonnet-5-5',
                     state='AVAILABLE' if self.configured else 'NOT_CONFIGURED',
                     reason=None if self.configured else 'ANTHROPIC_API_KEY_NOT_SET')]


class StoredEvidenceTests(unittest.TestCase):
    """Wednesday 2026-10-14, a regular session in the existing holiday table."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'imp-state.sqlite3'
        self.connection = LocalStateConnection(self.path)
        self.addCleanup(lambda: self.connection.close())
        self.now = epoch('2026-10-14T00:10:00+00:00')  # 20:10 New York on the 13th: collection continues overnight
        self.raw = dict(provider_native_id='wire-1', headline='AAPL reports earnings', summary='Revenue was 10',
                        tickers=['AAPL'], url='https://example.test/wire-1', published_time='2026-10-13T23:00:00Z')
        self.collector = NewsCollector(self.connection, [CollectionJob('finviz', '', 'US_EQUITIES', 120)], self.fetch,
                                       clock=lambda: self.now)
        self.budget = dict(day='2026-10-14', requests=0, tokens=0, max_requests=30, max_tokens=200_000,
                           usage_overrun=False, held_requests=0, held_tokens=0)
        self.settings = Settings()

    def fetch(self, job):
        article = normalize_raw_item(self.raw, provider_id=job.provider, source_id='wire',
                                     retrieved_time=datetime.fromtimestamp(self.now, timezone.utc).isoformat())
        return [(article, dict(source_type='NEWS', evidence_class='SOFTWARE_FIXTURE_ONLY',
                               license='SYNTHETIC_FIXTURE', source_reference='evidence-review/synthetic/1'))], {'state': 'CURRENT'}

    def collect(self, at, **changes):
        self.now = epoch(at)
        self.raw.update(changes)
        self.collector.step()

    def service(self, *, connection='own', at=None):
        clock = (lambda: epoch(at)) if at else (lambda: self.now)
        return EvidenceReviewService(SimpleNamespace(), connection=self.connection if connection == 'own' else connection,
                                     settings=self.settings, budget=lambda: dict(self.budget), clock=clock)

    def three_overnight_articles(self):
        self.collect('2026-10-14T00:10:00+00:00')
        self.collect('2026-10-14T02:00:00+00:00', provider_native_id='wire-2', url='https://example.test/wire-2',
                     headline='MSFT guidance')
        self.collect('2026-10-14T05:00:00+00:00', provider_native_id='wire-3', url='https://example.test/wire-3',
                     headline='NVDA supply note')

    def ui_payloads(self):
        """A corrected article plus two more stored overnight, read at 03:30 New York."""
        self.three_overnight_articles()
        self.collect('2026-10-14T06:00:00+00:00', provider_native_id='wire-1', url='https://example.test/wire-1',
                     headline='AAPL reports earnings', summary='Revenue was 12 (corrected)')
        svc = self.service(at='2026-10-14T07:30:00+00:00')
        return json.loads(json.dumps(dict(
            status=svc.status(), knowledge=svc.knowledge(),
            plan=svc.plan(max_requests='2', request_allowance='4096', assume_available=True),
            replay=svc.replay(replay_date='2026-09-09', as_of='2026-09-09T14:10:00Z'))))

    def test_ui_fixture_is_the_service_output(self):
        fixture = json.loads(UI_FIXTURE.read_text(encoding='utf-8'))
        payloads = self.ui_payloads()
        self.assertEqual({name: fixture[name] for name in payloads}, payloads)

    # --- stored knowledge -------------------------------------------------------------
    def test_correction_is_versioned_and_each_cutoff_sees_what_was_known(self):
        self.collect('2026-10-14T00:10:00+00:00')
        self.collect('2026-10-14T00:13:00+00:00')  # unchanged re-poll stores nothing
        self.collect('2026-10-14T03:00:00+00:00', summary='Revenue was 12 (corrected)')
        svc = self.service(at='2026-10-14T04:00:00+00:00')
        before = svc.knowledge(as_of='2026-10-14T01:00:00Z')
        after = svc.knowledge(as_of='2026-10-14T03:30:00Z')
        self.assertEqual([r['summary'] for r in before['records']], ['Revenue was 10'])
        self.assertEqual([r['summary'] for r in after['records']], ['Revenue was 12 (corrected)'])
        self.assertEqual(after['records'][0]['supersedes_record_id'], before['records'][0]['record_id'])
        self.assertEqual(after['records'][0]['article_id'], before['records'][0]['article_id'])
        versions = svc.knowledge(as_of='2026-10-14T03:30:00Z', include_revisions=True)
        self.assertEqual(sorted(r['summary'] for r in versions['records']), ['Revenue was 10', 'Revenue was 12 (corrected)'])
        self.assertEqual(svc.knowledge_store()['records'], 2)
        row = after['records'][0]
        self.assertEqual((row['source_id'], row['provider_id'], row['url'], row['instruments']),
                         ('wire', 'finviz', 'https://example.test/wire-1', ['AAPL']))
        self.assertEqual((row['evidence_class'], row['source_reference']), ('SOFTWARE_FIXTURE_ONLY', 'evidence-review/synthetic/1'))
        self.assertEqual((row['published_time'], row['first_observed_time'], row['available_time']),
                         ('2026-10-13T23:00:00Z', '2026-10-14T00:10:00Z', '2026-10-14T03:00:00Z'))

    def test_late_arrival_with_an_earlier_publication_time_is_not_known_earlier(self):
        self.collect('2026-10-14T00:10:00+00:00')
        self.collect('2026-10-14T12:00:00+00:00', provider_native_id='late', url='https://example.test/late',
                     published_time='2026-10-13T22:00:00Z')
        svc = self.service(at='2026-10-14T13:00:00+00:00')
        self.assertEqual(svc.knowledge(as_of='2026-10-14T11:59:59Z')['count'], 1)
        self.assertEqual(svc.knowledge(as_of='2026-10-14T12:00:00Z')['count'], 2)
        self.assertEqual(svc.knowledge()['count'], 2)
        self.assertEqual(svc.knowledge(symbol='AAPL')['count'], 2)
        self.assertEqual(svc.knowledge(symbol='TSLA')['count'], 0)
        self.assertEqual(svc.knowledge(source_id='other')['count'], 0)

    def test_future_or_naive_cutoff_and_bad_limit_are_refused(self):
        svc = self.service(at='2026-10-14T04:00:00+00:00')
        for value in ('2026-10-14T04:00:01Z', '2026-10-14T03:00:00', 'yesterday'):
            with self.assertRaisesRegex(ValueError, 'INVALID_EVIDENCE_CUTOFF'):
                svc.knowledge(as_of=value)
        for value in ('0', '201', 'many'):
            with self.assertRaisesRegex(ValueError, 'INVALID_EVIDENCE_LIMIT'):
                svc.knowledge(limit=value)

    def test_unavailable_empty_and_restarted_stores_are_reported_as_they_are(self):
        self.assertEqual(self.service(at='2026-10-14T04:00:00+00:00').knowledge()['store']['state'], 'EMPTY')
        with patch('market_platform_foundation.local_state.paths.persistence_enabled', return_value=False):
            absent = self.service(connection=None, at='2026-10-14T04:00:00+00:00')
            self.assertEqual(absent.knowledge()['store'], dict(state='UNAVAILABLE', reason='DURABLE_STATE_DISABLED',
                                                               records=None, latest_ingested_time=None))
            self.assertEqual(absent.plan()['candidates'], 0)
        legacy = SimpleNamespace(fetchone=lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError('no such table')))
        self.assertEqual(self.service(connection=legacy).knowledge_store()['reason'], 'NEWS_COLLECTION_STORE_MISSING')
        self.collect('2026-10-14T00:10:00+00:00')
        self.connection.close()
        self.connection = LocalStateConnection(self.path, require_existing=True)
        reopened = self.service(at='2026-10-14T04:00:00+00:00').knowledge()
        self.assertEqual((reopened['store']['state'], reopened['count']), ('AVAILABLE', 1))
        self.assertEqual(reopened['store']['latest_ingested_time'], '2026-10-14T00:10:00Z')

    # --- catch-up dry run -------------------------------------------------------------
    def test_pause_then_catch_up_plans_a_bounded_batch_and_defers_the_rest(self):
        self.three_overnight_articles()
        options = dict(max_requests='2', request_allowance='4096', assume_available=True)
        paused = self.service(at='2026-10-14T06:00:00+00:00').plan(**options)  # 02:00 New York
        self.assertEqual((paused['session']['window'], paused['planned_requests'], reasons(paused)),
                         ('INFERENCE_PAUSE', 0, {'INFERENCE_PAUSE': 3}))
        self.assertTrue(paused['collection_independent'])
        morning = self.service(at='2026-10-14T07:30:00+00:00').plan(**options)  # 03:30 New York
        self.assertEqual((morning['session']['window'], morning['candidates'], morning['planned_requests']), ('CATCH_UP', 3, 2))
        self.assertEqual([row['headline'] for row in morning['planned']], ['AAPL reports earnings', 'MSFT guidance'])
        self.assertEqual(reasons(morning), {'REQUEST_BOUND': 1})
        self.assertEqual(morning['deferred'][0]['headline'], 'NVDA supply note')
        self.assertEqual(morning['planned'][0]['available_time'], '2026-10-14T00:10:00Z')
        self.assertEqual(morning['planned_tokens'], sum(row['worst_case_tokens'] for row in morning['planned']))
        self.assertTrue(all(row['worst_case_tokens'] > 4096 for row in morning['planned']))
        self.assertEqual((morning['availability_basis'], morning['estimate_basis']),
                         ('OPERATOR_ASSUMPTION_FOR_PREVIEW', 'STORED_BYTES_PLUS_OPERATOR_ALLOWANCE'))
        self.assertEqual((morning['inference_calls'], morning['budget_reserved'], morning['dry_run']), (0, False, True))
        self.assertEqual(morning['processed_state'], 'NO_COMPLETED_ANALYSIS_RECORDED')
        tokens = self.service(at='2026-10-14T07:30:00+00:00').plan(
            max_tokens=str(morning['planned'][0]['worst_case_tokens']), request_allowance='4096', assume_available=True)
        self.assertEqual((tokens['planned_requests'], reasons(tokens)), (1, {'TOKEN_BOUND': 2}))

    def test_nothing_is_planned_without_a_request_bound_or_verified_availability(self):
        self.three_overnight_articles()
        svc = self.service(at='2026-10-14T07:30:00+00:00')
        unverified = svc.plan(request_allowance='4096')
        self.assertEqual((unverified['planned_requests'], reasons(unverified), unverified['availability_basis']),
                         (0, {'MODEL_AVAILABILITY_NOT_VERIFIED': 3}, 'NOT_VERIFIED'))
        self.assertEqual(unverified['model_route']['state'], 'NOT_VERIFIED')
        content_only = svc.plan(assume_available=True)
        self.assertEqual((content_only['planned_requests'], reasons(content_only), content_only['estimate_basis']),
                         (0, {'TOKEN_ESTIMATE_NOT_VERIFIED': 3}, 'STORED_CONTENT_BYTES_ONLY'))
        self.settings = Settings(configured=False)
        missing = self.service(at='2026-10-14T07:30:00+00:00').plan(request_allowance='4096', assume_available=True)
        self.assertEqual((missing['planned_requests'], reasons(missing)), (0, {'PROVIDER_NOT_CONFIGURED': 3}))
        self.settings = Settings(model='claude-haiku-9')  # not in the catalog: no request contract on record
        unknown = self.service(at='2026-10-14T07:30:00+00:00').plan(request_allowance='4096', assume_available=True)
        self.assertEqual(reasons(unknown), {'MODEL_REQUEST_CONTRACT_UNSUPPORTED': 3})

    def test_recorded_budget_bounds_the_plan_and_operator_bounds_only_tighten_it(self):
        self.three_overnight_articles()
        options = dict(request_allowance='4096', assume_available=True)
        self.budget.update(requests=29)
        one = self.service(at='2026-10-14T07:30:00+00:00').plan(max_requests='25', **options)
        self.assertEqual((one['planned_requests'], reasons(one), one['bounds']['max_requests']),
                         (1, {'REQUEST_BOUND': 2}, 25))
        self.budget.update(requests=30)
        spent = self.service(at='2026-10-14T07:30:00+00:00').plan(**options)
        self.assertEqual((spent['planned_requests'], reasons(spent)), (0, {'INFERENCE_BUDGET_BLOCKED': 3}))
        self.budget.update(requests=0, usage_overrun=True)
        overrun = self.service(at='2026-10-14T07:30:00+00:00').plan(**options)
        self.assertEqual(reasons(overrun), {'INFERENCE_BUDGET_BLOCKED': 3})
        self.budget = dict(source='BUDGET_STATE_UNREADABLE', reason='SYNTHESIS_BUDGET_STATE_UNREADABLE')
        unreadable = self.service(at='2026-10-14T07:30:00+00:00').plan(**options)
        self.assertEqual((unreadable['planned_requests'], unreadable['bounds']['max_requests']), (0, 0))

    def test_session_windows_calendar_and_preview_clock(self):
        svc = self.service(at='2026-10-14T00:10:00+00:00')
        self.assertEqual(svc.status()['session']['window'], 'INFERENCE_PAUSE')
        windows = {clock: svc.plan(at=clock)['session']['window'] for clock in (
            '2026-10-14T07:29:59Z', '2026-10-14T07:30:00Z', '2026-10-14T08:00:00Z', '2026-10-14T13:30:00Z',
            '2026-10-14T20:00:00Z', '2026-10-15T00:00:00Z')}
        self.assertEqual(list(windows.values()), ['INFERENCE_PAUSE', 'CATCH_UP', 'PREMARKET', 'REGULAR', 'AFTER_HOURS',
                                                  'INFERENCE_PAUSE'])
        preview = svc.plan(at='2026-10-14T07:30:00Z')
        self.assertEqual((preview['clock_source'], preview['evidence_as_of'], preview['planned_for']),
                         ('OPERATOR_PREVIEW_CLOCK', '2026-10-14T00:10:00Z', '2026-10-14T07:30:00Z'))
        self.assertEqual(svc.plan(at='2026-10-17T14:00:00Z')['session']['reason'], 'WEEKEND')
        self.assertEqual(svc.plan(at='2026-11-26T15:00:00Z')['session']['reason'], 'MARKET_HOLIDAY')
        uncovered = svc.plan(at='2031-03-05T15:00:00Z')['session']
        self.assertEqual((uncovered['reason'], uncovered['trading_day_basis']),
                         ('MARKET_CALENDAR_NOT_VERIFIED', 'CALENDAR_YEAR_NOT_COVERED'))
        # 2026-11-01 01:30 New York happens twice; both instants are the pause, and 03:30 that day is a Sunday.
        self.assertEqual(svc.plan(at='2026-11-02T08:30:00Z')['session']['window'], 'CATCH_UP')  # EST: 03:30
        self.assertEqual(svc.plan(at='2026-11-02T07:30:00Z')['session']['window'], 'INFERENCE_PAUSE')  # EST: 02:30
        for value in ('2026-10-14T00:09:59Z', '2026-10-14T07:30:00', 'soon'):
            with self.assertRaisesRegex(ValueError, 'INVALID_PLAN_CLOCK'):
                svc.plan(at=value)
        for bound in (dict(max_requests='-1'), dict(max_tokens='x'), dict(request_allowance='0'), dict(max_backlog='1001')):
            with self.assertRaisesRegex(ValueError, 'INVALID_PLAN_BOUND'):
                svc.plan(**bound)

    def test_status_reports_collection_separately_from_the_inference_pause(self):
        self.collect('2026-10-14T00:10:00+00:00')
        status = self.service(at='2026-10-14T01:00:00+00:00').status()
        self.assertEqual((status['session']['window'], status['session']['allowed']), ('INFERENCE_PAUSE', False))
        self.assertTrue(status['collection_independent_of_inference_pause'])
        self.assertEqual(set(status['collection']), {'raw_collection', 'market_persistence', 'market_supply', 'collection_supervision'})
        self.assertEqual(status['collection']['raw_collection']['state'], 'DISABLED')
        self.assertEqual((status['knowledge']['state'], status['knowledge']['records']), ('AVAILABLE', 1))
        self.assertEqual((status['model']['model'], status['model']['availability']), ('claude-haiku-4-5-20251001', 'NOT_PROBED'))
        self.assertEqual([row['window'] for row in status['schedule']],
                         ['INFERENCE_PAUSE', 'CATCH_UP', 'PREMARKET', 'REGULAR', 'AFTER_HOURS'])
        self.assertEqual(status['schedule_applies_to'], 'TRADING_DAYS')

    def test_store_block_and_scan_bound_do_not_leak_or_fail(self):
        self.collect('2026-10-14T00:10:00+00:00')
        self.collect('2026-10-14T03:00:00+00:00', provider_native_id='wire-2', url='https://example.test/wire-2')
        svc = self.service(at='2026-10-14T04:00:00+00:00')
        early = svc.knowledge(as_of='2026-10-14T01:00:00Z')['store']
        # A read at 01:00 does not reveal that, or when, something was stored at 03:00.
        self.assertEqual((early['records'], early['latest_ingested_time']), (1, '2026-10-14T00:10:00Z'))
        self.assertEqual(svc.knowledge()['store']['records'], 2)
        self.assertEqual(svc.knowledge(as_of='2026-10-13T23:00:00Z')['store']['state'], 'EMPTY')
        locked = SimpleNamespace(fetchone=lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError('database is locked')))
        self.assertEqual(self.service(connection=locked).knowledge_store()['reason'], 'NEWS_COLLECTION_STORE_UNREADABLE')
        with patch('market_platform_foundation.news.knowledge.StoredNewsRepository.retrieve',
                   side_effect=ValueError('NEWS_KNOWLEDGE_SCAN_BOUND')):
            bound = svc.knowledge()
            self.assertEqual((bound['store']['state'], bound['store']['reason'], bound['records']),
                             ('UNAVAILABLE', 'NEWS_KNOWLEDGE_SCAN_BOUND', []))
            self.assertEqual(svc.plan()['store']['reason'], 'NEWS_KNOWLEDGE_SCAN_BOUND')
        with patch('market_platform_foundation.news.knowledge.StoredNewsRepository.retrieve',
                   side_effect=ValueError('NEWS_KNOWLEDGE_TIME_INVALID')), self.assertRaisesRegex(ValueError, 'TIME_INVALID'):
            svc.knowledge()
        for value in ('0001-01-01T00:00:00+05:00', '9999-12-31T23:59:59-05:00'):  # out of range once converted
            with self.assertRaisesRegex(ValueError, 'INVALID_EVIDENCE_CUTOFF'):
                svc.knowledge(as_of=value)
            with self.assertRaisesRegex(ValueError, 'INVALID_PLAN_CLOCK'):
                svc.plan(at=value)

    def test_assumed_access_and_unconsulted_gates_are_labelled_not_claimed(self):
        self.three_overnight_articles()
        svc = self.service(at='2026-10-14T07:30:00+00:00')
        assumed = svc.plan(request_allowance='4096', assume_available=True)
        self.assertEqual((assumed['model_route']['state'], assumed['model_route']['availability_verified']),
                         ('ASSUMED_FOR_PREVIEW', False))
        self.assertEqual((assumed['spending_basis'], assumed['resource_basis'], assumed['paid_inference_permitted']),
                         ('RECORDED_DAILY_REQUEST_AND_TOKEN_BUDGET_ONLY', 'NOT_EVALUATED', False))
        self.assertEqual(assumed['model']['availability'], 'NOT_PROBED')
        honest = svc.plan(request_allowance='4096')
        self.assertEqual((honest['model_route']['state'], honest['model_route']['availability_verified']), ('NOT_VERIFIED', False))

    def test_backlog_beyond_the_bound_is_reported_not_hidden(self):
        self.three_overnight_articles()
        svc = self.service(at='2026-10-14T07:30:00+00:00')
        bounded = svc.plan(max_backlog='2', request_allowance='4096', assume_available=True)
        self.assertEqual((bounded['candidates'], bounded['unscanned_count'], bounded['unscanned_reason'], bounded['candidates_truncated']),
                         (3, 1, 'BACKLOG_BOUND', False))
        self.assertEqual([row['headline'] for row in bounded['planned']], ['AAPL reports earnings', 'MSFT guidance'])  # oldest first
        none = svc.plan(max_backlog='0', request_allowance='4096', assume_available=True)
        self.assertEqual((none['planned_requests'], none['deferred'], none['unscanned_count']), (0, [], 3))

    def test_usage_of_an_earlier_day_does_not_block_a_later_planned_day(self):
        self.three_overnight_articles()
        self.budget.update(day='2026-10-13', requests=30, tokens=150_000)  # yesterday's budget, fully used
        svc = self.service(at='2026-10-13T19:00:00+00:00')  # 15:00 New York on the 13th
        self.now = epoch('2026-10-13T19:00:00+00:00')
        today = svc.plan(at='2026-10-13T19:30:00Z', request_allowance='4096', assume_available=True)
        self.assertEqual((today['budget_basis'], today['budget']['requests']), ('RECORDED_USAGE_OF_THE_PLANNED_DAY', 30))
        tomorrow = svc.plan(at='2026-10-14T07:30:00Z', request_allowance='4096', assume_available=True)
        self.assertEqual((tomorrow['budget_basis'], tomorrow['budget']['requests'], tomorrow['budget']['day'], tomorrow['budget']['max_requests']),
                         ('LIMITS_ONLY_USAGE_RESETS_BEFORE_THE_PLANNED_DAY', 0, '2026-10-14', 30))
        self.assertNotIn('INFERENCE_BUDGET_BLOCKED', reasons(tomorrow))

    def test_every_payload_passes_the_response_secret_audit_over_http(self):
        """The server refuses a response whose keys look like credentials; reason codes must never be keys."""
        from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload
        import market_platform_foundation.ui_api.evidence_review as module

        self.three_overnight_articles()
        svc = self.service(at='2026-10-14T07:30:00+00:00')
        store = SimpleNamespace()
        prior = module._SERVICE, module._STORE
        module._SERVICE, module._STORE = svc, store
        self.addCleanup(lambda: (setattr(module, '_SERVICE', prior[0]), setattr(module, '_STORE', prior[1])))

        class Handler(UiApiHandler):
            def _authorize_request(self, *args, **kwargs): return True
            def log_message(self, *args): pass
        Handler.store = store
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def get(path):
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/evaluation/evidence/{path}', timeout=10) as response:
                    return json.load(response)
            estimate = get('plan?assume_available=1')
            self.assertEqual(reasons(estimate), {'TOKEN_ESTIMATE_NOT_VERIFIED': 3})
            one = get('plan?assume_available=1&request_allowance=4096')['planned'][0]['worst_case_tokens']
            bound = get(f'plan?assume_available=1&request_allowance=4096&max_tokens={one}')
            self.assertEqual((bound['planned_requests'], reasons(bound)), (1, {'TOKEN_BOUND': 2}))
            for path in ('status', 'knowledge', 'knowledge?revisions=1&symbol=AAPL', 'plan', 'plan?request_allowance=4096',
                         'plan?max_backlog=1', 'replay'):
                assert_no_secrets_in_payload(get(path))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_budget_read_creates_no_file_when_nothing_was_spent(self):
        cache = Path(self.temp.name) / 'cache'
        svc = EvidenceReviewService(SimpleNamespace(), connection=self.connection, settings=self.settings,
                                    clock=lambda: epoch('2026-10-14T07:30:00+00:00'))
        with patch('market_platform_foundation.local_state.external_cache.imp_cache_dir', return_value=cache), \
                patch('market_platform_foundation.news.config.configured_value', return_value=None):
            budget = svc.budget_status()
        self.assertEqual((budget['source'], budget['requests'], budget['max_requests'], budget['max_tokens']),
                         ('NO_USAGE_RECORDED', 0, 30, 200_000))
        self.assertFalse(cache.exists())

    # --- as-of replay -----------------------------------------------------------------
    def test_replay_gives_one_as_of_snapshot_to_three_policies_and_ranks_nothing(self):
        svc = self.service(at='2026-10-14T04:00:00+00:00')
        full = svc.replay()
        self.assertEqual((full['replay_date'], full['evidence_class'], full['rebuild_identical']),
                         ('2026-09-09', 'SOFTWARE_FIXTURE_ONLY', True))
        self.assertEqual(full['available'][0]['replay_date'], '2026-09-09')
        self.assertTrue(full['decisions'])
        for sample in full['decisions']:
            self.assertEqual(len(sample['policies']), 3)
            self.assertEqual(len({policy['policy_id'] for policy in sample['policies']}), 3)
            self.assertLessEqual(epoch(sample['as_of'].replace('Z', '+00:00')), epoch(full['as_of'].replace('Z', '+00:00')))
        self.assertEqual((full['comparison']['performance_ranking'], full['comparison']['ranking_status']),
                         (None, 'NOT_A_PERFORMANCE_RANKING'))
        self.assertIn('NO_REALIZED_PNL_OR_STRATEGY_EDGE_CLAIM', full['limitations'])
        early = svc.replay(replay_date='2026-09-09', as_of='2026-09-09T14:00:00Z')
        self.assertLess(early['coverage']['eligible_samples'], full['coverage']['eligible_samples'])
        self.assertNotEqual(early['snapshot_hash'], full['snapshot_hash'])
        self.assertEqual(early['snapshot_hash'], svc.replay(replay_date='2026-09-09', as_of='2026-09-09T14:00:00Z')['snapshot_hash'])
        # The curated pack's stored AI output has no article lineage, so none is admitted and the view says so.
        self.assertEqual((full['ai_output_admitted_samples'], full['coverage']['withheld_inference'] > 0), (0, True))
        self.assertIn('FIXTURE_AI_OUTPUT_NOT_ADMITTED_WITHOUT_ARTICLE_LINEAGE', full['limitations'])
        with self.assertRaisesRegex(ValueError, 'REPLAY_DAY_OR_TIMEZONE_MISMATCH'):
            svc.replay(replay_date='2026-09-09', as_of='2026-09-10T14:00:00Z')
        for options in (dict(replay_date='2026-09-10'), dict(replay_date='2026-09-10', as_of='2026-09-10T14:00:00Z')):
            with self.assertRaisesRegex(ValueError, 'REPLAY_DAY_NOT_IN_FIXTURE'):
                svc.replay(**options)
        with self.assertRaisesRegex(ValueError, 'INVALID_EVIDENCE_CUTOFF'):  # a clock the server has not reached
            self.service(at='2026-09-09T13:00:00+00:00').replay(replay_date='2026-09-09', as_of='2026-09-09T14:00:00Z')
        with self.assertRaisesRegex(ValueError, 'REPLAY_CLOCK_INVALID'):
            svc.replay(replay_date='2026-09-09', as_of='2026-09-09T14:00:00')


class DecisionJournalReviewTests(_Lifecycle):
    def review(self):
        evaluation = ProspectiveEvaluationService(self.store, actions=self.repo, next_sessions=ReevaluationRepository(),
                                                  repository=EvaluationRepository(), clock=self.clock)
        return EvidenceReviewService(self.store, actions=self.repo, evaluation=evaluation, settings=Settings(),
                                     budget=lambda: {}, clock=self.clock)

    def test_no_action_is_journaled_without_an_invented_trade_or_side_effect(self):
        decision = self.decide(self.new_run('AAPL'), 'NO_ACTION', 'AAPL')
        before, calls = json.dumps(self.store.paper_ledger.events), self.model.calls
        journal = self.review().journal()
        item = self.only_item(journal)
        self.assertEqual((item['decision_id'], item['instrument_id'], item['mode']), (decision['decision_id'], 'AAPL', 'PAPER'))
        self.assertEqual((item['action']['action_state'], item['action']['operator_action']), ('NO_ACTION', None))
        self.assertEqual(item['action']['model_proposal']['proposal_state'], 'NO_ACTION')
        self.assertEqual((item['evidence_snapshot_id'], item['candidate_run_id']),
                         (decision['evidence_snapshot_id'], decision['evidence_snapshot']['candidate_run_id']))
        self.assertGreater(item['evidence_count'], 0)
        # Fields this view does not read are named as such, never shown as empty findings.
        self.assertTrue({'realized_pnl', 'outcome_status', 'reviews'}.isdisjoint(item))
        self.assertEqual((journal['operator_action_source'], journal['research_outcomes'], journal['realized_pnl_source']),
                         ('DECISION_TRACE_NOT_READ_BY_THIS_VIEW', 'NOT_READ_BY_THIS_VIEW',
                          'PAPER_LEDGER_EPISODE_IN_LATER_EVIDENCE_NOT_COMPUTED_HERE'))
        self.assertEqual((item['later_evidence']['status'], item['later_evidence']['execution_outcome']), ('AVAILABLE', None))
        self.assertEqual((journal['source'], journal['unjournaled']), ('ACTION_DECISION_RECEIPTS', []))
        self.assertEqual(json.dumps(self.store.paper_ledger.events), before)
        self.assertEqual(self.model.calls, calls)

    def test_ui_fixture_journal_has_the_shape_the_service_returns(self):
        self.enter()
        self.tick(5)
        journal = json.loads(json.dumps(self.review().journal()))
        fixture = json.loads(UI_FIXTURE.read_text(encoding='utf-8'))['journal']
        self.assertEqual(set(fixture), set(journal))
        self.assertEqual(set(fixture['items'][0]), set(self.only_item(journal)))
        self.assertEqual(set(fixture['items'][0]['action']), set(journal['items'][0]['action']))
        self.assertEqual(set(fixture['items'][0]['later_evidence']), set(journal['items'][0]['later_evidence']))

    def only_item(self, journal):
        self.assertEqual(len(journal['items']), 1, journal)
        return journal['items'][0]

    def test_decision_stays_frozen_while_the_later_paper_outcome_appears(self):
        _, decision = self.enter()
        self.tick(10)
        open_cutoff = iso(self.t)
        self.tick(10)
        self.governed(self.exit(), price='152.00')
        self.tick(2)
        svc = self.review()
        early = {row['decision_id']: row for row in svc.journal(as_of=open_cutoff)['items']}
        late = {row['decision_id']: row for row in svc.journal()['items']}
        self.assertEqual(set(early), {decision['decision_id']})  # the exit decision did not exist yet
        self.assertEqual(len(late), 2)
        entry_early, entry_late = early[decision['decision_id']], late[decision['decision_id']]
        self.assertEqual(entry_early['decision_snapshot_hash'], entry_late['decision_snapshot_hash'])
        self.assertEqual(entry_early['action'], entry_late['action'])
        self.assertEqual(entry_late['action']['action_state'], 'ENTER')
        self.assertNotEqual(entry_early['later_evidence']['execution_outcome'], entry_late['later_evidence']['execution_outcome'])
        self.assertIsNotNone(entry_late['later_evidence']['execution_outcome'])
        self.assertEqual(entry_late['later_evidence']['evaluation_id'], 'DE-' + decision['decision_id'])
        self.assertEqual((entry_early['later_evidence']['execution_outcome']['state'], entry_late['later_evidence']['execution_outcome']['state']),
                         ('OPEN', 'CLOSED'))
        # The episode is reported on the decision that opened it; the exit decision carries none of its own.
        closing = next(row for row in late.values() if row['action']['action_state'] == 'EXIT')
        self.assertIsNone(closing['later_evidence']['execution_outcome'])
        detail = svc.journal(decision_id=decision['decision_id'])
        self.assertEqual(detail['entry']['decision_snapshot_hash'], entry_late['decision_snapshot_hash'])
        self.assertEqual(detail['entry']['source_decision']['decision_id'], decision['decision_id'])
        self.assertEqual(detail['entry']['evidence_snapshot'], decision['evidence_snapshot'])
        with self.assertRaisesRegex(ValueError, 'JOURNAL_DECISION_NOT_FOUND'):
            svc.journal(decision_id='missing')

    def test_other_days_future_cutoffs_and_refused_receipts_are_explicit(self):
        decision = self.decide(self.new_run('AAPL'), 'NO_ACTION', 'AAPL')
        svc = self.review()
        self.assertEqual(svc.journal(day='2020-01-02')['items'], [])
        with self.assertRaisesRegex(ValueError, 'INVALID_EVIDENCE_CUTOFF'):
            svc.journal(as_of=iso(self.t + 60))
        with self.assertRaisesRegex(ValueError, 'INVALID_JOURNAL_DAY'):
            svc.journal(day='today')
        # A receipt the journal contract refuses (its snapshot cutoff no longer matches) is listed, not repaired.
        broken = json.loads(json.dumps(decision))
        broken['decision_id'] = 'broken'
        broken['evidence_snapshot']['cutoff'] = iso(self.t - 5)
        self.repo._memory['decision', 'broken'] = json.dumps(broken)
        legacy = json.loads(json.dumps(decision))  # a legacy shape the contract cannot even read
        legacy['decision_id'] = 'legacy'
        legacy['evidence_snapshot']['context'] = None
        self.repo._memory['decision', 'legacy'] = json.dumps(legacy)
        journal = svc.journal()
        self.assertEqual([row['decision_id'] for row in journal['items']], [decision['decision_id']])
        self.assertEqual(sorted((row['decision_id'], row['reason']) for row in journal['unjournaled']),
                         [('broken', 'JOURNAL_SNAPSHOT_IDENTITY_MISMATCH'), ('legacy', 'AttributeError')])

    def test_http_views_are_reads_and_unknown_views_are_refused(self):
        self.decide(self.new_run('AAPL'), 'NO_ACTION', 'AAPL')
        import market_platform_foundation.ui_api.evidence_review as module
        prior = module._SERVICE, module._STORE
        module._SERVICE, module._STORE = self.review(), self.store
        self.addCleanup(lambda: (setattr(module, '_SERVICE', prior[0]), setattr(module, '_STORE', prior[1])))
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        connection = LocalStateConnection(Path(temp.name) / 'imp-state.sqlite3')
        self.addCleanup(connection.close)
        module._SERVICE._connection = connection
        # One stored article and a fully populated budget, so the response secret audit sees every field.
        stored_at = self.t - 60
        article = normalize_raw_item(dict(provider_native_id='wire-1', headline='AAPL note', summary='Synthetic', tickers=['AAPL'],
                                          url='https://example.test/wire-1', published_time=iso(stored_at - 60)),
                                     provider_id='finviz', source_id='wire', retrieved_time=iso(stored_at))
        NewsCollector(connection, [CollectionJob('finviz', '', 'US_EQUITIES', 120)],
                      lambda job: ([(article, dict(evidence_class='SOFTWARE_FIXTURE_ONLY'))], {'state': 'CURRENT'}),
                      clock=lambda: stored_at).step()
        module._SERVICE._budget = lambda: dict(day=iso(self.t)[:10], requests=1, tokens=500, max_requests=30, max_tokens=200_000,
                                               usage_overrun=False, held_requests=0, held_tokens=0)

        class Handler(UiApiHandler):
            def _authorize_request(self, *args, **kwargs): return True
            def log_message(self, *args): pass
        Handler.store = self.store
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def get(path):
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}{path}', timeout=10) as response:
                    return json.load(response)
            before = json.dumps(self.store.paper_ledger.events)
            self.assertEqual(get('/evaluation/evidence/status')['schema_version'], 'evidence-review-status/1')
            knowledge = get('/evaluation/evidence/knowledge?limit=5&symbol=AAPL')
            self.assertEqual((knowledge['store']['state'], knowledge['count']), ('AVAILABLE', 1))
            plan = get('/evaluation/evidence/plan?request_allowance=4096&assume_available=1')
            self.assertEqual((plan['candidates'], plan['inference_calls'], plan['budget']['tokens']), (1, 0, 500))
            self.assertEqual(len(plan['planned']) + len(plan['deferred']), 1)
            self.assertEqual(len(get('/evaluation/evidence/journal')['items']), 1)
            replay = get('/evaluation/evidence/replay?date=2026-09-09&as_of=2026-09-09T14:00:00Z')
            self.assertEqual((replay['as_of'], replay['rebuild_identical']), ('2026-09-09T14:00:00Z', True))
            for path in ('/evaluation/evidence/unknown', '/evaluation/evidence/knowledge?as_of=tomorrow',
                         '/evaluation/evidence/replay?date=2026-09-10'):
                with self.assertRaises(urllib.error.HTTPError) as refused:
                    get(path)
                self.assertEqual(refused.exception.code, 400)
                self.assertEqual(json.load(refused.exception)['reason_code'], 'EVIDENCE_REVIEW_UNAVAILABLE')
            self.assertEqual(json.dumps(self.store.paper_ledger.events), before)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_route_policy_is_an_audit_read(self):
        policy = policy_for_route('GET', '/evaluation/evidence/journal')
        self.assertEqual((policy.capability, policy.account_scope.name), ('audit.read', 'PAPER_LEDGER'))
        self.assertEqual(policy_for_route('GET', '/evaluation/evidence/plan').capability, 'audit.read')


if __name__ == '__main__':
    unittest.main()
