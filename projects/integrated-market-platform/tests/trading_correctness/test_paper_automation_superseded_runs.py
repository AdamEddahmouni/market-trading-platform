"""IMP-009 — a superseded cycle must not drop the handle of the universe run it started.

SOFTWARE_CONTROLLED, over the production controller and the AUTO-01 fixtures. A cycle starts a
full-universe run; while that cycle is still running the operator pauses or stops automation, so the
cycle's write-back is superseded. Before the fix the run's only handle (``universe.active_run_id``) lived
in the cycle's working copy and was discarded: ``_halt`` could not stop the run and no close event was ever
written for it.
"""
from __future__ import annotations

import copy

from tests.trading_correctness.test_paper_automation import AutoBase

CLOSES = ('UNIVERSE_RUN_FINISHED', 'UNIVERSE_RUN_INTERRUPTED')


class SupersededCycleRunHandleTests(AutoBase):
    def ready(self):
        a = self.auto
        a.quote('AAPL', 150, 2)
        a.opportunity('AAPL')
        a.go()
        return a

    def operator_during_run_start(self, a, command):
        """The operator command lands just after this cycle started its universe run, before write-back."""
        original = a.runs.start

        def start_then_command(*args, **kwargs):
            started = original(*args, **kwargs)
            a.runs.start = original
            command()
            return started
        a.runs.start = start_then_command

    def closed(self, a, run_id):
        return [e for kind in CLOSES for e in a.events(kind) if e.get('run_id') == run_id]

    # --- Pause: the handle is kept --------------------------------------------------------------
    def test_pause_during_the_starting_cycle_keeps_the_run_handle(self):
        a = self.ready()
        self.operator_during_run_start(a, a.service.pause)
        cycle = a.cycle()
        self.assertTrue(cycle.get('superseded'))
        self.assertEqual([r['run_id'] for r in a.runs.started], ['AIR-1'])
        self.assertEqual(a.service.status()['status'], 'PAUSED')
        self.assertEqual(a.service.status()['universe']['active_run_id'], 'AIR-1')
        self.assertEqual((a.runs.stopped, self.closed(a, 'AIR-1')), ([], []))  # still running, still tracked

    def test_a_kept_handle_lets_a_later_stop_reach_the_run(self):
        a = self.ready()
        self.operator_during_run_start(a, a.service.pause)
        a.cycle()
        a.service.stop()  # _halt stops only runs named by the persisted controller
        self.assertEqual(a.runs.stopped, ['AIR-1'])

    def test_after_resume_the_run_is_recorded_finished(self):
        a = self.ready()
        self.operator_during_run_start(a, a.service.pause)
        a.cycle()
        a.service.resume()
        a.runs.finish('AIR-1', ['AAPL'])
        a.cycle()
        self.assertEqual([e['status'] for e in self.closed(a, 'AIR-1')], ['GLOBAL_SELECTION_COMPLETE'])
        self.assertEqual(len(a.runs.started), 1)  # the run was not abandoned and restarted under a new id

    # --- Stop: the run is stopped and its end recorded at once ----------------------------------
    def test_stop_during_the_starting_cycle_stops_the_run_and_records_its_end(self):
        a = self.ready()
        self.operator_during_run_start(a, a.service.stop)
        cycle = a.cycle()
        self.assertTrue(cycle.get('superseded'))
        self.assertEqual(a.service.status()['status'], 'STOPPED')
        self.assertEqual(a.runs.stopped, ['AIR-1'])
        interrupted = a.events('UNIVERSE_RUN_INTERRUPTED')
        self.assertEqual([(e['run_id'], e['reason']) for e in interrupted], [('AIR-1', 'CYCLE_SUPERSEDED')])

    def test_every_started_run_has_a_recorded_end_after_a_superseding_stop(self):
        a = self.ready()
        self.operator_during_run_start(a, a.service.stop)
        a.cycle()
        started = [e['run_id'] for e in a.events('UNIVERSE_RUN_STARTED')]
        self.assertEqual(started, ['AIR-1'])
        self.assertEqual({run_id: len(self.closed(a, run_id)) for run_id in started}, {'AIR-1': 1})

    # --- Guard: a run tracked before the superseded cycle is not touched ------------------------
    def test_a_run_already_tracked_before_the_superseded_cycle_is_left_alone(self):
        a = self.ready()
        a.cycle()  # starts AIR-1; the handle is persisted by a normal write-back
        self.assertEqual(a.service.status()['universe']['active_run_id'], 'AIR-1')
        original = a.runs.read

        def read_then_pause(*args, **kwargs):
            a.runs.read = original
            a.service.pause()
            return original(*args, **kwargs)
        a.runs.read = read_then_pause
        self.assertTrue(a.cycle().get('superseded'))
        self.assertEqual(a.service.status()['universe']['active_run_id'], 'AIR-1')
        self.assertEqual((a.runs.stopped, a.events('UNIVERSE_RUN_INTERRUPTED')), ([], []))


class SettleSupersededScopesTests(AutoBase):
    """Direct checks of the settle step for multi-scope controllers (no multi-scope fixture drives a full cycle)."""

    def orphaned(self, origin):
        a = self.auto
        a.go()
        a.service.stop()
        fresh = a.service._controller()  # the operator's Stop is what the cycle finds at write-back
        work = copy.deepcopy(fresh)
        work['desired_state'] = 'RUNNING'
        handle = dict(active_run_id='AIR-9', origin=origin)
        # Multi-scope cycles keep the primary scope's state and its legacy projection; both name the run.
        work['universe'] = dict(handle)
        work['universes'] = {'US_EQUITIES': dict(universe=dict(handle))}
        a.service._settle_superseded_universe_runs(work, fresh)
        return a

    def test_a_run_named_by_scope_and_projection_is_stopped_and_closed_once(self):
        a = self.orphaned('AUTOMATION')
        self.assertEqual(a.runs.stopped, ['AIR-9'])
        self.assertEqual([e['run_id'] for e in a.events('UNIVERSE_RUN_INTERRUPTED')], ['AIR-9'])

    def test_a_joined_operator_run_is_not_stopped_by_a_superseded_cycle(self):
        # As in _halt, the automation stops only runs it started itself.
        a = self.orphaned('OPERATOR')
        self.assertEqual(a.runs.stopped, [])
        self.assertEqual([e['run_id'] for e in a.events('UNIVERSE_RUN_INTERRUPTED')], ['AIR-9'])
