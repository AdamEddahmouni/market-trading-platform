"""Prospective evaluation API composition: read canonical authorities only."""
from __future__ import annotations

import time
import platform
import sys
from pathlib import Path
from datetime import UTC, datetime

from ..evaluation.prospective import POLICY, build_run, fingerprint, ns_of, rerun
from ..evaluation.sources import construct_records
from ..git_ref import read_git_head
from ..local_state.action_decisions import action_repository
from ..local_state.evaluations import evaluation_repository
from ..local_state.paper_experiments import paper_experiment_repository
from ..local_state.reevaluation import reevaluation_repository


class ProspectiveEvaluationService:
    def __init__(self, store, *, actions=None, experiments=None, next_sessions=None, repository=None, clock=time.time):
        self.store=store
        self.actions=actions or action_repository()
        self.experiments=experiments or paper_experiment_repository()
        self.next_sessions=next_sessions or reevaluation_repository()
        self.repository=repository or evaluation_repository()
        self.clock=clock

    @property
    def account(self):
        return self.store.paper_ledger.paper_account_id

    def now(self):
        return datetime.fromtimestamp(self.clock(),UTC).isoformat().replace('+00:00','Z')

    def project(self, *, cutoff=None, evidence_class=None):
        cutoff=cutoff or self.now()
        cut=ns_of(cutoff)
        if cut is None or cut>ns_of(self.now()):
            raise ValueError('INVALID_EVALUATION_CUTOFF')
        ledger=self.store.paper_ledger
        experiment=self.experiments.get(ledger.experiment_id) if ledger.experiment_id else None
        if not experiment or experiment['paper_account_id']!=self.account:
            raise ValueError('PAPER_EXPERIMENT_REQUIRED')
        decisions=self.actions.evaluation_decisions(self.account,cutoff)
        if len(decisions)>10000:
            raise ValueError('EVALUATION_BOUND_EXCEEDED_NARROW_SOURCE_REQUIRED')
        snapshots=[]
        for instrument in sorted({d['instrument_id'] for d in decisions}):
            rows=self.next_sessions.list_snapshots(self.account,instrument,limit=100)
            if len(rows)==100:
                raise ValueError('NEXT_SESSION_SOURCE_TRUNCATED')
            snapshots.extend(rows)
        def observations(identifier):
            values=self.next_sessions.observations(identifier,limit=100)
            if len(values)==100:
                raise ValueError('OUTCOME_SOURCE_TRUNCATED')
            return values
        before=None
        equity=[]
        while True:
            page=self.experiments.snapshots(experiment['experiment_id'],limit=100,before=before)
            equity.extend([s for s in page if int(s['captured_at_ns'])<=cut])
            if len(equity)>10000:
                raise ValueError('EVALUATION_BOUND_EXCEEDED')
            if len(page)<100:
                break
            before=page[-1]['snapshot_id']
        # No live mark refresh: current quotes cannot rewrite a historical cutoff.
        with ledger.submit_critical_section():
            trades=ledger.project_trades()
        records=construct_records(decisions=decisions,candidate_reader=lambda i:self.actions.get('candidate_run',i),
                                  trades=trades,experiment=experiment,snapshots=snapshots,observations=observations,cutoff=cut)
        cohort=evidence_class or experiment['evidence_class']
        equity=equity if cohort==experiment['evidence_class'] else []
        sources=[dict(kind='paper_experiment',id=experiment['experiment_id'],hash=fingerprint({k:v for k,v in experiment.items() if k not in ('status','ended_at_ns','closing')}),
                      fill_model_id=experiment['fill_model_id'],cost_policy_id=experiment['cost_policy_id'],risk_policy_id=experiment['risk_policy_id'])]
        sources.append(dict(kind='execution_environment',python=sys.version.split()[0],os=platform.system(),
                            timezone='America/New_York',code_sources={
                                name:fingerprint(Path(__file__).parents[1].joinpath(name).read_text(encoding='utf-8-sig'))
                                for name in ('evaluation/prospective.py','evaluation/sources.py','ui_api/prospective_evaluation.py')}))
        result=build_run(records=records,equity=equity,policy=POLICY,cutoff=cutoff,git_sha=read_git_head(),
                         evidence_class=cohort,source_refs=sources)
        result['account_id']=self.account
        result['experiment_id']=experiment['experiment_id']
        return result

    @staticmethod
    def summary(run, *, finalized=False):
        return {k:v for k,v in run.items() if k!='inputs'} | dict(finalized=finalized)

    def create(self, body):
        if set(body)-{'cutoff','evidence_class'} or not body.get('cutoff'):
            raise ValueError('INVALID_EVALUATION_REQUEST')
        if getattr(self.store,'mode',None)=='DEMO' or self.store.paper_ledger.execution_mode!='INTERNAL_SIMULATION':
            raise ValueError('EVALUATION_FINALIZE_OBSERVATIONAL_ONLY')
        run=self.project(**body)
        self.repository.put(run,self.account)
        return dict(self.summary(run,finalized=True),durability=self.repository.durability)

    def get(self, identifier):
        run=self.repository.get(identifier,self.account)
        if not run:
            raise ValueError('EVALUATION_RUN_NOT_FOUND')
        return run

    def reproduce(self, identifier):
        run=self.get(identifier)
        # The compact normalized projection is frozen. Validate original source refs
        # separately; missing original evidence cannot claim full reconstruction.
        missing=[]
        for row in run['inputs']['records']:
            if not row.get('action_decision_id'):
                continue
            decision=self.actions.get('decision',row['action_decision_id'])
            candidate=self.actions.get('candidate_run',row.get('candidate_run_id'))
            if not decision or not candidate or fingerprint(dict(decision=decision,candidate=candidate))!=row.get('source_fingerprint'):
                missing.append(row['evaluation_id'])
        # Re-read all original fills, outcomes and equity at the frozen cutoff.
        try:
            current=self.project(cutoff=run['cutoff'],evidence_class=run['evidence_class'])
            # Code SHA changes do not erase source reproducibility.
            for key in ('records','equity','source_refs'):
                if fingerprint(current['inputs'][key])!=fingerprint(run['inputs'][key]):
                    missing.append('CHANGED_'+key.upper())
        except (ValueError,KeyError,TypeError):
            missing.append('CANONICAL_SOURCE_UNAVAILABLE')
        # account/experiment fields are composition metadata, not metric inputs.
        metric_run={k:v for k,v in run.items() if k not in ('account_id','experiment_id')}
        result=rerun(metric_run)
        result['source_reconstruction']='NOT_REPRODUCIBLE' if missing else 'MATCH'
        result['missing_or_changed_sources']=missing
        return result

    def records(self, run, *, offset=0, limit=25, dimension=None, label=None):
        offset=int(offset);limit=min(max(int(limit),1),100)
        if offset<0 or dimension is not None and dimension not in POLICY['segment_dimensions']:
            raise ValueError('INVALID_EVALUATION_PAGE')
        rows=run['inputs']['records']
        if dimension and label:
            rows=[r for r in rows if (r.get('segments',{}).get(dimension) or 'UNAVAILABLE')==label]
        page=rows[offset:offset+limit]
        reasons={r['evaluation_id']:r['reason'] for r in run['excluded_records']}
        return dict(records=[dict(r,excluded_reason=reasons.get(r['evaluation_id'])) for r in page],
                    total_count=len(rows),next_offset=offset+limit if offset+limit<len(rows) else None,
                    cutoff=run['cutoff'],run_id=run['run_id'])

    def detail(self, run, identifier):
        row=next((r for r in run['inputs']['records'] if r['evaluation_id']==identifier),None)
        if not row:
            raise ValueError('EVALUATION_RECORD_NOT_FOUND')
        decision=self.actions.get('decision',row.get('action_decision_id'))
        candidate=self.actions.get('candidate_run',row.get('candidate_run_id'))
        verified=decision is not None and candidate is not None and fingerprint(dict(decision=decision,candidate=candidate))==row.get('source_fingerprint')
        return dict(record=row,decision=decision if verified else None,source_reconstruction='MATCH' if verified else 'NOT_REPRODUCIBLE',
                    lifecycle_id=row.get('trade_episode_id'),cutoff=run['cutoff'])


_SERVICE=None
_STORE=None


def evaluation_service(store):
    global _SERVICE,_STORE
    if _SERVICE is None or _STORE is not store:
        _STORE=store
        _SERVICE=ProspectiveEvaluationService(store)
    return _SERVICE
