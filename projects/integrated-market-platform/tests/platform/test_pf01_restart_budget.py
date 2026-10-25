"""PF-01 supervisor restart budget: rolling, recoverable and bounded. Disposable SQLite, synthetic children."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.news import supervision
from market_platform_foundation.news.supervision import (CHILD_EXIT_PERMANENT, COOLDOWN_LIMIT, HEALTHY_RESET_SECONDS,
    LATCH_EXPIRY_SECONDS, RESTART_LIMIT, RESTART_WINDOW_SECONDS, STORAGE_GRACE_SECONDS, SUPERVISION_JOB,
    UNHEALTHY_FAILURE_LIMIT, CollectionSupervisor, reset_restart_budget, supervision_status)


class Process:
    def __init__(self): self.exit = None; self.stopped = False
    def poll(self): return self.exit
    def stop(self): self.stopped = True; self.exit = 0


class SupervisorCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'imp-state.sqlite3'
        self.db = LocalStateConnection(self.path); self.addCleanup(self.db.close)
        self.now = 1_000_000.; self.children = []; self.spawn_error = None
        self.env = {'IMP_PF01_SUPERVISION_ENABLED':'1','IMP_NEWS_COLLECTION_ENABLED':'1',
                    'IMP_PERSIST_STATE':'1','IMP_STATE_DIR':str(self.path.parent)}

    def spawn(self):
        if self.spawn_error: raise self.spawn_error
        child = Process(); self.children.append(child); return child

    def supervisor(self):
        owner = CollectionSupervisor(self.db, spawn=self.spawn, env=self.env, clock=lambda: self.now)
        self.addCleanup(owner.stop); return owner

    def run_for(self, owner, seconds, step=30):
        for _ in range(int(seconds/step)): self.now += step; owner.tick()

    def crash(self, owner, code=1):
        self.children[-1].exit = code; owner.tick()

    def saved(self):
        row = self.db.execute('SELECT payload_json FROM news_collection_jobs WHERE job_id=?', (SUPERVISION_JOB,)).fetchone()
        return json.loads(row['payload_json'])

    def exhaust(self, owner):
        """Initial start plus every automatic restart of one window, each crashing at once."""
        owner.tick()
        for _ in range(RESTART_LIMIT):
            self.crash(owner); self.run_for(owner, owner.status()['next_start']-self.now)
        self.crash(owner)


class RestartBudgetTests(SupervisorCase):
    def test_single_transient_failure_restarts_after_one_lease_interval(self):
        owner = self.supervisor(); owner.tick(); self.crash(owner, 3)
        self.assertEqual((owner.status()['state'], owner.status()['reason']), ('BACKOFF', 'CHILD_PROCESS_EXIT'))
        self.assertEqual(owner.status()['next_start']-self.now, 120)
        self.run_for(owner, 90); self.assertEqual(len(self.children), 1)
        self.run_for(owner, 30); self.assertEqual(len(self.children), 2)
        self.assertEqual(owner.status()['state'], 'RUNNING')
        self.assertEqual(owner.status()['restarts_in_window'], 1)
        self.assertEqual(self.saved()['events'][-2]['exit_code'], 3)

    def test_multiple_transient_failures_back_off_exponentially_inside_the_cap(self):
        owner = self.supervisor(); owner.tick(); waits = []
        for _ in range(RESTART_LIMIT):
            self.crash(owner); waits.append(owner.status()['next_start']-self.now)
            self.run_for(owner, waits[-1])
        self.assertEqual(waits, [120, 240, 480])
        self.assertLessEqual(max(waits), supervision.BACKOFF_CAP_SECONDS)
        self.assertEqual(len(self.children), 1+RESTART_LIMIT)

    def test_exhausted_budget_cools_down_without_spawning_then_recovers(self):
        owner = self.supervisor(); self.exhaust(owner)
        status = owner.status()
        self.assertEqual((status['state'], status['reason']), ('COOLDOWN', 'RESTART_LIMIT_EXCEEDED'))
        self.assertEqual(status['restarts_in_window'], RESTART_LIMIT)
        # No restart while the oldest restart is still inside the rolling window.
        oldest = status['restarts'][0]
        self.assertEqual(status['next_start'], oldest+RESTART_WINDOW_SECONDS)
        spawned = len(self.children)
        self.run_for(owner, oldest+RESTART_WINDOW_SECONDS-self.now-30)
        self.assertEqual(len(self.children), spawned)
        self.assertEqual(owner.status()['state'], 'COOLDOWN')
        # The supervisor stayed the owner throughout: it did not exit or lose its lease.
        self.assertEqual(self.db.execute('SELECT lease_owner FROM news_collection_jobs WHERE job_id=?',
                                         (SUPERVISION_JOB,)).fetchone()[0], owner.owner)
        self.run_for(owner, 30)
        self.assertEqual(len(self.children), spawned+1)
        self.assertEqual(owner.status()['state'], 'RUNNING')

    def test_healthy_period_restores_the_full_allowance(self):
        owner = self.supervisor(); self.exhaust(owner)
        self.run_for(owner, owner.status()['next_start']-self.now)
        self.assertEqual(owner.status()['cooldowns'], 1)
        self.run_for(owner, HEALTHY_RESET_SECONDS-30)
        self.assertEqual(owner.status()['cooldowns'], 1)
        self.run_for(owner, 30)
        status = owner.status()
        self.assertEqual((status['restarts'], status['cooldowns'], status['restarts_in_window']), ([], 0, 0))
        self.assertIn('RESTART_BUDGET_RESET_AFTER_HEALTHY_PERIOD', [e['reason'] for e in self.saved()['events']])
        # Restart after recovery: a later failure starts again from the shortest backoff.
        self.crash(owner)
        self.assertEqual(owner.status()['next_start']-self.now, 120)

    def test_repeated_persistent_failure_latches_and_never_spins(self):
        owner = self.supervisor(); self.exhaust(owner); started = self.now
        for _ in range(COOLDOWN_LIMIT-1):
            self.run_for(owner, owner.status()['next_start']-self.now); self.crash(owner)
        status = owner.status()
        self.assertEqual((status['state'], status['reason'], status['latched']),
                         ('BLOCKED', 'PERSISTENT_CHILD_FAILURE', 'PERSISTENT_CHILD_FAILURE'))
        total = len(self.children)
        self.assertEqual(total, 1+RESTART_LIMIT+COOLDOWN_LIMIT-1)
        # Latched well past a rolling window (the latch itself expires only after LATCH_EXPIRY_SECONDS).
        self.run_for(owner, LATCH_EXPIRY_SECONDS-900)
        self.assertEqual(len(self.children), total)
        # Never more than the limit inside any rolling window, even while failing continuously.
        starts = [e['at'] for e in self.saved()['events'] if e['reason'] == 'CHILD_START_ATTEMPT']
        for at in starts:
            self.assertLessEqual(sum(at <= other < at+RESTART_WINDOW_SECONDS for other in starts[1:]), RESTART_LIMIT)
        self.assertGreater(self.now-started, RESTART_WINDOW_SECONDS)
        # A new supervisor process does not clear the latch.
        owner.stop(); replacement = self.supervisor(); self.run_for(replacement, 600)
        self.assertEqual(replacement.status()['reason'], 'PERSISTENT_CHILD_FAILURE')
        self.assertEqual(len(self.children), total)

    def test_operator_reset_is_refused_while_owned_and_clears_the_latch_after_stop(self):
        owner = self.supervisor(); self.exhaust(owner)
        for _ in range(COOLDOWN_LIMIT-1):
            self.run_for(owner, owner.status()['next_start']-self.now); self.crash(owner)
        with self.assertRaisesRegex(ValueError, 'SUPERVISOR_OWNER_ACTIVE'):
            reset_restart_budget(self.db, clock=lambda: self.now)
        owner.stop(); total = len(self.children)
        evidence = reset_restart_budget(self.db, clock=lambda: self.now)
        self.assertEqual((evidence['latched'], evidence['restarts'], evidence['cooldowns']), (None, [], 0))
        self.assertEqual(evidence['events'][-1]['cleared'], 'PERSISTENT_CHILD_FAILURE')
        self.assertEqual(len(self.children), total)  # the reset starts nothing
        replacement = self.supervisor(); replacement.tick()
        self.assertEqual(replacement.status()['state'], 'RUNNING')
        self.assertEqual(replacement.status()['crashes'], evidence['crashes'])  # history is kept

    def latch(self, owner):
        self.exhaust(owner)
        for _ in range(COOLDOWN_LIMIT-1):
            self.run_for(owner, owner.status()['next_start']-self.now); self.crash(owner)
        self.assertEqual(owner.status()['latched'], 'PERSISTENT_CHILD_FAILURE')

    def test_persistent_failure_latch_expires_after_its_time_with_a_fresh_allowance(self):
        # Owner decision 3 (2026-10-23): unattended restart. The collector tries again a few times a day, never spins.
        owner = self.supervisor(); self.latch(owner)
        latched_at = owner.status()['latched_at']; self.assertEqual(latched_at, self.now)
        total = len(self.children)
        self.run_for(owner, LATCH_EXPIRY_SECONDS-30)
        self.assertEqual((owner.status()['latched'], len(self.children)), ('PERSISTENT_CHILD_FAILURE', total))
        self.run_for(owner, 30)
        status = owner.status()
        self.assertEqual((status['state'], status['latched'], status['restarts'], status['cooldowns'], status['unhealthy_failures']),
                         ('RUNNING', None, [], 0, 0))
        self.assertEqual(len(self.children), total+1)
        expired = [e for e in self.saved()['events'] if e['reason'] == 'RESTART_LATCH_EXPIRED']
        self.assertEqual((len(expired), expired[0]['cleared'], expired[0]['latched_at']), (1, 'PERSISTENT_CHILD_FAILURE', latched_at))

    def test_an_expired_latch_lets_a_fresh_supervisor_start(self):
        owner = self.supervisor(); self.latch(owner); owner.stop(); total = len(self.children)
        self.now += LATCH_EXPIRY_SECONDS
        replacement = self.supervisor(); replacement.tick()
        self.assertEqual((replacement.status()['state'], len(self.children)), ('RUNNING', total+1))

    def test_a_rejected_configuration_stays_latched_until_the_operator_resets_it(self):
        owner = self.supervisor(); owner.tick(); self.crash(owner, CHILD_EXIT_PERMANENT)
        self.assertEqual(owner.status()['latched'], 'CHILD_CONFIGURATION_REJECTED')
        self.run_for(owner, 2*LATCH_EXPIRY_SECONDS, step=300)
        self.assertEqual((owner.status()['latched'], len(self.children)), ('CHILD_CONFIGURATION_REJECTED', 1))
        self.assertNotIn('RESTART_LATCH_EXPIRED', [e['reason'] for e in self.saved()['events']])

    def test_a_latch_recorded_before_expiry_existed_starts_its_clock_when_first_seen(self):
        owner = self.supervisor(); self.latch(owner); owner.stop(); total = len(self.children)
        evidence = self.saved(); evidence.pop('latched_at')
        with self.db.transaction():
            self.db.execute('UPDATE news_collection_jobs SET payload_json=? WHERE job_id=?', (json.dumps(evidence), SUPERVISION_JOB))
        self.now += 3*LATCH_EXPIRY_SECONDS
        replacement = self.supervisor(); replacement.tick()
        status = replacement.status()
        self.assertEqual((status['latched'], status['latched_at'], len(self.children)), ('PERSISTENT_CHILD_FAILURE', self.now, total))
        self.run_for(replacement, LATCH_EXPIRY_SECONDS)
        self.assertEqual(len(self.children), total+1)

    def test_status_reports_when_an_expiring_latch_clears(self):
        owner = self.supervisor(); self.latch(owner)
        status = supervision_status(self.env, clock=lambda: self.now)
        self.assertEqual((status['latched'], status['latched_at'], status['latch_expiry_seconds']),
                         ('PERSISTENT_CHILD_FAILURE', self.now, LATCH_EXPIRY_SECONDS))

    def test_supervisor_stopped_during_backoff_keeps_the_remaining_backoff(self):
        owner = self.supervisor(); owner.tick(); self.crash(owner); self.run_for(owner, 120)
        self.crash(owner); due = owner.status()['next_start']
        self.assertEqual(due-self.now, 240)
        owner.stop(); replacement = self.supervisor()
        self.run_for(replacement, 210); self.assertEqual(len(self.children), 2)
        self.run_for(replacement, 30); self.assertEqual(len(self.children), 3)
        self.assertEqual(replacement.status()['restarts_in_window'], 2)

    def test_supervisor_killed_during_backoff_never_shortens_it(self):
        owner = self.supervisor(); owner.tick(); self.crash(owner); self.run_for(owner, 120)
        self.crash(owner); self.run_for(owner, 240); self.crash(owner)
        due = owner.status()['next_start']; self.assertEqual(due-self.now, 480)
        owner._stopped = True  # abrupt death: no release, the lease simply stops being renewed
        self.now += 60
        with self.assertRaisesRegex(ValueError, 'SUPERVISOR_OWNER_ACTIVE'): self.supervisor()
        self.now += 60
        replacement = self.supervisor()
        self.assertEqual(replacement.status()['next_start'], due)
        self.run_for(replacement, due-self.now-30); self.assertEqual(len(self.children), 3)
        self.run_for(replacement, 30); self.assertEqual(len(self.children), 4)

    def test_child_start_failure_is_charged_to_the_same_budget(self):
        self.spawn_error = OSError('private path')
        owner = self.supervisor(); owner.tick()
        self.assertEqual((owner.status()['state'], owner.status()['reason']), ('BACKOFF', 'CHILD_START_FAILED'))
        for _ in range(RESTART_LIMIT): self.run_for(owner, owner.status()['next_start']-self.now)
        self.assertEqual(owner.status()['state'], 'COOLDOWN')
        self.assertNotIn('private', json.dumps(owner.status()))
        self.assertEqual(self.children, [])

    def test_child_that_rejects_its_configuration_latches_without_spending_restarts(self):
        owner = self.supervisor(); owner.tick(); self.crash(owner, CHILD_EXIT_PERMANENT)
        status = owner.status()
        self.assertEqual((status['state'], status['reason'], status['restarts']), ('BLOCKED', 'CHILD_CONFIGURATION_REJECTED', []))
        self.run_for(owner, RESTART_WINDOW_SECONDS); self.assertEqual(len(self.children), 1)
        self.assertEqual(supervision.child_exit_code('APPROVED_SCHEMA_MIGRATION_REQUIRED'), CHILD_EXIT_PERMANENT)
        self.assertEqual(supervision.child_exit_code('COLLECTION_WORKER_UNHEALTHY'), 1)

    def test_evidence_row_from_the_lifetime_budget_is_not_permanently_blocked(self):
        self.db.execute('INSERT INTO news_collection_jobs VALUES (?,?,?,?,?)', (SUPERVISION_JOB, json.dumps(
            {'state':'BLOCKED','reason':'RESTART_LIMIT_EXCEEDED','crashes':3,'next_start':0,'events':[]}), 0, None, 0))
        owner = self.supervisor(); owner.tick()
        self.assertEqual(owner.status()['state'], 'RUNNING')
        self.assertEqual(owner.status()['crashes'], 3)

    def test_clock_set_backwards_cannot_pin_restarts_inside_the_window(self):
        owner = self.supervisor(); owner.tick(); self.crash(owner); self.run_for(owner, 120)
        self.now -= 10*RESTART_WINDOW_SECONDS  # the recorded restart is now "in the future"
        self.crash(owner)
        self.assertLessEqual(max(owner.status()['restarts']), self.now)
        self.assertEqual(owner.status()['next_start']-self.now, 240)


class SupervisorStorageOutageTests(SupervisorCase):
    def test_storage_outage_stops_child_waits_and_recovers_with_a_charged_restart(self):
        owner = self.supervisor(); owner.tick()
        with patch.object(Path, 'stat', side_effect=FileNotFoundError):
            owner.tick()
            self.assertTrue(self.children[0].stopped)
            self.assertEqual((owner.status()['state'], owner.status()['reason']), ('STORAGE_WAIT', 'STORAGE_UNAVAILABLE'))
            self.run_for(owner, 300)  # longer than the lease: nothing can be renewed or restarted
            self.assertEqual(len(self.children), 1)
            self.assertEqual(owner.status()['state'], 'STORAGE_WAIT')
        owner.tick()
        status = owner.status()
        self.assertEqual((status['state'], status['reason'], status['crashes']), ('BACKOFF', 'STORAGE_UNAVAILABLE', 1))
        self.assertIn('SUPERVISION_OUTAGE_GAP_UNVERIFIED', [e['reason'] for e in self.saved()['events']])
        self.run_for(owner, 120); self.assertEqual(len(self.children), 2)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir() if not p.name.endswith(('-wal', '-shm'))),
                         ['imp-state.sqlite3'])

    def test_storage_that_never_returns_blocks_after_the_grace_period(self):
        owner = self.supervisor(); owner.tick()
        with patch.object(Path, 'stat', side_effect=FileNotFoundError):
            self.run_for(owner, STORAGE_GRACE_SECONDS)
            self.assertEqual(owner.status()['state'], 'STORAGE_WAIT')
            self.run_for(owner, 60)
            self.assertEqual((owner.status()['state'], owner.status()['reason']), ('BLOCKED', 'STORAGE_UNAVAILABLE'))
        self.assertEqual(len(self.children), 1)

    def test_replaced_store_is_never_adopted(self):
        owner = self.supervisor(); owner.tick()
        owner._identity = (owner._identity[0], owner._identity[1]+1)
        owner.tick()
        self.assertTrue(self.children[0].stopped)
        self.assertEqual((owner.status()['state'], owner.status()['reason']), ('BLOCKED', 'STORAGE_REPLACED'))

    def test_outage_claimed_by_another_supervisor_is_not_recovered(self):
        owner = self.supervisor(); owner.tick()
        with patch.object(Path, 'stat', side_effect=FileNotFoundError): owner.tick()
        self.now += 200
        replacement = self.supervisor()
        owner.tick()
        self.assertEqual((owner.status()['state'], owner.status()['reason']), ('BLOCKED', 'OWNERSHIP_LOST'))
        self.assertEqual(replacement.status()['state'], 'WAITING')

    def test_brief_database_contention_does_not_stop_the_child_or_spend_a_restart(self):
        owner = self.supervisor(); owner.tick()
        blocker = sqlite3.connect(self.path, isolation_level=None)
        self.db.execute('PRAGMA busy_timeout=50')
        try:
            blocker.execute('BEGIN IMMEDIATE')
            self.run_for(owner, 30, step=10)
            self.assertFalse(self.children[0].stopped)
            self.assertEqual((owner.status()['state'], owner.status()['crashes']), ('RUNNING', 0))
        finally:
            blocker.execute('ROLLBACK'); blocker.close()
        owner.tick()
        self.assertEqual(owner.status()['state'], 'RUNNING')
        self.assertEqual(len(self.children), 1)

    def test_contention_longer_than_half_the_lease_stops_the_child_then_recovers(self):
        owner = self.supervisor(); owner.tick()
        blocker = sqlite3.connect(self.path, isolation_level=None)
        self.db.execute('PRAGMA busy_timeout=50')
        try:
            blocker.execute('BEGIN IMMEDIATE')
            self.run_for(owner, 70, step=10)
            self.assertTrue(self.children[0].stopped)
            self.assertEqual((owner.status()['state'], owner.status()['reason']),
                             ('STORAGE_WAIT', 'SUPERVISION_EVIDENCE_UNAVAILABLE'))
        finally:
            blocker.execute('ROLLBACK'); blocker.close()
        owner.tick()
        self.assertEqual((owner.status()['state'], owner.status()['crashes']), ('BACKOFF', 1))
        self.run_for(owner, 120); self.assertEqual(len(self.children), 2)


class MediumDurationFailureTests(SupervisorCase):
    """A child that fails after 20 to 29 minutes never fills a rolling window and never reaches 30 healthy minutes."""

    def fail_after(self, owner, uptime):
        """Wait out the backoff, let the child run for `uptime` seconds, then exit 1."""
        self.run_for(owner, max(0, owner.status()['next_start']-self.now))
        self.run_for(owner, uptime); self.crash(owner)

    def test_child_failing_every_25_minutes_is_latched_and_stops_restarting(self):
        owner = self.supervisor(); owner.tick(); states = []
        for _ in range(UNHEALTHY_FAILURE_LIMIT):
            self.fail_after(owner, 1500); states.append(owner.status()['state'])
        # The rolling window alone never notices: no failure reached a cooldown.
        self.assertEqual(states[:-1], ['BACKOFF']*(UNHEALTHY_FAILURE_LIMIT-1))
        status = owner.status()
        self.assertEqual((status['state'], status['reason'], status['latched'], status['cooldowns']),
                         ('BLOCKED', 'PERSISTENT_CHILD_FAILURE', 'PERSISTENT_CHILD_FAILURE', 0))
        self.assertLess(status['restarts_in_window'], RESTART_LIMIT)
        total = len(self.children)
        self.assertEqual(total, UNHEALTHY_FAILURE_LIMIT)
        self.run_for(owner, LATCH_EXPIRY_SECONDS-900)  # the latch expires only after LATCH_EXPIRY_SECONDS
        self.assertEqual(len(self.children), total)
        reasons = [event['reason'] for event in self.saved()['events']]
        self.assertEqual(reasons.count('CHILD_PROCESS_EXIT_GAP_UNVERIFIED'), UNHEALTHY_FAILURE_LIMIT)
        self.assertEqual(reasons[-1], 'PERSISTENT_CHILD_FAILURE')
        # Restarting the supervisor does not clear it; the operator reset does.
        owner.stop(); replacement = self.supervisor(); self.run_for(replacement, 600)
        self.assertEqual((replacement.status()['latched'], len(self.children)), ('PERSISTENT_CHILD_FAILURE', total))
        replacement.stop()
        self.assertEqual(reset_restart_budget(self.db, clock=lambda: self.now)['unhealthy_failures'], 0)
        recovered = self.supervisor(); recovered.tick()
        self.assertEqual((recovered.status()['state'], len(self.children)), ('RUNNING', total+1))

    def test_starts_stay_inside_the_window_limit_and_backoff_until_the_latch(self):
        owner = self.supervisor(); owner.tick()
        for _ in range(UNHEALTHY_FAILURE_LIMIT):
            self.fail_after(owner, 1260)
        starts = [event['at'] for event in self.saved()['events'] if event['reason'] == 'CHILD_START_ATTEMPT']
        self.assertEqual(len(starts), UNHEALTHY_FAILURE_LIMIT)
        for at in starts:
            self.assertLessEqual(sum(at < other <= at+RESTART_WINDOW_SECONDS for other in starts), RESTART_LIMIT)
        self.assertGreaterEqual(min(b-a for a, b in zip(starts, starts[1:])), 1260+supervision.LEASE_SECONDS)

    def test_one_healthy_period_clears_the_streak(self):
        owner = self.supervisor(); owner.tick()
        for _ in range(UNHEALTHY_FAILURE_LIMIT-1):
            self.fail_after(owner, 1500)
        self.assertEqual(owner.status()['unhealthy_failures'], UNHEALTHY_FAILURE_LIMIT-1)
        self.fail_after(owner, HEALTHY_RESET_SECONDS)
        self.assertEqual((owner.status()['state'], owner.status()['unhealthy_failures']), ('BACKOFF', 1))
        self.assertEqual(owner.status()['next_start']-self.now, 120)

    def test_uptime_one_tick_short_of_healthy_does_not_clear_the_streak(self):
        owner = self.supervisor(); owner.tick()
        self.fail_after(owner, 0); self.fail_after(owner, HEALTHY_RESET_SECONDS-30)
        self.assertEqual(owner.status()['unhealthy_failures'], 2)

    def test_restart_leaves_the_window_exactly_at_its_boundary(self):
        owner = self.supervisor(); owner.tick(); self.crash(owner)
        self.run_for(owner, 120); restarted = self.now
        self.assertEqual(owner.status()['restarts'], [restarted])
        self.now = restarted+RESTART_WINDOW_SECONDS-1
        self.assertEqual(owner.status()['restarts_in_window'], 1)
        self.now = restarted+RESTART_WINDOW_SECONDS
        self.assertEqual(owner.status()['restarts_in_window'], 0)
        self.crash(owner)
        # The expired restart no longer lengthens the backoff.
        self.assertEqual((owner.status()['restarts'], owner.status()['next_start']-self.now), ([], 120))

    def test_supervisor_side_outages_are_not_counted_as_child_failures(self):
        owner = self.supervisor(); owner.tick()
        for _ in range(UNHEALTHY_FAILURE_LIMIT+1):
            with patch.object(owner, '_storage_fault', return_value='STORAGE_UNAVAILABLE'):
                self.run_for(owner, 60)
            self.assertTrue(self.children[-1].stopped)
            self.run_for(owner, 30)
            self.run_for(owner, max(0, owner.status()['next_start']-self.now)+RESTART_WINDOW_SECONDS)
        status = owner.status()
        self.assertEqual((status['unhealthy_failures'], status['latched']), (0, None))

    def test_evidence_written_before_the_streak_counter_loads_with_zero(self):
        owner = self.supervisor(); owner.tick(); owner.stop()
        saved = self.saved(); saved.pop('unhealthy_failures')
        self.db.execute('UPDATE news_collection_jobs SET payload_json=? WHERE job_id=?', (json.dumps(saved), SUPERVISION_JOB))
        replacement = self.supervisor(); replacement.tick()
        self.assertEqual((replacement.status()['unhealthy_failures'], replacement.status()['state']), (0, 'RUNNING'))


class SupervisorCliTests(unittest.TestCase):
    def test_bounded_wait_for_a_dead_owner_then_gives_up_on_a_live_one(self):
        from tools.platform import pf01_supervisor
        clock = [0.]; attempts = []
        def constructor(connection, *, spawn, env):
            attempts.append(clock[0])
            if clock[0] < 120: raise ValueError('SUPERVISOR_OWNER_ACTIVE')
            return 'owner'
        def sleep(seconds): clock[0] += seconds
        with patch.object(pf01_supervisor, 'CollectionSupervisor', side_effect=constructor), patch('builtins.print') as out:
            self.assertEqual(pf01_supervisor.own(None, None, sleep=sleep, clock=lambda: clock[0]), 'owner')
        self.assertEqual(out.call_count, 1)  # the reason for the delay is stated once
        self.assertIn('SUPERVISOR_OWNER_ACTIVE', out.call_args.args[0])
        clock[0] = 0.
        def always(connection, *, spawn, env): raise ValueError('SUPERVISOR_OWNER_ACTIVE')
        with patch.object(pf01_supervisor, 'CollectionSupervisor', side_effect=always), patch('builtins.print'):
            with self.assertRaisesRegex(ValueError, 'SUPERVISOR_OWNER_ACTIVE'):
                pf01_supervisor.own(None, None, sleep=sleep, clock=lambda: clock[0])
        self.assertLessEqual(clock[0], pf01_supervisor.OWNER_WAIT_SECONDS+5)

    def test_plan_and_status_are_read_only_and_reset_never_starts_a_child(self):
        import os
        from tools.platform import pf01_supervisor
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'imp-state.sqlite3'
            LocalStateConnection(path).close()
            before = path.read_bytes()
            env = {'IMP_STATE_DIR': directory}
            with patch.dict(os.environ, env, clear=True), patch('builtins.print') as out, \
                 patch.object(pf01_supervisor.subprocess, 'Popen', side_effect=AssertionError('spawned')):
                self.assertEqual(pf01_supervisor.main([]), 0)
                self.assertEqual(json.loads(out.call_args.args[0])['restart_window_seconds'], RESTART_WINDOW_SECONDS)
                self.assertEqual(pf01_supervisor.main(['--status']), 0)
                self.assertEqual(json.loads(out.call_args.args[0])['state'], 'DISABLED')
                self.assertEqual(path.read_bytes(), before)
                with self.assertRaisesRegex(ValueError, 'SUPERVISION_EVIDENCE_MISSING'):
                    pf01_supervisor.main(['--reset-restart-budget'])


if __name__ == '__main__':
    unittest.main()
