"""Real service/HTTP integration. Fixtures validate software, never market edge."""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from market_platform_foundation.local_state.evaluations import EvaluationRepository
from market_platform_foundation.local_state.reevaluation import ReevaluationRepository
from market_platform_foundation.ui_api.prospective_evaluation import ProspectiveEvaluationService
from market_platform_foundation.ui_api.server import UiApiHandler
from tests.trading_correctness.test_trade_lifecycle import _Lifecycle,iso


class ProspectiveServiceTests(_Lifecycle):
    def evaluation(self):
        return ProspectiveEvaluationService(self.store,actions=self.repo,next_sessions=ReevaluationRepository(),
                                            repository=EvaluationRepository(),clock=self.clock)

    def test_no_action_is_admitted_without_trade_or_model_side_effects(self):
        self.decide(self.new_run('AAPL'),'NO_ACTION','AAPL')
        svc=self.evaluation();before=json.dumps(self.store.paper_ledger.events);calls=self.model.calls
        result=svc.project()
        self.assertEqual(result['metrics']['decisions'],1)
        self.assertEqual(result['metrics']['completed_trades'],0)
        self.assertEqual(json.dumps(self.store.paper_ledger.events),before)
        self.assertEqual(self.model.calls,calls)
        detail=svc.detail(result,result['included_record_ids'][0])
        self.assertEqual(detail['source_reconstruction'],'MATCH')
        self.assertEqual(detail['decision']['model_proposal']['proposal_state'],'NO_ACTION')

    def test_closed_episode_pnl_once_and_open_before_close(self):
        _,d=self.enter();self.tick(10)
        cutoff=iso(self.t)
        self.tick(10);e=self.exit();self.governed(e,price='152.00');self.tick(2)
        svc=self.evaluation();closed=svc.project();old=svc.project(cutoff=cutoff)
        self.assertEqual(closed['metrics']['completed_trades'],1,closed['admission'])
        self.assertEqual(old['metrics']['open_censored'],1)
        self.assertEqual(old['metrics']['completed_trades'],0)
        self.assertEqual(sum(bool(r.get('execution_outcome')) for r in closed['inputs']['records']),1)
        run=svc.create(dict(cutoff=iso(self.t)))
        self.assertEqual(svc.reproduce(run['run_id'])['status'],'MATCH')
        self.assertEqual(svc.reproduce(run['run_id'])['source_reconstruction'],'MATCH')

    def test_new_decision_does_not_change_frozen_run(self):
        self.decide(self.new_run('AAPL'),'NO_ACTION','AAPL')
        svc=self.evaluation();run=svc.create(dict(cutoff=iso(self.t)))
        self.tick(20);self.decide(self.new_run('AAPL'),'NO_ACTION','AAPL')
        self.assertEqual(svc.get(run['run_id'])['metrics']['decisions'],1)
        self.assertEqual(svc.project()['metrics']['decisions'],2)
        self.assertEqual(svc.reproduce(run['run_id'])['status'],'MATCH')

    def test_source_loss_reports_not_reconstructable_and_account_isolates(self):
        self.decide(self.new_run('AAPL'),'NO_ACTION','AAPL');svc=self.evaluation()
        result=svc.create(dict(cutoff=iso(self.t)))
        saved=dict(self.repo._memory);self.repo._memory.clear()
        self.assertEqual(svc.reproduce(result['run_id'])['source_reconstruction'],'NOT_REPRODUCIBLE')
        self.repo._memory=saved
        self.assertIsNone(svc.repository.get(result['run_id'],'other'))

    def test_http_current_run_page_finalize_and_rerun_no_orders(self):
        self.decide(self.new_run('AAPL'),'NO_ACTION','AAPL');svc=self.evaluation()
        import market_platform_foundation.ui_api.prospective_evaluation as module
        prior_service,prior_store=module._SERVICE,module._STORE
        module._SERVICE,module._STORE=svc,self.store
        self.addCleanup(setattr,module,'_SERVICE',prior_service);self.addCleanup(setattr,module,'_STORE',prior_store)
        class Handler(UiApiHandler):
            def _authorize_request(self,*args,**kwargs): return True
            def log_message(self,*args): pass
        Handler.store=self.store
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            def request(path,body=None):
                req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,
                                           headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=5) as response: return json.load(response)
            current=request('/evaluation/prospective/summary');self.assertEqual(current['metrics']['decisions'],1)
            page=request('/evaluation/prospective/records');self.assertEqual(page['total_count'],1)
            finalized=request('/evaluation/prospective/runs',dict(cutoff=iso(self.t)))
            fetched=request('/evaluation/prospective/runs/'+finalized['run_id'])
            self.assertEqual(fetched['input_fingerprint'],current['input_fingerprint'])
            self.assertEqual(request('/evaluation/prospective/rerun',dict(run_id=finalized['run_id']))['status'],'MATCH')
            self.assertEqual(len(self.store.paper_ledger.project_trades()),0)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_cutoff_compares_instants_and_rejects_future(self):
        from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository
        repo=ActionDecisionRepository()
        repo.put('decision','plain',dict(decision_id='plain',decision_time='2026-10-05T14:00:00Z',instrument_id='AAPL',position=dict(account_id='a')))
        self.assertEqual(len(repo.evaluation_decisions('a','2026-10-05T14:00:00.500000Z')),1)
        self.assertEqual(len(repo.evaluation_decisions('a','2026-10-05T14:00:00+00:00')),1)
        svc=self.evaluation()
        with self.assertRaisesRegex(ValueError,'INVALID_EVALUATION_CUTOFF'):
            svc.project(cutoff=iso(self.t+1))

    def test_demo_cannot_finalize(self):
        self.store.mode='DEMO'
        with self.assertRaisesRegex(ValueError,'EVALUATION_FINALIZE_OBSERVATIONAL_ONLY'):
            self.evaluation().create(dict(cutoff=iso(self.t)))
