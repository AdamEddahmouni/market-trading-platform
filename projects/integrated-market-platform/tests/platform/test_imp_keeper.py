"""The keeper (owner decision 3, 2026-10-23): OpenD, the collector and the platform come back on their own,
bounded, in order, and every restart is logged. Fakes only: no process, port, store or provider is touched."""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools.platform import imp_keeper
from tools.platform.imp_keeper import (ALLOWANCES, BACKOFF_SECONDS, COOL_OFF_SECONDS, OPEND_CHECK_SECONDS,
    PAPER_OUTCOME_SECONDS, TICK_SECONDS, InstanceLock, Keeper, KeeperPaths, paper_outcome)
from tools.platform.restart_log import RestartLog

START = 1_800_000_000.0


class Clock:
    def __init__(self, value=START):
        self.value = value

    def __call__(self):
        return self.value


class FakeProcess:
    pid = 4242

    def __init__(self, ops):
        self.ops, self.killed = ops, False

    def poll(self):
        return self.ops.verify_code

    def kill(self):
        self.killed = True
        self.ops.calls.append(('store_verify_kill', self.ops.clock.value))


class FakeOps:
    """The machine as the keeper sees it. Every action is recorded in ``calls``."""

    def __init__(self, clock):
        self.clock, self.calls = clock, []
        self.boot = START - 3600
        self.opend_running, self.opend_ok, self.opend_recovers, self.launch_error = True, True, True, None
        self.collector_running, self.collector_stays, self.supervision = True, True, {}
        self.answering, self.health, self.start_code, self.paper = True, {'data_flow': {'state': 'WATCHING'}}, 0, None
        # The store: no check running, a receipt one minute old, and a nightly check that finishes with ``verify_code``.
        self.verifying, self.receipt_age, self.verify_code, self.verify_process = False, 60.0, None, None

    def store_verifying(self):
        return self.verifying

    def store_receipt_age(self):
        return self.receipt_age

    def store_verify_spawn(self):
        self.calls.append(('store_verify_spawn', self.clock.value))
        self.verify_process = FakeProcess(self)
        return self.verify_process

    def boot_epoch(self):
        return self.boot

    def opend_pids(self):
        return [42] if self.opend_running else []

    def opend_health(self):
        return {'healthy': self.opend_ok, 'reason': None if self.opend_ok else 'QUOTE_NOT_LOGGED_IN'}

    def opend_close(self, pid, *, force):
        self.calls.append(('opend_close', force))
        self.opend_running = False

    def opend_launch(self):
        self.calls.append(('opend_launch', self.clock.value))
        if self.launch_error:
            raise self.launch_error
        self.opend_running, self.opend_ok = True, self.opend_recovers

    def collector_pids(self):
        return [7] if self.collector_running else []

    def collector_supervision(self):
        return dict(self.supervision)

    def collector_spawn(self):
        self.calls.append(('collector_spawn', self.clock.value))
        self.collector_running = self.collector_stays
        return 99

    def platform_answering(self):
        return self.answering

    def platform_health(self):
        return self.health

    def platform_start(self, *, stop_first):
        self.calls.append(('platform_start', stop_first, self.clock.value))
        if self.start_code == 0:
            self.answering, self.health = True, {'data_flow': {'state': 'WATCHING'}}
        return self.start_code

    def paper_status(self):
        return self.paper

    def sleep(self, seconds):
        self.clock.value += seconds

    def actions(self, name):
        return [call for call in self.calls if call[0] == name]


class KeeperCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        base = Path(folder.name)
        self.paths = KeeperPaths(app=base / 'app', portable=base / 'portable')
        (self.paths.portable / 'collector').mkdir(parents=True)
        self.clock = Clock()
        self.ops = FakeOps(self.clock)

    def keeper(self, **kwargs):
        return Keeper(self.ops, self.paths, clock=self.clock, **kwargs)

    def run_ticks(self, keeper, count, step=TICK_SECONDS):
        for _ in range(count):
            keeper.tick()
            self.clock.value += step

    def run_until(self, keeper, done, limit=2000):
        for _ in range(limit):
            if done():
                return
            self.run_ticks(keeper, 1)
        self.fail('condition not reached')

    def budget_spent_then_one_more(self, keeper, component, action):
        """Run to the spent allowance, check its cool-off, then run to the next attempt. Returns the attempt times."""
        self.run_until(keeper, lambda: self.log(component, 'BUDGET_SPENT'))
        limit, window = ALLOWANCES[component]
        times = [call[-1] for call in self.ops.actions(action)]
        self.assertEqual(len(times), limit)
        spent = self.log(component, 'BUDGET_SPENT')[0]
        retry_at = spent['detail']['retry_at_epoch']
        self.assertGreaterEqual(retry_at, spent['at_epoch'] + COOL_OFF_SECONDS - 1)
        # Never more than the limit inside one window (an attempt is counted a few seconds before its launch).
        self.assertGreaterEqual(retry_at, times[0] + window - 10)
        self.run_until(keeper, lambda: len(self.ops.actions(action)) > limit)
        self.assertGreaterEqual(self.ops.actions(action)[-1][-1], retry_at)  # a fresh allowance, not a permanent block
        self.assertEqual(len(self.log(component, 'BUDGET_SPENT')), 1)
        return times

    def log(self, component=None, event=None):
        return [entry for entry in RestartLog(self.paths.log_file).read()
                if (component is None or entry['component'] == component) and (event is None or entry['event'] == event)]


class StartAndRebootTests(KeeperCase):
    def test_with_everything_up_the_keeper_only_records_its_own_start(self):
        keeper = self.keeper()
        self.run_ticks(keeper, 10)
        self.assertEqual(self.ops.calls, [])
        self.assertEqual([(e['component'], e['event']) for e in self.log()], [('KEEPER', 'STARTED')])
        self.assertTrue(self.paths.state_file.is_file())

    def test_a_reboot_is_logged_with_how_long_the_pc_was_down_and_is_the_cause_of_what_follows(self):
        self.run_ticks(self.keeper(), 2)
        last_heartbeat = self.clock.value - TICK_SECONDS
        # The PC is off for two hours; it boots, and the keeper starts five minutes after the boot.
        self.clock.value += 7200
        self.ops.boot = self.clock.value - 300
        self.ops.collector_running = False
        self.keeper().tick()
        reboot = self.log('PC', 'REBOOT')[0]
        self.assertEqual((reboot['cause'], reboot['outcome']), ('REBOOT', 'DETECTED'))
        self.assertAlmostEqual(reboot['down_seconds'], self.ops.boot - last_heartbeat, places=0)
        start = self.log('COLLECTOR', 'START')[0]
        self.assertEqual((start['cause'], start['outcome'], start['attempt']), ('REBOOT', 'RUNNING', 1))
        self.assertGreaterEqual(start['down_seconds'], 7200)  # counted from when the keeper last saw the PC

    def test_a_restarted_keeper_without_a_reboot_does_not_claim_one(self):
        self.run_ticks(self.keeper(), 2)
        self.clock.value += 60
        self.keeper().tick()
        self.assertEqual(self.log('PC'), [])
        self.assertEqual(len(self.log('KEEPER', 'STARTED')), 2)


class PlatformTests(KeeperCase):
    def test_a_platform_that_stops_answering_is_restarted_after_three_checks(self):
        keeper = self.keeper()
        self.ops.answering = False
        self.run_ticks(keeper, 2)
        self.assertEqual(self.ops.actions('platform_start'), [])
        self.run_ticks(keeper, 1)
        self.assertEqual([call[1] for call in self.ops.actions('platform_start')], [False])
        entry = self.log('PLATFORM', 'RESTART')[0]
        self.assertEqual((entry['cause'], entry['outcome'], entry['attempt'], entry['detail']['exit_code']),
                         ('NOT_ANSWERING', 'READY', 1, 0))
        self.assertGreaterEqual(entry['down_seconds'], 2 * TICK_SECONDS)
        self.assertIsNotNone(keeper.state['paper_watch'])

    def test_failed_starts_back_off_cool_off_and_then_try_again_never_for_ever_and_never_tightly(self):
        keeper = self.keeper()
        self.ops.answering, self.ops.start_code = False, 1  # a platform that never comes up
        starts = self.budget_spent_then_one_more(keeper, 'PLATFORM', 'platform_start')
        gaps = [later - earlier for earlier, later in zip(starts, starts[1:])]
        self.assertTrue(all(gap >= wait for gap, wait in zip(gaps, BACKOFF_SECONDS)))
        self.assertEqual({e['outcome'] for e in self.log('PLATFORM', 'RESTART')}, {'START_FAILED'})

    def test_an_unrecoverable_feed_restarts_the_platform_only_while_opend_is_healthy(self):
        keeper = self.keeper()
        self.ops.health = {'data_flow': {'state': 'UNRECOVERABLE'}}
        self.ops.opend_ok = False  # OpenD itself is the problem: restarting the platform cannot help yet
        self.run_ticks(keeper, 3)
        self.assertEqual(self.ops.actions('platform_start'), [])
        self.assertEqual([e['outcome'] for e in self.log('PLATFORM', 'WAITING')], ['WAITING_FOR_OPEND'])
        self.ops.opend_ok = True
        self.run_ticks(keeper, 4)
        self.assertEqual([call[1] for call in self.ops.actions('platform_start')], [True])  # stopped first, then started
        entry = self.log('PLATFORM', 'RESTART')[0]
        self.assertEqual((entry['cause'], entry['outcome'], entry['detail']['stopped_first']), ('FEED_UNRECOVERABLE', 'READY', True))


