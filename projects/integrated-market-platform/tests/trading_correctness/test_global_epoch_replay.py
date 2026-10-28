"""ISOLATED DETERMINISTIC GLOBAL-EVALUATION REPLAY — one full coverage epoch at live scale.

SOFTWARE_CONTROLLED. The production controller (slice plans, run ownership, epoch folding, adoption, back-off,
pause, restart recovery) drives the production full-universe coverage method (``ScreenerAiCoverage``: local
one-row-per-request first pass, slice deadline, finalist limit, bounded reduction, row accounting, immutable
ledger rows, stored candidate runs). Only the clock, the Screener rows, the local engine's answers and the
run tracker's thread are fixtures: a run executes synchronously inside ``start``. Nothing here is market truth,
and this replay is not, and cannot stand in for, a natural global evaluation of the live account.

The universe is shaped like the live CRYPTO scope on 2026-10-27: 623 rows, 621 of them eligible (one without a
price, one whose provider state is unavailable). One row in three gets an answer the validator rejects, one row
is refused at send for its size, a few rows are controlled-strong, one call fails at the provider, one row's
quote is stale for one slice, and the run is paused, resumed, interrupted by a process loss and recovered.

With ``IMP_GLOBAL_REPLAY_OUT`` set to a directory, the replay also writes its receipts there as JSON.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
from market_platform_foundation.local_state.action_decisions import action_repository
from market_platform_foundation.local_state.ai_screener_coverage import coverage_ledger
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from market_platform_foundation.ui_api.screener_ai_coverage import ScreenerAiCoverage
from market_platform_foundation.ui_api.screener_ai_runs import AiScreenerRuns
from tests.support.coverage_universe import (
    SCOPE, News, PagingReader, RankingProvider, answer, full_tournament, instrument_id, row, strength,
)
from tests.trading_correctness.test_paper_automation import AutoBase

# The live scope runs the full tournament (no opportunity shortlist); so does this replay.
setUpModule, tearDownModule = full_tournament()

LABEL = 'ISOLATED DETERMINISTIC GLOBAL-EVALUATION REPLAY'
SHA = 'b' * 40
SIZE = 623
NO_PRICE, UNAVAILABLE = 5, 6                 # the two rows that are never eligible
REFUSED = 600                                # too large to send: refused before generation, every time
STRONG = {40: 91.0, 41: 90.0, 170: 92.0, 302: 93.0, 303: 94.0, 455: 95.0, 590: 96.0}
STALE_ONCE = 200                             # its quote is stale while slice STALE_SLICE is planned
STALE_SLICE = 3
FAIL_SLICE = 6                               # the provider fails one call of this slice
FIRST_PASS_SECONDS, COMPARISON_SECONDS = 7.5, 1.0
SEPARATION = 300                             # the live owner separation: a slice gets 40% of it, 120 s


def iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace('+00:00', 'Z')


def rejected(index):
    return index % 3 == 1 and index not in STRONG and index != REFUSED


class ReplayReader(PagingReader):
    """The Screener read contract over controlled rows, stamped at the engine clock; one row can be stale."""

    def __init__(self, rows, clock):
        super().__init__(rows)
        self.clock, self.stale = clock, False

    def read(self, **kwargs):
        page = super().read(**kwargs)
        now = iso(self.clock[0] - 1)
        rows = []
        for item in page['rows']:
            index = int(item['instrument']['instrument_id'].split('S')[-1])
            as_of = iso(self.clock[0] - 86400) if self.stale and index == STALE_ONCE else now
            fields = {name: dict(value, as_of=as_of) for name, value in item['fields'].items()}
            rows.append(dict(item, fields=fields))
        return dict(page, rows=rows, universe_as_of=now, screener_as_of=now)


class ReplayEngine(RankingProvider):
    """A local engine: every first-pass request takes 7.5 s of the engine clock and every comparison 1 s."""

    runtime = 'LOCAL_MODEL'

    def __init__(self, clock):
        super().__init__()
        self.clock = clock
        self.fail_next = False
        self.answers = []

    def on_call(self, call, packet):
        ids = [c['instrument']['instrument_id'] for c in packet.candidates]
        index = int(ids[0].split('S')[-1])
        if len(ids) == 1 and index == REFUSED:
            self.answers.append((ids, 'REFUSED_AT_SEND'))
            from dataclasses import replace
            return replace(self.failure('LOCAL_CONTEXT_EXCEEDED'), tokens_input=9000, inference_dispatched=False)
        self.clock[0] += FIRST_PASS_SECONDS if len(ids) == 1 else COMPARISON_SECONDS
        if self.fail_next:
            self.fail_next = False
            self.answers.append((ids, 'PROVIDER_FAILED'))
            return self.failure('LOCAL_ENGINE_UNAVAILABLE')
        if len(ids) == 1 and rejected(index):
            self.answers.append((ids, 'INVALID_OUTPUT'))
            return ProviderInferenceResponse('{not json', self.provider_id, self.model_id, tokens_input=1000,
                                             tokens_output=100, latency_ms=1, simulated=True)
        if len(ids) > 1:
            # A discriminating comparison: only the strongest advances.
            best = max(packet.candidates, key=lambda c: (strength(c), c['instrument']['instrument_id']))
            self.answers.append((ids, 'COMPARED'))
            return ProviderInferenceResponse(answer(packet.candidates, [best]), self.provider_id, self.model_id,
                                             tokens_input=1000, tokens_output=100, latency_ms=1, simulated=True)
        self.answers.append((ids, 'ANSWERED'))
        return self.respond(packet)


class CoverageRuns:
    """The run tracker, backed by the production coverage method and the local-state coverage ledger."""

    def __init__(self, controller_clock):
        self.controller_clock = controller_clock
        self.engine_clock = [controller_clock.value]
        rows = [row(index, rsi=STRONG.get(index, 50.0), price=None if index == NO_PRICE else 100.0 + index % 50,
                    state='UNAVAILABLE' if index == UNAVAILABLE else 'LIVE') for index in range(SIZE)]
        self.reader = ReplayReader(rows, self.engine_clock)
        self.engine = ReplayEngine(self.engine_clock)
        self.service = ScreenerAiService(reader=self.reader, news=News(self.engine), clock=lambda: self.engine_clock[0])
        self.started, self.snapshots, self.lost = [], {}, set()
        self.hold_next = False

    def start(self, account_id, body, *, spend_limit=None, origin='OPERATOR', slice_plan=None, order_bounds=None):
        run_id = f'replay{len(self.started) + 1:026d}'
        self.started.append(dict(run_id=run_id, at=self.controller_clock.value, origin=origin, slice_plan=slice_plan))
        self.snapshots[run_id] = dict(run_id=run_id, state='RUNNING', stage='EVALUATING', progress={}, origin=origin)
        if self.hold_next:
            # The owning process will be lost before this run writes anything.
            self.hold_next = False
            return dict(run_id=run_id, state='RUNNING', engine=dict(runtime='LOCAL_MODEL'))
        self.engine_clock[0] = self.controller_clock.value
        result = ScreenerAiCoverage(self.service, ledger=coverage_ledger(), software_sha=SHA).run(
            dict(SCOPE, **body), run_id=run_id, account_id=account_id, spend_limit=spend_limit, slice_plan=slice_plan)
        self.snapshots[run_id] = dict(run_id=run_id, state='COMPLETE', finished_at=iso(self.engine_clock[0]), result=result,
                                      error=None)
        return dict(run_id=run_id, state='RUNNING', engine=dict(runtime='LOCAL_MODEL'))

    def read(self, account_id, run_id):
        return None if run_id in self.lost else self.snapshots.get(run_id)

    def stop(self, account_id, run_id):
        return self.read(account_id, run_id)

    # The production tracker's readers: FINAL rows from the immutable ledger, nothing else.
    row_records = AiScreenerRuns.row_records
    row_outcomes = AiScreenerRuns.row_outcomes

    def block(self, run_id):
        return ((self.snapshots.get(run_id) or {}).get('result') or {}).get('universe_coverage') or {}

    def sent(self, run_id):
        return [r for r in coverage_ledger().records(run_id, 'batch') if r['stage'] == 'BATCH_INFERENCE']


class GlobalEpochReplayTests(AutoBase):

    def test_one_full_coverage_epoch_at_live_scale(self):
        runs = CoverageRuns(self.clock)
        a = self.auto = type(self.auto)(self.store, clock=self.clock, feed=self.feed, runs=runs)
        a.go(schedule=dict(universe_evaluation_interval_seconds=SEPARATION))
        eligible = {instrument_id(i) for i in range(SIZE)} - {instrument_id(NO_PRICE), instrument_id(UNAVAILABLE)}
        timeline, turned_at = [], {}            # instrument -> slice numbers in which it had its turn
        paused_cycles = restarted = lost_run = None

        def controller():
            return self.auto.service._controller()['universe']

        def capture():
            """Fold the controller's last finished run into the replay's own timeline, once."""
            universe = controller()
            result = universe.get('last_result') or {}
            rid = result.get('run_id')
            if not rid or any(t['run_id'] == rid for t in timeline):
                return result
            number = next(i for i, s in enumerate(runs.started, 1) if s['run_id'] == rid)
            if result['status'] == 'INTERRUPTED':
                timeline.append(dict(run_id=rid, slice=number, status='INTERRUPTED', reason=result.get('reason'), folded=False))
                return result
            records = runs.row_records(rid)
            turns = sorted(k for k, (name, reasons) in records.items()
                           if name in ('AI_EVALUATED', 'AI_REJECTED')
                           or (name == 'UNPROCESSED' and 'BATCH_FAILED:LOCAL_CONTEXT_EXCEEDED' in reasons))
            for key in turns:
                turned_at.setdefault(key, []).append(number)
            block = runs.block(rid)
            timeline.append(dict(run_id=rid, slice=number, status=result['status'], reason=result.get('reason'),
                                 adopted=result.get('adopted'), selected=result.get('selected'), epoch=result.get('epoch'),
                                 eligible=block.get('eligible_count'), turns=len(turns),
                                 requests=len(runs.sent(rid)), model_calls=block.get('model_calls'),
                                 deferred=(block.get('slice') or {}).get('deferred_count'),
                                 reasons=(block.get('counts') or {}).get('reasons'),
                                 candidate_run_id=result.get('candidate_run_id'), failure=universe.get('failure')))
            return result

        def cycle(seconds=SEPARATION):
            number = len(runs.started) + 1             # the slice this cycle would start
            runs.reader.stale = number == STALE_SLICE
            runs.engine.fail_next = number == FAIL_SLICE
            self.auto.cycle(seconds)
            return capture()

        for _ in range(80):
            if cycle().get('epoch', {}).get('epoch_completed'):
                break
            folded = sum(1 for t in timeline if t['status'] != 'INTERRUPTED')
            if folded == 8 and paused_cycles is None:
                # Pause between slices: no slice starts while paused; resuming continues the same epoch.
                epoch_before = json.loads(json.dumps(controller()['epoch']))
                self.auto.service.pause()
                count = len(runs.started)
                for _ in range(3):
                    cycle()
                paused_cycles = dict(started_while_paused=len(runs.started) - count, epoch_before=epoch_before,
                                     epoch_after=controller()['epoch'])
                self.auto.service.resume()
            if folded == 15 and restarted is None:
                # The process is lost while its next slice is running; a new process recovers the controller.
                runs.hold_next = True
                cycle()
                lost_run = controller()['active_run_id']
                epoch_before = json.loads(json.dumps(controller()['epoch']))
                runs.lost.add(lost_run)
                self.clock.value += 1500
                b = self.restart()
                resumed = b.service.resume_on_startup(threaded=False)
                cycle(60)
                restarted = dict(lost_run=lost_run, resumed=resumed, epoch_before=epoch_before,
                                 epoch_after=controller()['epoch'], interrupted=b.events('UNIVERSE_RUN_INTERRUPTED'))

        a = self.auto
        completed = a.events('UNIVERSE_EPOCH_COMPLETED')
        finished = [t for t in timeline if t['status'] != 'INTERRUPTED']
        before_completion = finished[:-1]
        last = finished[-1]

        # 1. The epoch completed, at live scale, with every eligible row's turn accounted for.
        self.assertEqual(len(completed), 1, timeline[-3:])
        self.assertEqual((completed[0]['number'], completed[0]['eligible'], completed[0]['turns']), (1, 621, 621))
        self.assertTrue(last['epoch']['epoch_completed'])
        self.assertEqual(controller()['epoch']['number'], 2)
        self.assertEqual(set(turned_at), eligible, 'an eligible row never had its turn')
        self.assertTrue(all(t['eligible'] in (620, 621) for t in finished))
        # 2. Nothing pending is lost: every row a slice deferred or left unprocessed had its turn later.
        left = {k for t in finished for k, (name, _) in runs.row_records(t['run_id']).items() if name == 'UNPROCESSED'}
        self.assertTrue(left <= set(turned_at))
        # 3. No duplicate turn before the completing slice: a row is sent again only once every row has had one.
        duplicates = {k: s for k, s in turned_at.items() if len(s) > 1}
        self.assertTrue(all(s[-1] == last['slice'] and len(s) == 2 for s in duplicates.values()), duplicates)
        # 4. Deferrals advance: while rows without a turn remain, a slice sends none that already had one.
        seen = set()
        for t in before_completion:
            sent = {i for r in runs.sent(t['run_id']) for i in r['instrument_ids']}
            self.assertFalse(sent & seen, t['slice'])
            seen |= {k for k, s in turned_at.items() if t['slice'] in s}
        # 5. A slice is a bounded workload: first-pass requests fit its 120 s deadline; every request is one row.
        cap = int(0.4 * SEPARATION / FIRST_PASS_SECONDS) + 1
        for t in finished:
            first_pass = [r for r in runs.sent(t['run_id']) if len(r['instrument_ids']) == 1]
            self.assertLessEqual(len(first_pass), cap + 1, t)
            self.assertTrue(all(len(r['instrument_ids']) == 1 for r in runs.sent(t['run_id'])))
        # 6. The size refusal is a turn, never retried in the epoch, and never model input.
        refused = turned_at[instrument_id(REFUSED)]
        self.assertTrue(len(refused) == 1 or (len(refused) == 2 and refused[-1] == last['slice']), refused)
        self.assertEqual(sum(1 for ids, kind in runs.engine.answers if kind == 'REFUSED_AT_SEND'), len(refused))
        # 7. A failed call produces no decision: that slice is not adopted, its unanswered rows are not turns,
        #    the controller backs off, and the rows are taken by a later slice.
        failed = next(t for t in finished if t['slice'] == FAIL_SLICE)
        self.assertNotIn(failed['status'], ('SLICE_SELECTION_COMPLETE', 'GLOBAL_SELECTION_COMPLETE'), failed)
        self.assertFalse(failed['adopted'])
        self.assertIsNotNone(failed['failure'])
        failed_rows = {i for r in runs.sent(failed['run_id']) if r.get('outcome') != 'COMPLETED' for i in r['instrument_ids']}
        self.assertTrue(failed_rows)
        self.assertTrue(all(min(turned_at[k]) > FAIL_SLICE for k in failed_rows))
        # 8. Selections carry provenance: each adopted slice stored its candidate run under its own run id.
        adopted = [t for t in finished if t['adopted']]
        self.assertTrue(adopted)
        for t in adopted:
            self.assertEqual(t['status'], 'SLICE_SELECTION_COMPLETE')
            self.assertEqual(t['candidate_run_id'], 'CU-' + t['run_id'])
            stored = action_repository().get('candidate_run', t['candidate_run_id'])
            self.assertEqual([p['instrument_id'] for p in stored['candidates']], t['selected'])
        no_selection = [t for t in finished if t['status'] == 'SLICE_COMPLETE_NO_SELECTION']
        self.assertTrue(no_selection)
        self.assertFalse(any(t['adopted'] for t in no_selection))
        # 9. Pause and recovery preserve progression: no slice starts while paused; the lost run is closed
        #    INTERRUPTED and not folded; the epoch is carried unchanged across the restart and continues.
        self.assertEqual(paused_cycles['started_while_paused'], 0)
        self.assertEqual(paused_cycles['epoch_after'], paused_cycles['epoch_before'])
        self.assertEqual(restarted['resumed'], dict(resumed=True, reason=None))
        self.assertEqual([e['run_id'] for e in restarted['interrupted']], [lost_run])
        self.assertEqual(restarted['epoch_after']['number'], restarted['epoch_before']['number'])
        self.assertEqual(restarted['epoch_after']['prior_turns'], restarted['epoch_before']['prior_turns'])
        self.assertNotIn(lost_run, {k for k, s in turned_at.items()})
        self.assertFalse(runs.row_records(lost_run))
        # 10. The quote limitation is an outcome of that slice only: the stale row is not eligible there and has
        #     its turn later in the same epoch.
        stale = next(t for t in finished if t['slice'] == STALE_SLICE)
        self.assertEqual(stale['eligible'], 620)
        self.assertGreater(min(turned_at[instrument_id(STALE_ONCE)]), STALE_SLICE)
        # No order exists without its own Action Decision; the replay manufactures none.
        self.assertEqual(self.automation_orders(), [])

        out = os.environ.get('IMP_GLOBAL_REPLAY_OUT')
        if out:
            Path(out).mkdir(parents=True, exist_ok=True)
            Path(out, 'full-global-replay.json').write_text(json.dumps(dict(
                label=LABEL, universe=SIZE, eligible=len(eligible), slices_started=len(runs.started),
                slices_folded=len(finished), completed_event=completed[0], next_epoch=controller()['epoch']['number'],
                pause=dict(started_while_paused=paused_cycles['started_while_paused']),
                restart=dict(lost_run=lost_run, resumed=restarted['resumed'], interrupted_events=len(restarted['interrupted'])),
                rows_with_two_turns=len(duplicates), engine_answers=dict(
                    (kind, sum(1 for _, k in runs.engine.answers if k == kind))
                    for kind in sorted({k for _, k in runs.engine.answers})),
                timeline=timeline), indent=1, default=str), encoding='utf-8')
