"""PF-01 supervisor uses disposable SQLite and synthetic owned processes."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from market_platform_foundation.local_state.connection import LocalStateConnection

class Process:
    def __init__(self): self.exit = None; self.stopped = False
    def poll(self): return self.exit
    def stop(self): self.stopped = True; self.exit = 0

class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'imp-state.sqlite3'
        self.db = LocalStateConnection(self.path); self.addCleanup(self.db.close)
        self.now = 1000.; self.children=[]
        self.env={'IMP_PF01_SUPERVISION_ENABLED':'1','IMP_NEWS_COLLECTION_ENABLED':'1',
                  'IMP_PERSIST_STATE':'1','IMP_STATE_DIR':str(self.path.parent)}
    def spawn(self):
        child=Process(); self.children.append(child); return child
    def supervisor(self):
        from market_platform_foundation.news.supervision import CollectionSupervisor
        owner=CollectionSupervisor(self.db,spawn=self.spawn,env=self.env,clock=lambda:self.now)
        self.addCleanup(owner.stop); return owner
    def test_default_off_never_spawns(self):
        self.env['IMP_PF01_SUPERVISION_ENABLED']='0'
        owner=self.supervisor(); owner.tick()
        self.assertEqual(self.children,[]); self.assertEqual(owner.status()['state'],'DISABLED')
    def test_duplicate_owner_refused_and_browser_not_required(self):
        owner=self.supervisor(); owner.tick(); owner.tick()
        self.assertEqual(len(self.children),1)
        with self.assertRaisesRegex(ValueError,'OWNER_ACTIVE'): self.supervisor()
    def test_crashes_have_persistent_bounded_restart_budget(self):
        owner=self.supervisor(); owner.tick()
        for index in range(3):
            self.children[-1].exit=1; owner.tick()
            if index<2:
                owner.tick(); self.assertEqual(len(self.children),index+1)
                self.now+=60; owner.tick(); self.now+=61; owner.tick()
        self.assertEqual(owner.status()['state'],'BLOCKED')
        self.assertEqual(owner.status()['reason'],'RESTART_LIMIT_EXCEEDED')
        exits=[e for e in owner.status()['events'] if e['reason']=='CHILD_PROCESS_EXIT_GAP_UNVERIFIED']
        self.assertEqual([e.get('exit_code') for e in exits],[1,1,1])
        owner.stop(); restarted=self.supervisor(); restarted.tick()
        self.assertEqual(len(self.children),3)
        self.assertEqual(restarted.status()['crashes'],3)
    def test_missing_storage_stops_child_and_never_recreates_path(self):
        owner=self.supervisor(); owner.tick()
        with patch.object(Path,'stat',side_effect=FileNotFoundError): owner.tick()
        self.assertTrue(self.children[-1].stopped)
        self.assertEqual(owner.status()['reason'],'STORAGE_UNAVAILABLE')
    def test_disabled_configuration_stops_owned_child(self):
        owner=self.supervisor(); owner.tick(); self.env['IMP_NEWS_COLLECTION_ENABLED']='0'; owner.tick()
        self.assertTrue(self.children[-1].stopped)
    def test_trading_gates_refuse_spawn(self):
        self.env['IMP_PAPER_EXECUTION']='1'
        owner=self.supervisor(); owner.tick()
        self.assertEqual(self.children,[]); self.assertEqual(owner.status()['reason'],'EXECUTION_GATE_ENABLED')
    def test_expired_lease_cannot_resume_after_sleep(self):
        owner=self.supervisor(); owner.tick(); self.now+=300; owner.tick()
        self.assertTrue(self.children[-1].stopped)
        self.assertEqual(owner.status()['reason'],'OWNERSHIP_LOST')
    def test_abrupt_parent_restart_records_gap_and_waits_for_child_lease(self):
        owner=self.supervisor(); owner.tick(); self.now+=121
        replacement=self.supervisor(); replacement.tick()
        self.assertEqual(len(self.children),1)
        self.now+=60; replacement.tick(); self.now+=61; replacement.tick()
        self.assertEqual(len(self.children),2)
        self.assertIn('UNCLEAN_SUPERVISOR_RESTART',[e['reason'] for e in replacement.status()['events']])
        owner.tick(); self.assertTrue(self.children[0].stopped)
    def test_evidence_failure_stops_process_before_unrecorded_restart(self):
        owner=self.supervisor(); owner.tick()
        with patch.object(self.db,'execute',side_effect=OSError('secret value')): owner.tick()
        self.assertTrue(self.children[-1].stopped)
        self.assertNotIn('secret',json.dumps(owner.status()))

    def test_supervision_projection_marks_expired_lease_stale(self):
        from market_platform_foundation.news.supervision import supervision_status
        owner=self.supervisor(); owner.tick()
        status=supervision_status(self.env,clock=lambda:self.now)
        self.assertEqual(status['state'],'RUNNING')
        self.now+=121
        self.assertEqual(supervision_status(self.env,clock=lambda:self.now)['state'],'STALE')

    def test_supervisor_storage_guard_stops_child(self):
        owner=self.supervisor(); owner.tick()
        with patch.object(owner,'_storage_ok',return_value=False): owner.tick()
        self.assertTrue(self.children[-1].stopped)
        self.assertEqual(owner.status()['reason'],'STORAGE_UNAVAILABLE')

class HeadlessTests(unittest.TestCase):
    def test_headless_lifecycle_never_loads_store_or_recovers_paper(self):
        from tools.ui1 import run_ui_api
        from market_platform_foundation.news import collection
        from market_platform_foundation.market_data import persistence
        from market_platform_foundation.news import supervision
        stop=threading.Event(); stop.set()
        env={'IMP_NEWS_COLLECTION_ENABLED':'1','IMP_STATE_DIR':'synthetic','IMP_PERSIST_STATE':'1'}
        with patch.dict('os.environ',env,clear=True), patch.object(collection,'validate_collection_storage'), \
             patch.object(supervision,'require_current_schema'), \
             patch.object(collection,'start_collection',return_value=object()) as news, \
             patch.object(collection,'stop_collection'), \
             patch.object(persistence,'start_persistence',return_value=None), \
             patch.object(run_ui_api,'_load_store',side_effect=AssertionError('store invoked')), \
             patch.object(run_ui_api,'resume_paper_automation',side_effect=AssertionError('Paper invoked')), \
             patch.object(run_ui_api,'start_screener_warmup',side_effect=AssertionError('warmup invoked')):
            run_ui_api.collect_only(stop)
        news.assert_called_once_with('LIVE_OBSERVATIONAL')