class OpenDTests(KeeperCase):
    def test_a_lost_login_is_restarted_after_three_checks_politely_then_by_force(self):
        keeper = self.keeper()
        self.ops.opend_ok = False
        self.run_ticks(keeper, 2, step=OPEND_CHECK_SECONDS)
        self.assertEqual(self.ops.actions('opend_launch'), [])
        self.run_ticks(keeper, 1, step=OPEND_CHECK_SECONDS)
        self.assertEqual(self.ops.actions('opend_close'), [('opend_close', False)])  # it closed politely in time
        self.assertEqual(len(self.ops.actions('opend_launch')), 1)
        entry = self.log('OPEND', 'RESTART')[0]
        self.assertEqual((entry['cause'], entry['outcome'], entry['attempt']), ('QUOTE_NOT_LOGGED_IN', 'RECOVERED', 1))
        self.assertEqual(entry['detail']['login_wait_seconds'], 10)

    def test_no_opend_process_is_started_at_once(self):
        keeper = self.keeper()
        self.ops.opend_running = False
        keeper.tick()
        self.assertEqual(len(self.ops.actions('opend_launch')), 1)
        self.assertEqual(self.log('OPEND', 'RESTART')[0]['cause'], 'OPEND_NOT_RUNNING')

    def test_a_missing_opend_program_is_recorded_not_hidden(self):
        keeper = self.keeper()
        self.ops.opend_running, self.ops.launch_error = False, FileNotFoundError('OPEND_NOT_INSTALLED: x')
        keeper.tick()
        entry = self.log('OPEND', 'RESTART')[0]
        self.assertEqual((entry['outcome'], entry['detail']['error']), ('LAUNCH_FAILED', 'FileNotFoundError'))

    def test_opend_keeps_the_old_watchdogs_four_restarts_per_six_hours_then_cools_off(self):
        keeper = self.keeper()
        self.ops.opend_ok, self.ops.opend_recovers = False, False  # e.g. the remembered login has expired
        self.assertEqual(ALLOWANCES['OPEND'], (4, 6 * 3600))
        self.budget_spent_then_one_more(keeper, 'OPEND', 'opend_launch')
        self.assertEqual({e['outcome'] for e in self.log('OPEND', 'RESTART')}, {'NOT_RECOVERED'})

    def test_nothing_downstream_is_restarted_while_opend_is_being_restarted(self):
        keeper = self.keeper()
        self.ops.opend_running, self.ops.answering = False, False
        keeper.tick()
        self.assertEqual(self.ops.calls[0][0], 'opend_launch')  # OpenD first, in the same pass
        self.assertEqual(self.ops.actions('platform_start'), [])  # the platform waits for its own three checks


