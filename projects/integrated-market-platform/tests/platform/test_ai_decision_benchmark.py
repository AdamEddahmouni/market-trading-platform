"""The step-5 AI decision benchmark, offline: fake providers, a temporary database, no network or model."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from market_platform_foundation.intelligence.inference.errors import InferenceErrorCode
from market_platform_foundation.intelligence.inference.paid_spend import DollarLedger
from tests.intelligence.test_action_decision import END, NOW, candidate, proposal, wire
from tools import ai_decision_benchmark as bench


def context():
    return dict(position=dict(state='FLAT', quantity=0, snapshot_at=NOW, pending=False, account_id='PAPER-1'),
                candidate_valid_until=END, opportunity=None, authority=False, allow_short=False)


def record(decision_id, *, time=NOW, instrument='US:NVDA', prompt_hash=None, latency=900):
    case = dict(candidate=candidate(), context=context(), candidate_input_hash='RUN-HASH', candidate_rank=1)
    prompt = bench.rebuild(dict(case, cutoff=NOW, selection=dict(rank=1)))['prompt_hash']
    value = dict(decision_id=decision_id, instrument_id=instrument, decision_time=time, action_state='NO_ACTION',
                 blocker_codes=[], model_proposal=None,
                 model=dict(provider_id='local.openai_compatible', model_id=bench.BASELINE_MODEL, latency_ms=latency,
                            tokens_input=100, prompt_hash=prompt_hash or prompt, prompt_version='3.0.0'),
                 evidence_snapshot=dict(cutoff=NOW, evidence=candidate(), selection=dict(rank=1), context=context(),
                                        candidate_input_hash='RUN-HASH', candidate_rank=1))
    value['input_hash'] = bench.material_hash(case, provider_id='local.openai_compatible', model_id=bench.BASELINE_MODEL,
                                              prompt_hash=prompt_hash or prompt)
    return value


class Answer(SimpleNamespace):
    def __init__(self, raw='', error=None, message=None, **extra):
        super().__init__(raw_text=raw, error_code=error, error_message=message, latency_ms=extra.get('latency', 1000),
                         tokens_input=10, tokens_output=5, diagnostics={'runtime_timings': {'predicted_per_second': 50.0}})


class ExportTests(unittest.TestCase):
    def test_export_reads_read_only_and_verifies_each_rebuild(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'state.sqlite3'
            connection = sqlite3.connect(db)
            connection.execute('CREATE TABLE action_decision_records (kind TEXT, id TEXT, instrument_id TEXT, '
                               'decision_time TEXT, payload TEXT)')
            rows = [record('AD-1'), record('AD-2', instrument='US:AMD', prompt_hash='OLD-PROMPT'),
                    record('AD-3', latency=None)]                       # never reached a model: not replayable
            for item in rows:
                connection.execute('INSERT INTO action_decision_records VALUES (?,?,?,?,?)',
                                   ('decision', item['decision_id'], item['instrument_id'], item['decision_time'],
                                    json.dumps(item)))
            connection.commit()
            connection.close()
            before = db.read_bytes()
            summary = bench.export(db, Path(folder) / 'cases.json', count=10)
            self.assertEqual(db.read_bytes(), before)                     # the database is never written
            self.assertEqual(summary, {'eligible': 2, 'selected': 2, 'input_verified': 2, 'rebuild_verified': 1})
            cases = {c['case_id']: c for c in json.loads((Path(folder) / 'cases.json').read_text())['cases']}
            self.assertFalse(cases['AD-2']['prompt_current'])             # made with an older prompt; inputs exact

    def test_selection_spreads_over_days_and_instruments(self):
        cases = [dict(case_id=f'{day}-{n}', decision_time=f'2026-10-{day}T15:00:00Z', instrument_id=f'I{n % 3}',
                      has_news=bool(n % 2)) for day in (20, 21) for n in range(6)]
        chosen = bench.select_cases(cases, 4)
        self.assertEqual(len({c['decision_time'][:10] for c in chosen}), 2)
        self.assertGreaterEqual(len({c['instrument_id'] for c in chosen}), 3)


class RunTests(unittest.TestCase):
    def case(self):
        return bench._case_from_record(record('AD-1'))

    def test_answers_are_graded_by_the_production_validator(self):
        answers = iter([Answer(wire(proposal('NO_ACTION', None))),
                        Answer(wire(dict(proposal(), rationale='Buy five hundred shares now.'))),
                        Answer('not json'),
                        Answer(error=InferenceErrorCode.PROVIDER_TIMEOUT, message='LOCAL_MODEL_TIMEOUT')])
        provider = SimpleNamespace(infer=lambda *a, **k: next(answers), last_resource_sample={})
        results, stopped = bench.run_cases([self.case()] * 4, provider, local=True)
        self.assertIsNone(stopped)
        self.assertEqual([r['outcome'] for r in results], ['ACCEPTED', 'REJECTED', 'INVALID_OUTPUT', 'PROVIDER_ERROR'])
        self.assertEqual(results[1]['reason'], 'UNSUPPORTED_EXECUTION_OR_LEVEL')
        summary = bench.summarize(results)
        self.assertEqual((summary['accepted'], summary['accepted_pct'], summary['valid_output_pct']), (1, 25.0, 50.0))

    def test_the_dollar_cap_stops_the_run_before_a_call_is_sent(self):
        ledger = DollarLedger(None, daily_micro=3_000_000, monthly_micro=3_000_000)
        calls = []

        def infer(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                return Answer(error=InferenceErrorCode.PROVIDER_RATE_LIMIT, message='PAID_AI_MONTHLY_DOLLAR_CAP')
            return Answer(wire(proposal('NO_ACTION', None)))
        results, stopped = bench.run_cases([self.case()] * 5, SimpleNamespace(infer=infer), local=False, ledger=ledger)
        self.assertEqual((stopped, len(calls), [r['outcome'] for r in results]),
                         ('PAID_AI_MONTHLY_DOLLAR_CAP', 2, ['ACCEPTED', 'NOT_SENT']))
        self.assertEqual(bench.summarize(results)['cases'], 1)

    def test_a_paid_engine_without_its_key_is_skipped_and_named(self):
        with tempfile.TemporaryDirectory() as folder:
            cases = Path(folder) / 'cases.json'
            cases.write_text(json.dumps({'cases': [self.case()]}))
            args = SimpleNamespace(cases=cases, limit=0, out=Path(folder) / 'out', engine='openai', model='gpt-6-luna',
                                   provider_env=None, ledger_dir=Path(folder) / 'ledger', total_usd=3.0)
            self.assertEqual(bench.run(args), {'skipped': True, 'reason': 'OPENAI_API_KEY_NOT_SET'})
            saved = json.loads((Path(folder) / 'out' / 'openai--gpt-6-luna.json').read_text())
            self.assertFalse(saved['key_present'])

    def test_the_paid_provider_uses_its_own_capped_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            provider, reason = bench.paid_provider('anthropic', 'claude-haiku-5-5', keys={'ANTHROPIC_API_KEY': 'k'},
                                                   ledger_dir=Path(folder), total_usd=3.0)
            self.assertIsNone(reason)
            self.assertEqual((provider.ledger.daily_micro, provider.ledger.monthly_micro), (3_000_000, 3_000_000))
            self.assertTrue(str(provider.ledger._path).startswith(folder))


def run_record(engine, model, accepted_pct, p50, p95, dollars_per_accepted=None, start_reason=None):
    return dict(engine=engine, model=model, start_reason=start_reason,
                summary=dict(accepted_pct=accepted_pct, p50_latency_ms=p50, p95_latency_ms=p95,
                             dollars_per_accepted=dollars_per_accepted))


class WinnerRuleTests(unittest.TestCase):
    def test_a_candidate_needs_five_points_and_at_most_double_the_p95(self):
        base = run_record('local', bench.BASELINE_MODEL, 60.0, 5000, 9000)
        runs = [base, run_record('local', 'better-but-slow', 80.0, 9000, 19000),
                run_record('local', 'barely-better', 64.0, 4000, 8000),
                run_record('local', 'winner', 70.0, 6000, 12000),
                run_record('local', 'did-not-start', 90.0, None, None, start_reason='LOCAL_RESOURCE_PREDICTED_VRAM_LIMIT')]
        model, notes = bench.pick_local(runs)
        self.assertEqual(model, 'winner')
        self.assertEqual(len(notes), 4)
        self.assertEqual(bench.pick_local([base, runs[2]])[0], bench.BASELINE_MODEL)

    def test_agreement_counts_only_cases_both_accepted(self):
        reference = dict(model='claude-sonnet-5-5', results=[
            dict(case_id='a', outcome='ACCEPTED', proposed_state='NO_ACTION'),
            dict(case_id='b', outcome='ACCEPTED', proposed_state='ENTER'),
            dict(case_id='c', outcome='REJECTED')])
        local = dict(model='m', results=[dict(case_id='a', outcome='ACCEPTED', proposed_state='NO_ACTION'),
                                         dict(case_id='b', outcome='ACCEPTED', proposed_state='NO_ACTION'),
                                         dict(case_id='c', outcome='ACCEPTED', proposed_state='ENTER')])
        self.assertEqual(bench.agreement(local, reference), (1, 2))
        self.assertEqual(bench.agreement_lines([reference, local]), ['- m vs claude-sonnet-5-5: 1 of 2 (50%)'])

    def test_paid_pick_is_cheapest_per_accepted_at_or_above_local(self):
        runs = [run_record('anthropic', 'claude-haiku-5-5', 70.0, 1, 1, 0.002),
                run_record('anthropic', 'claude-sonnet-5-5', 90.0, 1, 1, 0.03),
                run_record('openai', 'gpt-6-luna', 50.0, 1, 1, 0.001)]
        self.assertEqual(bench.pick_paid(runs, 65.0), 'claude-haiku-5-5')
        self.assertEqual(bench.pick_paid(runs, 80.0), 'claude-sonnet-5-5')
        self.assertEqual(bench.pick_paid(runs, 95.0), bench.DEFAULT_PAID_PICK)


if __name__ == '__main__':
    unittest.main()
