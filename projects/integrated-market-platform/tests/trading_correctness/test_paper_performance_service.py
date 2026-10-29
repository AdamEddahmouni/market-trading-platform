"""Temporary-store integration of step 8, no services or providers."""
import copy
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.paper_performance import PerformanceRepository
from market_platform_foundation.ui_api.paper_performance import PerformanceService, PerformanceObserver, historical_ledger
from market_platform_foundation.evaluation.performance_calendar import session_bounds, NS
from tests.trading_correctness.test_paper_experiment_accounting import _experiment_ledger, _Orders, _mark
from market_platform_foundation.paper.experiment import build_experiment_record
from market_platform_foundation.intelligence.inference.action_decision import PROMPT_ID

class PerformanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.now=session_bounds(date(2026,10,26))[1]
        self.ledger=_experiment_ledger()
        self.ledger.data_mode="LIVE_OBSERVATIONAL"
        for row in self.ledger.events:
            row["event_time"]=self.now-NS
        self.store=SimpleNamespace(mode="PAPER",data_mode="LIVE_OBSERVATIONAL",paper_ledger=self.ledger)
        self.record=build_experiment_record(experiment_id=self.ledger.experiment_id,name="test",created_at_ns=self.now-NS,
            paper_account_id=self.ledger.paper_account_id,paper_session_id=self.ledger.session_id,policy=self.ledger.policy,
            data_mode="LIVE_OBSERVATIONAL",data_providers=["MOOMOO"],execution_provider="INTERNAL",
            execution_authority="PAPER_ONLY",source_scope="test")
        self.record["status"]="ACTIVE"
        self.repo=PerformanceRepository()
        self.config={"automation_policy_id":"policy-1","ai":{"engine":"LOCAL","model":"fixture"}}
        self.service=PerformanceService(self.store,repository=self.repo,experiment_reader=lambda _:self.record,
            configuration_reader=lambda:copy.deepcopy(self.config),clock=lambda:self.now/NS,benchmark_reader=None)

    def enroll(self):
        return self.service.enroll({"experiment_id":self.record["experiment_id"]})

    def test_enroll_read_is_pure_and_account_scoped(self):
        run=self.enroll()
        self.assertEqual(run["first_session"],"2026-10-27")
        before=copy.deepcopy(self.repo.rows(self.ledger.paper_account_id,run["run_id"]))
        report=self.service.read(run["run_id"])
        self.assertEqual(report["report"]["milestones"]["fixed_10"]["status"],"Not due")
        self.service.export(run["run_id"],"html",report["report"]["report_id"])
        self.service.export(run["run_id"],"csv",report["report"]["report_id"])
        self.assertEqual(self.repo.rows(self.ledger.paper_account_id,run["run_id"]),before)
        other=PerformanceService(SimpleNamespace(paper_ledger=SimpleNamespace(paper_account_id="other")),repository=self.repo)
        with self.assertRaisesRegex(ValueError,"RUN_NOT_FOUND"):
            other.read(run["run_id"])

    def test_enrollment_rejects_replay_wrong_authority_positions_and_duplicate(self):
        self.enroll()
        with self.assertRaisesRegex(ValueError,"ALREADY_ENROLLED"):
            self.enroll()
        self.repo=PerformanceRepository()
        self.service.repository=self.repo
        for field,value in (("data_mode","HISTORICAL_CAPTURE"),("execution_authority","BLOCKED")):
            old=getattr(self.ledger,field);setattr(self.ledger,field,value)
            with self.assertRaises(ValueError): self.enroll()
            setattr(self.ledger,field,old)
        _Orders(self.ledger).submit("AAPL","BUY",1,"10")
        with self.assertRaisesRegex(ValueError,"UNTRADED"):
            self.enroll()

    def test_capture_without_browser_records_config_change_and_downtime(self):
        run=self.enroll()
        start,end=session_bounds(date(2026,10,27))
        self.now=start
        self.service.capture()
        self.now=start+300*NS
        self.config["ai"]["model"]="changed"
        self.service.capture()
        self.now=end+NS
        self.service.capture()
        report=self.service.read(run["run_id"])["report"]
        self.assertIn("CONFIGURATION_CHANGED",report["sessions"][0]["reasons"])
        self.assertFalse(report["sessions"][0]["covered"])
        self.assertTrue(report["sessions"][0]["coverage"]["gaps"])

    def test_report_revisions_are_immutable(self):
        run=self.enroll()
        first=self.service.read(run["run_id"])["report"]
        self.now=session_bounds(date(2026,10,27))[1]+NS
        self.service.capture()
        second=self.service.read(run["run_id"])["report"]
        self.assertNotEqual(first["report_id"],second["report_id"])
        self.assertEqual(self.service.read(run["run_id"],first["report_id"])["report"],first)

    def test_historical_projection_has_no_current_or_future_fills(self):
        initial=copy.deepcopy(self.ledger.events)
        _Orders(self.ledger).submit("AAPL","BUY",2,"10")
        for row in self.ledger.events[len(initial):]:
            row["event_time"]=self.now+100*NS
        clone=historical_ledger(self.ledger,self.ledger.events,self.now,[])
        self.assertEqual(clone.project_positions(),[])
        self.assertIsNone(clone.persist_sink)
        self.assertEqual(len(self.ledger.events)>len(clone.events),True)

    def test_observer_failure_does_not_escape_or_trade(self):
        failing=SimpleNamespace(capture=lambda:(_ for _ in ()).throw(RuntimeError("fixture")))
        observer=PerformanceObserver(failing)
        observer.tick()
        self.assertEqual(observer.last_error,"RuntimeError")


    def seed_session(self,run,day,*,complete=True):
        start,end=session_bounds(day)
        for at in range(start,end+1,120*NS):
            self.repo.append(self.service.account,run["run_id"],"observation",str(at),
                dict(captured_at_ns=at,quality="CURRENT",equity_minor=10000000,
                     valuation=dict(marks=[]),reasons=[]))
        if complete:
            evidence=dict(session_date=day.isoformat(),ready=True,bar=dict(date=day.isoformat(),open="100",close="100"),
                          actions=[],adjustments_complete=True,source_hash="fixture-"+day.isoformat())
            self.repo.append(self.service.account,run["run_id"],"benchmark",day.isoformat(),evidence)

    def test_full_twenty_sessions_completed_roundtrips_costs_and_frozen_exports(self):
        from market_platform_foundation.evaluation.performance_calendar import sessions_after
        run=self.enroll()
        start,_=session_bounds(date(2026,10,27))
        orders=_Orders(self.ledger)
        previous=len(self.ledger.events)
        for i in range(30):
            orders.submit("AAPL","BUY",10,"10",key=f"PAI-buy-{i}")
            orders.submit("AAPL","SELL",10,"12",key=f"PAI-sell-{i}")
        for event in self.ledger.events[previous:]:
            event["event_time"]=start+3600*NS
            if event["event_type"]=="FillRecorded":
                event["payload"]["fill"]["fill_time"]=start+3600*NS
        self.service._save_events(run,copy.deepcopy(self.ledger.events))
        days=sessions_after(date(2026,10,26),20)
        for day in days: self.seed_session(run,day)
        self.now=session_bounds(days[-1])[1]+2*NS
        self.service.capture()
        report=self.service.read(run["run_id"])["report"]
        self.assertEqual(report["milestones"]["fixed_20"]["status"],"Pass")
        self.assertEqual(report["milestones"]["covered_20"]["status"],"Pass")
        last=report["sessions"][-1]
        self.assertEqual(last["completed_trades"],30)
        self.assertEqual(last["ledger_equity_minor"],self.ledger.project_valuation()["equity_minor"])
        self.assertEqual(last["costs"]["commission_minor"],self.ledger.project_valuation()["total_commission_minor"])
        mime,html=self.service.export(run["run_id"],"html",report["report_id"])
        self.assertIn(report["report_id"],html)
        self.assertIn("Pass",html)
        self.assertIn(str(last["equity_minor"]),self.service.export(run["run_id"],"csv",report["report_id"])[1])

    def test_missing_first_benchmark_never_drops_its_return(self):
        from market_platform_foundation.evaluation.performance_calendar import sessions_after
        run=self.enroll()
        days=sessions_after(date(2026,10,26),2)
        self.seed_session(run,days[0],complete=False)
        self.seed_session(run,days[1])
        self.now=session_bounds(days[-1])[1]+2*NS
        self.service.capture()
        report=self.service.read(run["run_id"])["report"]
        self.assertIsNone(report["sessions"][1]["spy_return"])
        self.assertEqual(report["covered_sessions"],0)

    def test_runtime_configuration_uses_registry_and_resolves_local_model(self):
        from unittest.mock import patch
        from market_platform_foundation.ui_api.paper_performance import runtime_configuration
        with patch("market_platform_foundation.ui_api.screener_news._default_synthesis_settings") as settings, \
             patch("market_platform_foundation.local_state.paper_automation.paper_automation_repository") as repo, \
             patch("market_platform_foundation.intelligence.inference.synthesis_engines.local_model",return_value=("fixture-local",None)):
            settings.return_value.current.return_value=dict(engine="auto",model=None)
            repo.return_value.get_controller.return_value=dict(policy_id="policy-1")
            config=runtime_configuration(self.store)
        self.assertEqual(config["ai"]["model"],"fixture-local")
        self.assertEqual(config["prompt_id"],PROMPT_ID)


    def test_route_policy_and_dispatch_without_opening_server(self):
        import io,json
        from market_platform_foundation.platform.security.route_policy import policy_for_route,AccountScopeKind
        from market_platform_foundation.ui_api.server import UiApiHandler
        base="/evaluation/paper-performance/runs"
        self.assertEqual(policy_for_route("POST",base).capability,"state.write")
        self.assertEqual(policy_for_route("GET",base+"/x/export").capability,"audit.read")
        self.assertEqual(policy_for_route("POST",base).account_scope,AccountScopeKind.PAPER_LEDGER)
        self.store._paper_performance_service=self.service
        class Handler(UiApiHandler):
            def _authorize_request(self,*a,**k): return True
            def _send_json(self,payload,**kwargs): self.payload=payload
            def _send_error_json(self,code,message,**kwargs): self.payload=dict(error=code,message=message)
            def send_response(self,status): self.status=status
            def send_header(self,*args): pass
            def end_headers(self): pass
        handler=object.__new__(Handler);handler.store=self.store
        body=json.dumps({"experiment_id":self.record["experiment_id"]}).encode()
        handler.path=base;handler.headers={"Content-Length":str(len(body))};handler.rfile=io.BytesIO(body)
        handler.do_POST()
        self.assertIn("run_id",handler.payload)
        run_id=handler.payload["run_id"]
        handler.path=base+"/"+run_id
        handler.do_GET()
        report=handler.payload["report"]
        handler.path=base+"/"+run_id+"/export?format=html&report_id="+report["report_id"]
        handler.wfile=io.BytesIO();handler.do_GET()
        self.assertIn(report["report_id"].encode(),handler.wfile.getvalue())
        self.assertEqual(len(self.ledger.project_trades()),0)


    def test_observer_uses_cached_marks_without_changing_trading_ledger(self):
        run=self.enroll()
        start,end=session_bounds(date(2026,10,27))
        previous=len(self.ledger.events)
        _Orders(self.ledger).submit("AAPL","BUY",2,"10",key="PAI-BUY")
        for event in self.ledger.events[previous:]:
            event["event_time"]=start+NS
            if event["event_type"]=="FillRecorded":
                event["payload"]["fill"]["fill_time"]=start+NS
        _mark(self.ledger,"AAPL",700,as_of=start)
        self.now=start+60*NS
        self.service.mark_reader=lambda ledger:[dict(instrument_id="AAPL",mark_minor=1100,provider="FIXTURE",
            mark_as_of_ns=self.now,quality="CURRENT")]
        before=copy.deepcopy(self.ledger.mark_for("AAPL"))
        self.service.capture()
        observation=self.repo.latest(self.service.account,run["run_id"],"observation")
        self.assertEqual(observation["valuation"]["marks"][0]["mark_minor"],1100)
        self.assertEqual(self.ledger.mark_for("AAPL"),before)

    def test_unposted_borrow_is_identified_without_charging_real_ledger(self):
        from market_platform_foundation.paper.experiment import build_experiment_policy
        from tests.trading_correctness.test_paper_short_selling import FLAT_DAY
        self.ledger.policy=build_experiment_policy(allow_short=True)
        self.record["risk_policy"]=self.ledger.policy
        run=self.enroll()
        start,end=session_bounds(date(2026,10,27))
        previous=len(self.ledger.events)
        _Orders(self.ledger).submit("AAPL","SELL",10,"10",key="PAI-SHORT",short_sale_facts=FLAT_DAY)
        for event in self.ledger.events[previous:]:
            event["event_time"]=start+NS
            if event["event_type"]=="FillRecorded":
                event["payload"]["fill"]["fill_time"]=start+NS
        _mark(self.ledger,"AAPL",1000,as_of=end)
        self.now=end
        self.service.capture()
        report=self.service.read(run["run_id"])["report"]
        row=report["sessions"][0]
        self.assertEqual(row["costs"]["unposted_borrow_minor"],1)
        self.assertEqual(row["ledger_equity_minor"]-row["equity_minor"],1)
        self.assertFalse(any(e["event_type"]=="ShortBorrowFeeAccrued" for e in self.ledger.events))


    def test_enrollment_refuses_an_unresolved_model(self):
        self.config["ai"]["model"]=None
        with self.assertRaisesRegex(ValueError,"CONFIGURATION_REQUIRED"):
            self.enroll()

    def test_benchmark_recovery_revises_report_without_repairing_observation_gaps(self):
        run=self.enroll()
        start,end=session_bounds(date(2026,10,27))
        self.now=end+NS
        self.service.capture()
        first=self.service.read(run["run_id"])["report"]
        self.service.benchmark_reader=lambda day:dict(ready=True,bar=dict(date=day,open="100",close="110"),
            actions=[],adjustments_complete=True,source="FIXTURE",raw={})
        self.service.recover_benchmark()
        second=self.service.read(run["run_id"])["report"]
        self.assertNotEqual(first["report_id"],second["report_id"])
        self.assertIsNotNone(second["sessions"][0]["spy_return"])
        self.assertFalse(second["sessions"][0]["covered"])
        self.assertEqual(self.service.read(run["run_id"],first["report_id"])["report"],first)

    def test_later_benchmark_corrections_keep_old_revision(self):
        run=self.enroll()
        day=date(2026,10,27)
        self.seed_session(run,day)
        self.now=session_bounds(day)[1]+NS
        self.service.capture()
        first=self.service.read(run["run_id"])["report"]
        self.service.request_benchmark_refresh(run["run_id"])
        self.service.benchmark_reader=lambda day:dict(ready=True,bar=dict(date=day,open="100",close="110"),
            actions=[],adjustments_complete=True,source="FIXTURE",raw={})
        self.service.recover_benchmark()
        second=self.service.read(run["run_id"])["report"]
        self.assertNotEqual(first["report_id"],second["report_id"])
        self.assertEqual(self.service.read(run["run_id"],first["report_id"])["report"],first)


    def test_same_date_duplicate_actions_remain_unavailable(self):
        run=self.enroll();day=date(2026,10,27)
        self.seed_session(run,day)
        self.repo.append(self.service.account,run["run_id"],"benchmark","ambiguous",
            dict(session_date=day.isoformat(),ready=True,adjustments_complete=True,
                 bar=dict(date=day.isoformat(),open="100",close="100"),
                 actions=[dict(date=day.isoformat(),cash_dividend="1"),dict(date=day.isoformat(),cash_dividend="2")],
                 source_hash="ambiguous"))
        self.now=session_bounds(day)[1]+NS
        self.service.capture()
        report=self.service.read(run["run_id"])["report"]
        self.assertFalse(report["sessions"][0]["covered"])
        self.assertIsNone(report["sessions"][0]["spy_return"])

    def test_configuration_resolves_actual_local_and_paid_default(self):
        from unittest.mock import patch
        from market_platform_foundation.ui_api.paper_performance import runtime_configuration
        with patch("market_platform_foundation.ui_api.screener_news._default_synthesis_settings") as settings, \
             patch("market_platform_foundation.local_state.paper_automation.paper_automation_repository") as repo, \
             patch("market_platform_foundation.intelligence.inference.synthesis_engines.local_model",return_value=("actual-new-model",None)) as local, \
             patch("market_platform_foundation.intelligence.inference.synthesis_engines.engine_models",return_value=[("configured-paid-default",None)]):
            settings.return_value.current.return_value=dict(engine="local",model="saved-old-model")
            repo.return_value.get_controller.return_value=dict(policy_id="policy-1")
            self.assertEqual(runtime_configuration(self.store)["ai"]["model"],"actual-new-model")
            local.assert_called_once()
            settings.return_value.current.return_value=dict(engine="anthropic",model=None)
            self.assertEqual(runtime_configuration(self.store)["ai"]["model"],"configured-paid-default")


    def test_paid_default_binding_without_provider_or_inference(self):
        from unittest.mock import patch
        from market_platform_foundation.ui_api.paper_performance import runtime_configuration
        with patch("market_platform_foundation.ui_api.screener_news._default_synthesis_settings") as settings, \
             patch("market_platform_foundation.local_state.paper_automation.paper_automation_repository") as repo, \
             patch("market_platform_foundation.intelligence.inference.synthesis_engines.engine_models",return_value=[("configured-paid-default",None)]):
            settings.return_value.current.return_value=dict(engine="anthropic",model=None)
            repo.return_value.get_controller.return_value=dict(policy_id="policy-1")
            self.assertEqual(runtime_configuration(self.store)["ai"]["model"],"configured-paid-default")

    def test_sqlite_reopen_and_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fixture.sqlite3"
            with LocalStateConnection(path) as conn:
                repo=PerformanceRepository(conn)
                repo.append("account","run","observation","1",{"equity_minor":100})
                repo.append("account","run","observation","1",{"equity_minor":100})
                with self.assertRaisesRegex(ValueError,"IMMUTABLE"):
                    repo.append("account","run","observation","1",{"equity_minor":101})
            with LocalStateConnection(path) as conn:
                rows=PerformanceRepository(conn).rows("account","run","observation")
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]["equity_minor"],100)