class CollectorTests(KeeperCase):
    def test_a_missing_collector_is_started_and_confirmed(self):
        keeper = self.keeper()
        self.ops.collector_running = False
        keeper.tick()
        entry = self.log('COLLECTOR', 'START')[0]
        self.assertEqual((entry['cause'], entry['outcome'], entry['detail']['pid']), ('PROCESS_GONE', 'RUNNING', 99))

    def test_a_collector_that_exits_at_once_is_recorded_and_retried_within_its_allowance(self):
        keeper = self.keeper()
        self.ops.collector_running = self.ops.collector_stays = False
        self.budget_spent_then_one_more(keeper, 'COLLECTOR', 'collector_spawn')
        self.assertEqual({e['outcome'] for e in self.log('COLLECTOR', 'START')}, {'EXITED_AT_ONCE'})

    def test_an_owner_disabled_collector_is_left_stopped(self):
        keeper = self.keeper()
        self.ops.collector_running = False
        self.paths.collector_disabled.write_text('owner', encoding='utf-8')
        self.run_ticks(keeper, 5)
        self.assertEqual(self.ops.actions('collector_spawn'), [])
        self.assertEqual([(e['cause'], e['outcome']) for e in self.log('COLLECTOR')], [('DISABLED_BY_OWNER', 'NOT_STARTED')])

    def test_a_rejected_configuration_waits_for_the_owner(self):
        keeper = self.keeper()
        self.ops.collector_running = False
        self.ops.supervision = {'latched': 'CHILD_CONFIGURATION_REJECTED'}
        self.run_ticks(keeper, 200)
        self.assertEqual(self.ops.actions('collector_spawn'), [])
        waiting = self.log('COLLECTOR', 'WAITING')
        self.assertEqual(len(waiting), 1)
        self.assertTrue(waiting[0]['detail']['manual_reset_needed'])

    def test_a_persistent_failure_latch_is_waited_out_then_the_collector_is_started(self):
        keeper = self.keeper()
        self.ops.collector_running = False
        self.ops.supervision = {'latched': 'PERSISTENT_CHILD_FAILURE', 'latched_at': START, 'latch_expiry_seconds': 7200}
        self.run_ticks(keeper, int(7200 // TICK_SECONDS) - 2)
        self.assertEqual(self.ops.actions('collector_spawn'), [])
        self.assertEqual(len(self.log('COLLECTOR', 'WAITING')), 1)
        self.run_ticks(keeper, 3)
        self.assertEqual(len(self.ops.actions('collector_spawn')), 1)


class PauseAndPaperTests(KeeperCase):
    def test_a_paused_keeper_does_nothing_but_says_so(self):
        keeper = self.keeper()
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        self.paths.paused_file.write_text('deploy', encoding='utf-8')
        self.ops.opend_running = self.ops.collector_running = self.ops.answering = False
        self.run_ticks(keeper, 10)
        self.assertEqual(self.ops.calls, [])
        self.paths.paused_file.unlink()
        keeper.tick()
        self.assertEqual([e['event'] for e in self.log('KEEPER')], ['STARTED', 'PAUSED', 'RESUMED'])
        self.assertTrue(self.ops.actions('opend_launch'))

    def test_what_the_paper_controller_did_after_a_restart_is_recorded(self):
        keeper = self.keeper()
        self.ops.answering = False
        self.run_ticks(keeper, 3)
        self.ops.paper = dict(status='RUNNING', armed=True, desired_state='RUNNING', run={'run_id': 'PAR-new'},
                              liveness={'owner': 'THIS_PROCESS', 'worker_alive': True})
        self.run_ticks(keeper, 1)
        entry = self.log('PAPER_CONTROLLER', 'RESUME')[0]
        self.assertEqual((entry['cause'], entry['outcome'], entry['detail']['run_id']), ('PLATFORM_RESTART', 'RESUMED', 'PAR-new'))
        self.assertIsNone(keeper.state['paper_watch'])

    def test_a_controller_that_does_not_come_back_in_time_is_recorded_as_such(self):
        keeper = self.keeper()
        self.ops.answering = False
        self.run_ticks(keeper, 3)
        self.ops.paper = dict(status='ERROR', armed=True, desired_state='RUNNING', liveness={'owner': None, 'worker_alive': False})
        self.run_ticks(keeper, int(PAPER_OUTCOME_SECONDS // TICK_SECONDS) + 2)
        self.assertEqual([e['outcome'] for e in self.log('PAPER_CONTROLLER')], ['NOT_RESUMED_IN_TIME'])

    def test_paper_outcome_reads_only_the_status(self):
        since = START
        running = dict(armed=True, desired_state='RUNNING')
        self.assertEqual(paper_outcome(None, since=since), (None, {}))
        self.assertEqual(paper_outcome(dict(status='NOT_CONFIGURED'), since=since)[0], 'NOT_CONFIGURED')
        self.assertEqual(paper_outcome(dict(armed=False, desired_state='STOPPED'), since=since)[0], 'NOT_ARMED')
        self.assertEqual(paper_outcome(dict(armed=True, desired_state='STOPPED'), since=since)[0], 'NOT_RUNNING_BEFORE_RESTART')
        self.assertEqual(paper_outcome(dict(running, emergency={'at': 'x'}), since=since)[0], 'EMERGENCY_STOPPED')
        refused = dict(running, liveness={'last_error': {'code': 'PAPER_RISK_POLICY_CHANGED', 'at': '2027-01-15T08:00:00Z'}})
        self.assertEqual(paper_outcome(refused, since=since), ('REFUSED', {'reason': 'PAPER_RISK_POLICY_CHANGED'}))
        stale = dict(running, liveness={'last_error': {'code': 'OLD', 'at': '2020-01-01T00:00:00Z'}})
        self.assertEqual(paper_outcome(stale, since=since), (None, {}))  # an error from before the restart is not its outcome

    def test_the_keeper_has_no_way_to_arm_start_or_stop_paper(self):
        source = Path(imp_keeper.__file__).read_text(encoding='utf-8')
        for operation in ('arm', 'start', 'resume', 'stop', 'pause', 'configure', 'disarm', 'emergency-stop'):
            self.assertNotIn('/paper/automation/' + operation, source)
        self.assertNotIn('data=', source)  # it never sends a request body: every HTTP call is a GET
        self.assertNotIn('IMP_PAPER_EXECUTION', source)
        self.assertNotIn('IMP_LIVE', source)


class DryRunAndLockTests(KeeperCase):
    def test_a_dry_run_starts_nothing_writes_nothing_and_reads_no_store(self):
        self.ops.opend_running = self.ops.collector_running = self.ops.answering = False
        self.ops.collector_supervision = lambda: self.fail('a dry run must not read the store')
        output = io.StringIO()
        with redirect_stdout(output):
            summary = self.keeper(dry_run=True).tick()
        self.assertEqual([call[0] for call in self.ops.calls], [])
        self.assertFalse(self.paths.state_dir.exists())
        self.assertEqual(summary['collector'], 'DRY_RUN_NOT_STARTED')
        self.assertEqual(summary['platform'], 'DRY_RUN_NOT_STARTED')
        printed = output.getvalue()
        for component in ('OPEND', 'COLLECTOR', 'PLATFORM'):
            self.assertIn('"component": "%s"' % component, printed)

    def test_one_keeper_per_pc(self):
        first, second = InstanceLock(self.paths.lock_file), InstanceLock(self.paths.lock_file)
        self.assertTrue(first.acquire())
        self.addCleanup(first.release)
        self.assertFalse(second.acquire())
        first.release()
        self.assertTrue(second.acquire())
        second.release()

    def test_a_stop_file_ends_the_loop_and_says_why(self):
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        self.paths.stop_file.write_text('deploy', encoding='utf-8')
        self.assertEqual(self.keeper().run(), 0)
        self.assertEqual(self.log('KEEPER', 'STOPPED')[0]['cause'], 'STOP_FILE')


def eastern_epoch(year, month, day, hour, minute):
    """The epoch of a US/Eastern wall-clock time, as the keeper reads it (local time without a tz database)."""
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo

        return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo('America/New_York')).timestamp()
    except Exception:  # noqa: BLE001
        return datetime(year, month, day, hour, minute).timestamp()


class StoreVerifyTests(KeeperCase):
    """2026-10-27: a platform start waited out a whole-store scan, the keeper restarted it, and each restart began
    the scan again. The keeper now waits for a visible scan and renews the receipt off-hours."""

    def at(self, hour, minute, day=27):
        self.clock.value = eastern_epoch(2026, 10, day, hour, minute)

    def test_the_window_is_after_the_evening_close_and_before_pre_market(self):
        cases = [((20, 14), None), ((20, 15), '2026-10-27'), ((23, 59), '2026-10-27'), ((12, 0), None)]
        for (hour, minute), window in cases:
            self.assertEqual(imp_keeper.store_verify_window(eastern_epoch(2026, 10, 27, hour, minute)), window)
        self.assertEqual(imp_keeper.store_verify_window(eastern_epoch(2026, 10, 28, 3, 44)), '2026-10-27')
        self.assertIsNone(imp_keeper.store_verify_window(eastern_epoch(2026, 10, 28, 3, 45)))

    def test_a_stale_receipt_is_renewed_once_per_night_and_the_outcome_is_logged(self):
        keeper = self.keeper()
        self.ops.receipt_age = None
        self.at(20, 10)
        self.run_ticks(keeper, 5)
        self.assertEqual(self.ops.actions('store_verify_spawn'), [])  # not before the window
        self.at(20, 20)
        self.run_ticks(keeper, 5)
        self.assertEqual(len(self.ops.actions('store_verify_spawn')), 1)
        self.assertEqual(self.log('STORE', 'VERIFY'), [])  # still running
        self.ops.verify_code = 0
        self.run_ticks(keeper, 3)
        entry = self.log('STORE', 'VERIFY')[0]
        self.assertEqual((entry['cause'], entry['outcome'], entry['detail']['exit_code']), ('NIGHTLY', 'OK', 0))
        self.assertGreater(entry['detail']['elapsed_seconds'], 0)
        self.run_ticks(keeper, 50)  # the receipt reads stale again: still one try this night
        self.assertEqual(len(self.ops.actions('store_verify_spawn')), 1)
        self.at(20, 30, day=28)
        self.run_ticks(keeper, 1)
        self.assertEqual(len(self.ops.actions('store_verify_spawn')), 2)  # the next night tries again

    def test_a_fresh_receipt_or_a_pause_starts_nothing(self):
        keeper = self.keeper()
        self.at(21, 0)
        self.ops.receipt_age = 3600.0
        self.run_ticks(keeper, 5)
        self.assertEqual(self.ops.actions('store_verify_spawn'), [])
        self.ops.receipt_age = None
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        self.paths.paused_file.write_text('deploy', encoding='utf-8')
        self.run_ticks(keeper, 5)
        self.assertEqual(self.ops.actions('store_verify_spawn'), [])

    def test_a_check_that_outlives_its_limit_is_stopped_and_logged(self):
        keeper = self.keeper()
        self.ops.receipt_age = None
        self.at(20, 30)
        keeper.tick()
        self.clock.value += imp_keeper.STORE_VERIFY_TIMEOUT_SECONDS + 1
        keeper.tick()
        self.assertEqual(len(self.ops.actions('store_verify_kill')), 1)
        self.assertEqual(self.log('STORE', 'VERIFY')[0]['outcome'], 'TIMED_OUT')

    def test_a_dry_run_starts_no_check(self):
        keeper = self.keeper(dry_run=True)
        self.ops.receipt_age = None
        self.at(21, 0)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(keeper.tick()['store_verify'], 'DRY_RUN_NOT_STARTED')
        self.assertEqual(self.ops.actions('store_verify_spawn'), [])

    def test_a_platform_reading_the_whole_store_is_waited_for_not_restarted(self):
        keeper = self.keeper()
        self.ops.answering, self.ops.verifying = False, True
        self.run_ticks(keeper, 40)  # twenty minutes of a scan
        self.assertEqual(self.ops.actions('platform_start'), [])
        self.assertEqual([e['outcome'] for e in self.log('PLATFORM', 'WAITING')], ['WAITING_FOR_STORE_VERIFY'])
        self.ops.verifying = False  # the scan ended but the API still does not answer: the usual three checks
        self.run_ticks(keeper, 2)
        self.assertEqual(self.ops.actions('platform_start'), [])
        self.run_ticks(keeper, 1)
        self.assertEqual(len(self.ops.actions('platform_start')), 1)

    def test_the_start_timeout_outlasts_the_launchers_wait_for_a_scan(self):
        from tools.platform.local_launcher import VERIFY_WAIT_CAP_SECONDS

        self.assertGreaterEqual(imp_keeper.PLATFORM_START_TIMEOUT_SECONDS, VERIFY_WAIT_CAP_SECONDS + 300)


if __name__ == '__main__':
    unittest.main()
