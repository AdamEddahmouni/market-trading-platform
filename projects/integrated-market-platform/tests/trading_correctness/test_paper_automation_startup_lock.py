"""AUD-046: a locked store at boot must not leave an armed, running controller without a worker for good.

At 22:10Z on 2026-10-29 the restarted API's first controller read raised ``database is locked``. That read sat
outside ``resume_on_startup``'s transient retry, so the boot reported ``{'resumed': False, 'reason':
'OperationalError'}`` and no retry ran: the controller stayed armed and RUNNING with no worker, and the next-open
close of five carried positions became unreachable (audit repro R5).
"""
from __future__ import annotations

import sqlite3

from tests.trading_correctness.test_paper_automation import AutoBase


class _LockedReads:
    """Wraps the repository so its next ``count`` controller reads fail as a held write lock does."""

    def __init__(self, repository, count):
        self._repository, self.remaining, self.raised = repository, count, 0

    def __getattr__(self, name):
        return getattr(self._repository, name)

    def get_controller(self, *args, **kwargs):
        if self.remaining > 0:
            self.remaining -= 1
            self.raised += 1
            raise sqlite3.OperationalError('database is locked')
        return self._repository.get_controller(*args, **kwargs)


class StartupLockedReadTests(AutoBase):
    def restart_with_locked_reads(self, count):
        self.enter()
        self.clock.value += 1500  # the previous process is gone and its lease has expired
        b = self.restart()
        locked = _LockedReads(b.service.repository, count)
        b.service.repository = locked
        waited = []

        def sleep(seconds):
            waited.append(seconds)
            self.clock.value += seconds
        b.service.sleep = sleep
        return b, locked, waited

    def test_a_locked_first_read_is_retried_and_the_controller_resumes(self):
        b, locked, waited = self.restart_with_locked_reads(1)
        self.assertEqual(b.service.resume_on_startup(threaded=False), dict(resumed=True, reason=None))
        self.assertEqual(locked.raised, 1)
        self.assertEqual(len(waited), 1)
        retry = b.events('STARTUP_RESUME_RETRYING')[0]
        self.assertEqual((retry['reason'], retry['stage']), ('OperationalError', 'READ'))
        self.assertEqual((b.service.status()['status'], b.service.status()['liveness']['owner']), ('RUNNING', 'THIS_PROCESS'))

    def test_a_threaded_boot_returns_retrying_and_starts_a_retry_thread(self):
        b, locked, _ = self.restart_with_locked_reads(1)
        started = []
        b.service._resume_after_lease = lambda *args: started.append(args)
        # The boot line is no longer the permanent ``{'resumed': False, 'reason': 'OperationalError'}``.
        self.assertEqual(b.service.resume_on_startup(threaded=True), dict(resumed=False, reason='RETRYING'))
        for _ in range(50):
            if started:
                break
            import time
            time.sleep(0.01)
        self.assertEqual(len(started), 1)
        self.assertTrue(started[0][1])  # threaded retry

    def test_reads_locked_during_the_retries_keep_retrying_within_the_window(self):
        b, locked, waited = self.restart_with_locked_reads(5)
        self.assertEqual(b.service.resume_on_startup(threaded=False), dict(resumed=True, reason=None))
        self.assertEqual(locked.raised, 5)
        self.assertEqual(len(waited), 5)

    def test_a_store_locked_past_the_window_gives_up_visibly_without_starting(self):
        b, locked, waited = self.restart_with_locked_reads(10_000)
        result = b.service.resume_on_startup(threaded=False)
        self.assertEqual(result, dict(resumed=False, reason='OperationalError'))
        self.assertLessEqual(sum(waited), 900 + 30)  # STARTUP_RESUME_RETRY_LIMIT_SECONDS bounds the retries
        locked.remaining = 0  # the lock clears; the controller was never started
        self.assertNotEqual(b.service.status()['liveness']['owner'], 'THIS_PROCESS')

    def test_a_controller_disarmed_while_reads_were_locked_is_not_resumed(self):
        b, locked, _ = self.restart_with_locked_reads(0)
        b.service.disarm()  # the operator disarms before the locked boot read is retried
        locked.remaining = 1
        self.assertEqual(b.service.resume_on_startup(threaded=False), dict(resumed=False, reason='NOT_ARMED'))
        self.assertNotEqual(b.service.status()['status'], 'RUNNING')

    def test_a_non_transient_read_error_is_not_retried(self):
        b, locked, waited = self.restart_with_locked_reads(0)

        def broken(*args, **kwargs):
            raise sqlite3.OperationalError('no such table: paper_automation_controllers')
        locked.get_controller = broken
        with self.assertRaises(sqlite3.OperationalError):
            b.service.resume_on_startup(threaded=False)
        self.assertEqual(waited, [])


class BootWrapperTests(__import__('unittest').TestCase):
    """``run_ui_api.resume_paper_automation``: the boot path that turned a locked read into a permanent no-resume."""

    def run_wrapper(self, failures, error='database is locked'):
        from unittest import mock
        from tools.ui1 import run_ui_api

        calls, slept = [], []

        class Service:
            def resume_on_startup(self):
                return dict(resumed=True, reason=None)

        def service(store):
            calls.append(store)
            if len(calls) <= failures:
                raise sqlite3.OperationalError(error)
            return Service()

        with mock.patch('market_platform_foundation.ui_api.paper_automation.paper_automation_service', service), \
                mock.patch('builtins.print'):
            result = run_ui_api.resume_paper_automation('store', sleep=slept.append, threaded=False)
        return result, calls, slept

    def test_a_locked_service_read_at_boot_is_retried_until_it_resumes(self):
        result, calls, slept = self.run_wrapper(2)
        self.assertEqual(result, dict(resumed=True, reason=None))
        self.assertEqual((len(calls), len(slept)), (3, 2))

    def test_a_non_transient_failure_is_reported_once_as_before(self):
        result, calls, slept = self.run_wrapper(1, error='no such table: x')
        self.assertEqual(result, dict(resumed=False, reason='OperationalError'))
        self.assertEqual((len(calls), slept), (1, []))
