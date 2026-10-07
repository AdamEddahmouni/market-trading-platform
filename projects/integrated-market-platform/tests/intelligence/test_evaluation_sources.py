"""Canonical adapters, account isolation, persistence and source reconstruction."""
import copy
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.evaluation.sources import construct_records
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.evaluations import EvaluationRepository
from market_platform_foundation.platform.security.route_policy import policy_for_route
from tests.intelligence.test_prospective_evaluation import record,run

T0=1791208800000000000


def decision(i='d', state='ENTER'):
    return dict(decision_id=i,instrument_id='AAPL',instrument=dict(symbol='AAPL',universe='US_EQUITIES'),
                decision_time='2026-10-05T14:00:00Z',position=dict(account_id='a',state='FLAT'),action_state=state,
                evidence_snapshot_id='s',evidence_snapshot=dict(cutoff='2026-10-05T14:00:00Z',candidate_run_id='c',candidate_input_hash='c',
                evidence=dict(instrument=dict(asset_class='EQUITY'),current_market_evidence=[dict(as_of='2026-10-05T13:59:00Z',
                source='provider',delivery_mode='REALTIME')],reference_evidence=[])),
                model=dict(provider_id='p',model_id='m',simulated=False,prompt_version='1'),model_proposal=dict(proposal_state=state),direction='LONG')


def trade(seq,effect,before,after,decision_id='d',pnl=0):
    return dict(fill_id=f'f{seq}',sequence=seq,instrument_id='AAPL',symbol='AAPL',position_effect=effect,
                position_before=before,position_after=after,decision_id=decision_id,fill_price_minor=10000,
                filled_quantity=abs(after-before),realized_pnl_delta_minor=pnl,costs_minor=5,commission_minor=3,fees_minor=2,
                fill_time_ns=T0+seq*60_000_000_000,submit_time_ns=T0,simulator_version='v')


class EvaluationSourceTests(unittest.TestCase):
    def records(self,ds,ts,cut=T0+3600_000_000_000,**kw):
        from market_platform_foundation.intelligence.inference.hashing import input_hash_from_dict
        for d in ds:
            d['evidence_snapshot_id']='AS-'+input_hash_from_dict(d['evidence_snapshot'])
        return construct_records(decisions=ds,candidate_reader=lambda _:dict(run_id='c',input_hash='c'),trades=ts,
                                 experiment=dict(paper_account_id='a',experiment_id='x',currency='USD',data_mode='LIVE_OBSERVATIONAL',
                                                 evidence_class='PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA'),
                                 snapshots=kw.get('snapshots',[]),observations=kw.get('observations',lambda _:[]),cutoff=cut)

    def test_episode_pnl_attached_once_and_later_close_censored_at_cutoff(self):
        d,e=decision(),decision('exit','EXIT')
        ts=[trade(1,'OPEN',0,1,pnl=-5),trade(2,'CLOSE',1,0,'exit',105)]
        rows=self.records([d,e],ts)
        self.assertEqual(sum(bool(r['execution_outcome']) for r in rows),1)
        self.assertEqual(rows[0]['execution_outcome']['net_pnl_minor'],100)
        self.assertEqual(rows[0]['execution_outcome']['gross_pnl_minor'],110)
        self.assertEqual(self.records([d],ts,cut=T0+90_000_000_000)[0]['execution_outcome']['state'],'OPEN')

    def test_fixtures_dominate_live_experiment_label(self):
        d=decision();d['evidence_snapshot']['evidence']['current_market_evidence'][0]['delivery_mode']='FIXTURE'
        self.assertEqual(self.records([d],[])[0]['evidence_class'],'SOFTWARE_CONTROLLED')

    def test_future_receive_rejected(self):
        d=decision();d['evidence_snapshot']['evidence']['current_market_evidence'][0]['received_at']='2026-10-05T14:00:01Z'
        r=run(self.records([d],[]),cohort='PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA')
        self.assertEqual(r['admission']['reasons'],{'FUTURE_DECISION_INPUT':1})

    def test_manual_and_missing_close_decision_not_ai(self):
        rows=self.records([], [trade(1,'OPEN',0,1,None)])
        self.assertEqual(rows[0]['origin'],'MANUAL_UNLINKED')
        rows=self.records([decision()],[trade(1,'OPEN',0,1),trade(2,'CLOSE',1,0,None,105)])
        self.assertFalse(rows[0]['execution_outcome']['lineage_valid'])

    def test_only_frozen_regime_model_labels(self):
        row=self.records([decision()],[])[0]
        self.assertEqual(row['segments']['regime'],'UNAVAILABLE')
        self.assertEqual(row['segments']['model'],'p/m/UNAVAILABLE')
        self.assertEqual(row['segments']['asset'],'EQUITY')

    def test_snapshot_horizon_and_short_direction(self):
        d=decision('d','NO_ACTION');d['direction']='SHORT'
        snap=dict(snapshot_id='ns',lock_state='LOCKED',locked_at='2026-10-05T14:01:00Z',action_decision_id='d',
                  evidence_snapshot_ref='AS-'+__import__('market_platform_foundation.intelligence.inference.hashing',fromlist=['input_hash_from_dict']).input_hash_from_dict(d['evidence_snapshot']),reference_price=100,evaluation_policy=dict(policy_id='frozen',
                  observation_start='2026-10-06T13:30:00Z',observation_end='2026-10-06T14:00:00Z'))
        from market_platform_foundation.ui_api.screener_next_session import content_hash
        snap['content_hash']=content_hash(snap)
        obs=dict(observation_id='o',source_time='2026-10-06T13:59:00Z',observed_at='2026-10-06T13:59:01Z',
                 price=90,source='provider',delivery_mode='REALTIME')
        row=self.records([d],[],cut=T0+86400_000_000_000,snapshots=[snap],observations=lambda _:[obs])[0]
        self.assertEqual(row['signal_outcomes'][0]['directional_return'],'0.1')
        early=self.records([d],[],snapshots=[snap],observations=lambda _:[obs])[0]
        self.assertEqual(early['signal_outcomes'],[])


class EvaluationPersistenceTests(unittest.TestCase):
    def test_sqlite_restart_immutability_and_account_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            connection=LocalStateConnection(Path(directory)/'local.sqlite3')
            repo=EvaluationRepository(connection)
            value=run([record()]);repo.put(value,'a');repo.put(value,'a')
            mutated=copy.deepcopy(value);mutated['metrics']['net_pnl_minor']=999
            with self.assertRaisesRegex(ValueError,'IMMUTABLE'):
                repo.put(mutated,'a')
            self.assertIsNone(repo.get(value['run_id'],'b'))
            self.assertEqual(len(repo.list('a')),1)
            connection.close()
            connection=LocalStateConnection(Path(directory)/'local.sqlite3')
            self.assertEqual(EvaluationRepository(connection).get(value['run_id'],'a'),value)
            connection.close()

    def test_routes_never_order_capability(self):
        for method,path in [('GET','/evaluation/prospective/summary'),('POST','/evaluation/prospective/runs'),
                            ('POST','/evaluation/prospective/rerun')]:
            self.assertNotIn('order',policy_for_route(method,path).capability)
