"""OCT1-11 metric/admission regression tests. SOFTWARE_CONTROLLED only."""
import copy
import unittest

from market_platform_foundation.evaluation.prospective import POLICY, build_run, rerun


def record(i=0, pnl=100, **changes):
    row = dict(evaluation_id=f'e{i}', schema_version='decision-outcome/1.0.0', account_id='a', experiment_id='x',
               currency='USD', instrument_id='AAPL', action_decision_id=f'd{i}', candidate_run_id='c',
               evidence_snapshot_id='s', source_fingerprint='f', decision_time='2026-10-05T14:00:00Z',
               decision_cutoff='2026-10-05T14:00:00Z', evidence_max_time='2026-10-05T13:59:00Z',
               evidence_available_time='2026-10-05T13:59:01Z', evidence_class='SOFTWARE_CONTROLLED',
               quality='COMPLETE', action_state='ENTER', direction='LONG', origin='AI_PROPOSAL_SERVER_GATED',
               model=dict(provider_id='p', model_id='m', model_version='1', prompt_version='1'),
               segments=dict(setup='one', asset='EQUITY', regime='UNAVAILABLE', model='p/m/1', prompt='1', direction='LONG'),
               trade_episode_id=f't{i}', execution_outcome=dict(state='CLOSED', net_pnl_minor=pnl,
               gross_pnl_minor=pnl+10, costs_minor=10, commission_minor=6, fees_minor=4,
               entry_time='2026-10-05T14:01:00Z', exit_time=f'2026-10-05T15:0{i}:00Z',
               executed_notional_minor=20000, entry_fill_ids=[f'in{i}'], exit_fill_ids=[f'out{i}']),
               signal_outcomes=[], limitations=[])
    row.update(changes)
    return row


def run(rows, equity=(), cohort='SOFTWARE_CONTROLLED'):
    return build_run(records=rows, equity=list(equity), policy=POLICY, cutoff='2026-10-16T20:00:00Z',
                     git_sha='a'*40, evidence_class=cohort, source_refs=[])


class ProspectiveMetricsTests(unittest.TestCase):
    def test_expectancy_and_costs(self):
        m=run([record(i,p) for i,p in enumerate([100,-50,50,-100])])['metrics']
        self.assertEqual(m['expectancy_minor'],'0')
        self.assertEqual(m['net_pnl_minor'],0)
        self.assertEqual(m['gross_pnl_minor'],40)
        self.assertEqual(m['costs_minor'],40)
        self.assertEqual(m['win_rate'],'0.5')
        self.assertEqual(m['completed_trades'],4)

    def test_profit_factor_and_edge_cases(self):
        self.assertEqual(run([record(0,300),record(1,-150)])['metrics']['profit_factor'],'2')
        self.assertIsNone(run([record()])['metrics']['profit_factor'])
        self.assertEqual(run([record(0,-100)])['metrics']['profit_factor'],'0')
        self.assertIsNone(run([])['metrics']['expectancy_minor'])
        self.assertIsNone(run([])['metrics']['win_rate'])

    def test_flat_and_open(self):
        r=record(1); r['execution_outcome']['state']='OPEN'
        m=run([record(0,0),r])['metrics']
        self.assertEqual((m['completed_trades'],m['flat'],m['open_censored']),(1,1,1))
        self.assertIsNone(m['win_rate'])

    def test_drawdown_uses_observed_equity(self):
        curve=[dict(snapshot_id=i,captured_at_ns=1791205200000000000+i*3600000000000,
                    equity_minor=p,quality='CURRENT') for i,p in enumerate([100000,101000,100400,100200,102000])]
        dd=run([],curve)['portfolio_metrics']['drawdown']
        self.assertEqual(dd['amount_minor'],800)
        self.assertEqual(dd['duration_seconds'], '10800')
        self.assertIsNotNone(dd['recovered_at'])
        self.assertIsNone(run([])['portfolio_metrics']['drawdown'])

    def test_streak_order_is_close_time(self):
        rows=[record(i,p) for i,p in enumerate([-1,-2,0,-3,-4,-5])]
        m=run(list(reversed(rows)))['metrics']
        self.assertEqual((m['longest_losing_streak'],m['current_losing_streak']),(3,3))

    def test_primary_prospective_excludes_fixture_replay_controlled_manual(self):
        rows=[record(0,evidence_class='FIXTURE'),record(1,evidence_class='HISTORICAL_REPLAY'),record(2),
              record(3,evidence_class='PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA',origin='MANUAL_UNLINKED')]
        r=run(rows,cohort='PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA')
        self.assertEqual(r['admission']['admitted'],0)
        self.assertEqual(r['admission']['excluded'],4)
        self.assertEqual(r['metrics']['completed_trades'],0)

    def test_future_and_equal_outcome_rejected(self):
        a=record(0,evidence_max_time='2026-10-05T14:00:01Z')
        b=record(1); b['execution_outcome']['entry_time']=b['decision_cutoff']
        r=run([a,b]); self.assertEqual(r['admission']['excluded'],2)

    def test_missing_clocks_and_currency_rejected(self):
        r=run([record(0,decision_cutoff=None),record(1,currency='EUR')])
        self.assertEqual(r['admission']['excluded'],2)

    def test_duplicate_episode_never_double_counts(self):
        r=run([record(0),record(1,trade_episode_id='t0')]); self.assertEqual(r['metrics']['completed_trades'],1)
        self.assertEqual(r['admission']['excluded'],1)

    def test_no_action_signal_is_not_pnl(self):
        a=record(action_state='NO_ACTION',trade_episode_id=None,execution_outcome=None)
        a['signal_outcomes']=[dict(state='COMPLETE',horizon='next-session',source_time='2026-10-06T14:00:00Z',
                                  observed_at='2026-10-06T14:00:01Z',market_return='0.02',directional_return=None)]
        r=run([a]); self.assertEqual(r['metrics']['signal_outcomes'],1)
        self.assertEqual(r['metrics']['completed_trades'],0)
        self.assertIsNone(r['metrics']['net_pnl_minor'])

    def test_segments_and_missing_regime(self):
        b=record(1);b['segments']['model']='p/m/2';b['segments']['prompt']='2'
        r=run([record(),b]);self.assertEqual(len(r['segments']['model']),2)
        self.assertEqual(r['segments']['regime'][0]['label'],'UNAVAILABLE')
        self.assertEqual(r['segments']['regime'][0]['metrics']['decisions'],2)

    def test_rerun_is_frozen_and_tampering_detected(self):
        rows=[record()]; r=run(rows);rows[0]['execution_outcome']['net_pnl_minor']=999
        self.assertEqual(rerun(r)['status'],'MATCH')
        broken=copy.deepcopy(r);broken['metrics']['net_pnl_minor']=888
        self.assertEqual(rerun(broken)['status'],'DIFFERENT')

    def test_fingerprint_input_order_independent(self):
        a,b=record(0),record(1)
        self.assertEqual(run([a,b])['input_fingerprint'],run([b,a])['input_fingerprint'])

    def test_weekly_closing_time_and_turnover(self):
        a=record();a['execution_outcome']['exit_time']='2026-10-12T01:00:00Z' # Sunday ET
        r=run([a]);self.assertEqual(r['weekly'][0]['week'],'2026-10-05')
        self.assertEqual(r['metrics']['executed_notional_minor'],20000)

    def test_paper_only_read_only_result(self):
        r=run([record()]);self.assertFalse(r['authority']['live_capital'])
        self.assertFalse(r['authority']['trading_mutation'])
        self.assertEqual(r['conclusion'],'INSUFFICIENT_EVIDENCE')
