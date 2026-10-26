"""Passive Paper performance capture. No order, model or service-start authority."""
from __future__ import annotations
import copy
import hashlib
import threading
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from ..canonical import canonical_bytes
from ..evaluation.paper_performance import POLICY_VERSION, completed_trades, milestones, session_coverage
from ..evaluation.performance_calendar import VERSION as CALENDAR_VERSION, NS, local_date, session_bounds, sessions_after, trading_day
from ..evaluation.performance_benchmark import total_return, decimal_string
from ..local_state.paper_performance import PerformanceRepository
from ..paper.ledger import PaperExecutionLedger, CURRENT_MARK_QUALITIES

def fingerprint(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def historical_ledger(source,events,cutoff_ns,marks):
    """Detached replay, with original event/mark clocks. Never opens a database."""
    selected=[]
    for event in events:
        if int(event["event_time"])>cutoff_ns:
            continue
        if event["event_type"]=="FillRecorded":
            fill=(event.get("payload") or {}).get("fill") or {}
            if int(fill.get("fill_time",0))>cutoff_ns:
                continue
        selected.append(copy.deepcopy(event))
    clone=PaperExecutionLedger(paper_account_id=source.paper_account_id,session_id=source.session_id,
        policy=copy.deepcopy(source.policy),events=selected,data_mode=source.data_mode,
        execution_mode="INTERNAL_SIMULATION",execution_authority="BLOCKED",data_provider=source.data_provider,
        execution_provider="INTERNAL")
    chosen={}
    for mark in marks:
        when=int(mark.get("mark_as_of_ns") or 0)
        iid=mark.get("instrument_id")
        if not iid or not when or when>cutoff_ns or when<cutoff_ns-60*NS:
            continue
        if mark.get("quality") not in CURRENT_MARK_QUALITIES or mark.get("mark_minor") is None:
            continue
        if iid not in chosen or when>int(chosen[iid]["mark_as_of_ns"]):
            chosen[iid]=mark
    for iid,mark in chosen.items():
        clone.apply_live_mark(mark_minor=int(mark["mark_minor"]),mark_provider=str(mark.get("provider") or "UNKNOWN"),
            mark_as_of_ns=int(mark["mark_as_of_ns"]),mark_quality=str(mark["quality"]),instrument_id=iid)
    return clone

def runtime_configuration(store):
    from ..local_state.paper_automation import paper_automation_repository
    from .screener_news import _default_synthesis_settings
    from ..intelligence.inference.prompts import PromptRegistry
    from ..intelligence.inference.synthesis_engines import local_model, resolved_engine, engine_models
    from ..local_state.external_cache import imp_cache_dir
    from ..news.config import configured_value
    from ..intelligence.inference.contracts import IntelligenceTaskType
    controller=paper_automation_repository().get_controller(store.paper_ledger.paper_account_id)
    settings=_default_synthesis_settings().current()
    prompt=PromptRegistry().get_for_task(IntelligenceTaskType.SCREENER_ACTION_DECISION)
    engine=resolved_engine(settings['engine'])
    model=settings.get('model')
    if engine=='local':
        # Canonical local selection ignores the saved model label and resolves
        # the currently configured endpoint/manifest. This starts nothing.
        model,_reason=local_model(configured_value,imp_cache_dir())
    elif engine in ('anthropic','openai','gemini'):
        offered=[item[0] for item in engine_models(engine,configured_value)]
        if engine=='anthropic' and model and model not in offered:
            model=None
        elif model not in offered:
            model=offered[0] if offered else None
    from ..git_ref import read_git_head
    return dict(git_sha=read_git_head(),automation_policy_id=(controller or {}).get("policy_id"),
        ledger_policy_id=store.paper_ledger.policy.get("risk_policy_identity_hash"),
        ai=dict(engine=engine,model=model),
        prompt_id=prompt.prompt_id,prompt_version=prompt.version,prompt_hash=prompt.content_hash,
        experiment_id=store.paper_ledger.experiment_id,data_mode=store.paper_ledger.data_mode)

class PerformanceService:
    def __init__(self,store,*,repository=None,experiment_reader=None,configuration_reader=None,clock=time.time,benchmark_reader=None):
        self.store=store
        self.repository=repository or PerformanceRepository()
        if experiment_reader is None:
            from ..local_state.paper_experiments import paper_experiment_repository
            experiment_reader=lambda identifier:paper_experiment_repository().get(identifier)
        self.experiment_reader=experiment_reader
        self.configuration_reader=configuration_reader or (lambda:runtime_configuration(store))
        self.clock=clock
        self.benchmark_reader=benchmark_reader
        self.mark_reader=None
        self.controller_reader=None
        self.lock=threading.RLock()
        self.benchmark_retry={}

    @property
    def account(self):
        return self.store.paper_ledger.paper_account_id

    def _run(self,run_id):
        return next((r for r in self.repository.runs(self.account) if r["run_id"]==run_id),None)

    def enroll(self,body):
        if not isinstance(body,dict) or set(body)!={"experiment_id"} or not isinstance(body["experiment_id"],str):
            raise ValueError("INVALID_PERFORMANCE_ENROLLMENT")
        ledger=self.store.paper_ledger
        from ..operating_modes import broker_paper_execution_env_enabled, live_execution_env_enabled
        if (getattr(self.store,"mode",None)=="DEMO" or ledger.data_mode!="LIVE_OBSERVATIONAL"
            or getattr(self.store,"data_mode",None)!="LIVE_OBSERVATIONAL"
            or ledger.execution_mode!="INTERNAL_SIMULATION" or ledger.execution_authority!="PAPER_ONLY"
            or ledger.execution_provider!="INTERNAL"
            or broker_paper_execution_env_enabled() or live_execution_env_enabled()):
            raise ValueError("PROSPECTIVE_INTERNAL_PAPER_REQUIRED")
        with self.lock,ledger.submit_critical_section():
            record=self.experiment_reader(body["experiment_id"])
            if (not record or record.get("status")!="ACTIVE" or record["experiment_id"]!=ledger.experiment_id
                or record["paper_account_id"]!=self.account or record["paper_session_id"]!=ledger.session_id
                or record.get("evidence_class")!="PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA"):
                raise ValueError("ACTIVE_PROSPECTIVE_EXPERIMENT_REQUIRED")
            if any(e["event_type"]=="FillRecorded" for e in ledger.events) or ledger.project_positions():
                raise ValueError("UNTRADED_FLAT_EXPERIMENT_REQUIRED")
            if any(r["experiment_id"]==record["experiment_id"] for r in self.repository.runs(self.account)):
                raise ValueError("EXPERIMENT_ALREADY_ENROLLED")
            now=int(self.clock()*NS)
            dates=sessions_after(local_date(now),20)
            configuration=self.configuration_reader()
            if (not configuration.get("automation_policy_id") or not configuration.get("ai",{}).get("engine")
                or not configuration.get("ai",{}).get("model")):
                raise ValueError("EVALUATION_CONFIGURATION_REQUIRED")
            run=dict(schema_version=POLICY_VERSION,run_id="PPR-"+uuid.uuid4().hex,account_id=self.account,
                experiment_id=record["experiment_id"],session_id=ledger.session_id,enrolled_at_ns=now,
                initial_capital_minor=int(record["initial_capital_minor"]),first_session=dates[0].isoformat(),
                fixed_10=dates[9].isoformat(),fixed_20=dates[19].isoformat(),configuration=configuration,
                configuration_hash=fingerprint(configuration),ledger_policy=copy.deepcopy(ledger.policy),
                calendar_version=CALENDAR_VERSION,currency="USD")
            self.repository.append(self.account,run["run_id"],"run",record["experiment_id"],run)
            self._save_events(run,copy.deepcopy(ledger.events))
            self._save_report(run,now)
            return run

    def _save_events(self,run,events):
        latest=self.repository.latest(self.account,run["run_id"],"event")
        last=int(latest["sequence"]) if latest else -1
        for event in events:
            if int(event["sequence"])>last:
                self.repository.append(self.account,run["run_id"],"event",str(event["sequence"]),event)

    def capture(self):
        with self.lock:
            ledger=self.store.paper_ledger
            runs=self.repository.runs(self.account)
            if not runs:
                return
            now=int(self.clock()*NS)
            with ledger.submit_critical_section():
                events=copy.deepcopy(ledger.events)
                valuation=copy.deepcopy(ledger.project_valuation())
                config=self.configuration_reader()
                controller=self.controller_reader() if self.controller_reader else {}
                if self.mark_reader is not None:
                    marks=valuation.get("marks",[])+self.mark_reader(ledger)
                    detached=historical_ledger(ledger,events,now,marks)
                    valuation=detached.project_valuation(as_of_ns=now)
            for run in runs:
                if ledger.experiment_id!=run["experiment_id"] or ledger.session_id!=run["session_id"]:
                    continue
                latest_report=self.repository.latest(self.account,run["run_id"],"report")
                if latest_report and latest_report.get("complete"):
                    continue
                self._save_events(run,events)
                reasons=[]
                if fingerprint(config)!=run["configuration_hash"] or ledger.policy!=run["ledger_policy"]:
                    reasons.append("CONFIGURATION_CHANGED")
                if any(e["event_type"]=="PaperSessionClosed" for e in events):
                    reasons.append("EXPERIMENT_CLOSED")
                try:
                    day=local_date(now)
                    start,end=session_bounds(day) if trading_day(day) else (0,0)
                except ValueError:
                    start=end=0
                    reasons.append("CALENDAR_UNAVAILABLE")
                if start<=now<=end+60*NS and start:
                    quality=valuation["quality"]
                    if any(not m.get("mark_as_of_ns") or now-int(m["mark_as_of_ns"])>60*NS
                           or int(m["mark_as_of_ns"])>now for m in valuation.get("marks",[])):
                        quality="DEGRADED"
                    row=dict(captured_at_ns=now,quality=quality,equity_minor=valuation["equity_minor"],
                        valuation=valuation,configuration_hash=fingerprint(config),controller_state=controller,reasons=reasons,
                        last_event_sequence=int(events[-1]["sequence"]) if events else 0)
                    self.repository.append(self.account,run["run_id"],"observation",str(now),row)
                elif reasons:
                    issue=dict(at_ns=now,reasons=reasons)
                    self.repository.append(self.account,run["run_id"],"issue",fingerprint(issue),issue)
                self._save_report(run,now)

    def request_benchmark_refresh(self,run_id):
        """Queue explicit evidence revalidation; the request performs no provider call."""
        with self.lock:
            run=self._run(run_id)
            if run is None:
                raise ValueError("PERFORMANCE_RUN_NOT_FOUND")
            now=int(self.clock()*NS)
            dates=[]
            day=date.fromisoformat(run["first_session"])
            while day<=local_date(now):
                if trading_day(day) and session_bounds(day)[1]<=now:
                    dates.append(day.isoformat())
                day+=timedelta(days=1)
            request=dict(refresh_id="PRF-"+uuid.uuid4().hex,requested_at_ns=now,dates=dates)
            self.repository.append(self.account,run_id,"refresh",request["refresh_id"],request)
            return dict(queued=True,refresh_id=request["refresh_id"],sessions=len(dates))

    def recover_benchmark(self):
        """Separate worker: one bounded day per tick; explicit corrections persist."""
        if self.benchmark_reader is None:
            return
        account=self.account
        now=int(self.clock()*NS)
        for run in self.repository.runs(account):
            if now<session_bounds(date.fromisoformat(run["first_session"]))[1]:
                continue
            evidence_rows=self.repository.rows(account,run["run_id"],"benchmark")
            existing={r["session_date"]:r for r in evidence_rows if r.get("ready")}
            done={(r["refresh_id"],r["session_date"]) for r in self.repository.rows(account,run["run_id"],"refresh_done")}
            candidates=[]
            for request in self.repository.rows(account,run["run_id"],"refresh"):
                candidates.extend((d,request["refresh_id"]) for d in request["dates"] if (request["refresh_id"],d) not in done)
            day=date.fromisoformat(run["first_session"])
            while day<=local_date(now):
                try:
                    if trading_day(day) and session_bounds(day)[1]<=now and day.isoformat() not in existing:
                        candidates.append((day.isoformat(),None))
                except ValueError:
                    break
                day+=timedelta(days=1)
            for day,refresh_id in candidates:
                key=(run["run_id"],day,refresh_id)
                if now<self.benchmark_retry.get(key,0):
                    continue
                self.benchmark_retry[key]=now+300*NS
                payload=self.benchmark_reader(day)
                evidence=dict(payload,session_date=day,retrieved_at_ns=now)
                evidence["source_hash"]=fingerprint(evidence)
                with self.lock:
                    if self.account!=account:
                        return
                    self.repository.append(account,run["run_id"],"benchmark",evidence["source_hash"],evidence)
                    if refresh_id:
                        self.repository.append(account,run["run_id"],"refresh_done",refresh_id+":"+day,
                            dict(refresh_id=refresh_id,session_date=day,ready=bool(evidence.get("ready")),at_ns=now))
                    self._save_report(run,now)
                return

    def _session_rows(self,run,now):
        account=self.account
        events=self.repository.rows(account,run["run_id"],"event")
        observations=self.repository.rows(account,run["run_id"],"observation")
        issues=self.repository.rows(account,run["run_id"],"issue")
        benchmark={r["session_date"]:r for r in self.repository.rows(account,run["run_id"],"benchmark") if r.get("ready") and r.get("adjustments_complete") is True}
        first=date.fromisoformat(run["first_session"])
        final=max(date.fromisoformat(run["fixed_20"]),local_date(now))
        source=self.store.paper_ledger
        # Use the enrollment's immutable policy even if the current account changed.
        prototype=PaperExecutionLedger(paper_account_id=run["account_id"],session_id=run["session_id"],
            policy=copy.deepcopy(run["ledger_policy"]),data_mode="LIVE_OBSERVATIONAL")
        rows=[]
        bars=[]
        actions=[]
        pending={}
        for offset in range((final-first).days+1):
            day=first+timedelta(days=offset)
            try:
                if not trading_day(day):
                    continue
                start,end=session_bounds(day)
            except ValueError:
                break
            if end>now:
                rows.append(dict(session_date=day.isoformat(),cutoff_ns=end,covered=False,equity_minor=None,
                    completed_trades=0,spy_return=None,reasons=[]))
                continue
            day_observations=[r for r in observations if start<=r["captured_at_ns"]<=end+60*NS]
            marks=[m for r in day_observations for m in r["valuation"].get("marks",[])]
            clone=historical_ledger(prototype,events,end,marks)
            valuation=clone.project_valuation(as_of_ns=end)
            trades=clone.project_trades()
            for trade in trades:
                trade["client_order_id"]=(clone.lookup_order(trade["order_id"]) or {}).get("client_order_id","")
            episodes=completed_trades(trades)
            reasons=[reason for r in day_observations for reason in r.get("reasons",[])]
            reasons.extend(reason for i in issues if i["at_ns"]<=end for reason in i["reasons"])
            if episodes["mixed"]:
                reasons.append("MANUAL_FILLS")
            opening=session_bounds(first)[0]
            if any(int(t.get("fill_time_ns") or 0)<opening for t in trades):
                reasons.append("PRESTART_FILLS")
            if valuation["quality"]!="CURRENT":
                reasons.append("CLOSING_VALUATION_UNAVAILABLE")
            data=benchmark.get(day.isoformat())
            spy=None
            if data and data.get("ready"):
                bars.append(data["bar"])
                # Preserve duplicates so the pure validator can refuse ambiguity.
                actions.extend(data.get("actions",[]))
            # Missing sessions break the total-return chain, never drop their return.
            complete=len(bars)==len(rows)+1 and all(benchmark.get(r["session_date"],{}).get("ready") for r in rows)
            if complete:
                try:
                    curve=total_return(bars,actions,actions_complete=True)
                    spy=curve[-1]["return_ratio"]
                except ValueError:
                    pass
            coverage=session_coverage(day_observations,start,end,benchmark_ready=spy is not None)
            # Dry-run the canonical fee calculator on a detached clone only.
            recorded={(e["payload"].get("instrument_id"),e["payload"].get("accrual_date"))
                      for e in clone.events if e["event_type"]=="ShortBorrowFeeAccrued"}
            for fee in clone.accrue_short_borrow_fees(accrual_date=day.isoformat(),as_of_ns=end) if valuation["quality"]=="CURRENT" else []:
                payload=fee["payload"]
                pending[(payload["instrument_id"],payload["accrual_date"])]=int(payload["fee_minor"])
            pending={k:v for k,v in pending.items() if k not in recorded}
            unposted=sum(pending.values())
            ledger_equity=valuation["equity_minor"]
            net=ledger_equity-unposted if ledger_equity is not None else None
            rows.append(dict(session_date=day.isoformat(),cutoff_ns=end,covered=coverage["covered"],
                coverage=coverage,equity_minor=net,ledger_equity_minor=ledger_equity,
                completed_trades=episodes["completed"],mixed=episodes["mixed"],spy_return=spy,
                spy_equity_minor=decimal_string(Fraction(run["initial_capital_minor"])*(1+Fraction(int(spy[0]),int(spy[1])))) if spy else None,
                costs=dict(commission_minor=valuation["total_commission_minor"],fees_minor=valuation["total_fees_minor"],
                    posted_borrow_minor=valuation.get("total_borrow_fees_minor",0),unposted_borrow_minor=unposted),
                reasons=sorted(set(reasons)),benchmark_source=data.get("source_hash") if data else None,
                observation_hash=fingerprint(day_observations),ledger_hash=fingerprint([e for e in events if int(e["event_time"])<=end])))
        return rows

    def _save_report(self,run,now):
        rows=self._session_rows(run,now)
        closed=[r for r in rows if r["cutoff_ns"]<=now]
        scorecards=milestones(initial=run["initial_capital_minor"],sessions=rows,now_ns=now)
        report=dict(schema_version=POLICY_VERSION,run_id=run["run_id"],experiment_id=run["experiment_id"],
            account_id=run["account_id"],currency="USD",initial_capital_minor=run["initial_capital_minor"],
            first_session=run["first_session"],configuration=run["configuration"],
            calendar_version=run["calendar_version"],milestones=scorecards,sessions=closed,
            fixed_sessions=len(closed),covered_sessions=sum(r["covered"] for r in closed),
            complete=scorecards["covered_20"]["status"]!="Not due",
            assumptions=["Whole selected Paper account; internal simulation.",
                         "SPY fractional shares; dividends reinvested at ex-date close; fee-free and pre-tax.",
                         "Account equity is net of posted costs and separately identified unposted borrow.",
                         "Covered-session results are supplemental; gaps and intervening returns are retained."],
            authority=dict(trading_mutation=False,live_capital=False))
        report["report_id"]="PPEVAL-"+fingerprint(report)
        latest=self.repository.latest(self.account,run["run_id"],"report")
        if latest is None or latest["report_id"]!=report["report_id"]:
            self.repository.append(self.account,run["run_id"],"report",report["report_id"],report)
        return report

    def read(self,run_id,report_id=None):
        run=self._run(run_id)
        if run is None:
            raise ValueError("PERFORMANCE_RUN_NOT_FOUND")
        if report_id:
            report=next((r for r in self.repository.rows(self.account,run_id,"report") if r["report_id"]==report_id),None)
        else:
            report=self.repository.latest(self.account,run_id,"report")
        if report is None:
            raise ValueError("PERFORMANCE_REPORT_NOT_FOUND")
        observation=self.repository.latest(self.account,run_id,"observation")
        return dict(run=run,report=report,durability=self.repository.durability,
                    last_observation_ns=observation["captured_at_ns"] if observation else None)

    def export(self,run_id,format,report_id=None):
        from ..evaluation.performance_export import export_report
        from ..platform.security.leak_audit import assert_no_secrets_in_payload
        report=self.read(run_id,report_id)["report"]
        assert_no_secrets_in_payload(report)
        return export_report(report,format)




def runtime_marks(ledger):
    """Read existing streams only; no subscriptions, refresh, persistence or gates."""
    from ..market_data.live_runtime import get_live_runtime
    from .paper_market_evidence import PaperMarketEvidence
    runtime=get_live_runtime(create=False)
    result=[]
    for position in ledger.project_positions():
        iid=str(position["instrument_id"])
        mark=None
        if position.get("instrument_kind")=="CRYPTO_PAIR":
            quote=PaperMarketEvidence().quote(iid,universe="CRYPTO",instrument=ledger.instrument_for(iid))
            if quote.get("admissible"):
                mark=dict(mark_minor=quote["last_price_minor"],mark_provider=quote["source"],
                          mark_as_of_ns=quote["as_of_time_ns"],mark_quality="CURRENT")
        elif runtime is not None:
            mark=runtime.live_mark_for(iid)
        if mark:
            result.append(dict(instrument_id=iid,mark_minor=mark["mark_minor"],
                provider=mark["mark_provider"],mark_as_of_ns=mark["mark_as_of_ns"],quality=mark["mark_quality"]))
    return result

def performance_service(store, *, initialize=False):
    """GET uses an already initialized service or a read-only empty view."""
    service=getattr(store,"_paper_performance_service",None)
    if service is not None and (not initialize or getattr(service,"_runtime_initialized",True)):
        return service
    connection=None
    if initialize:
        from ..local_state.paths import persistence_enabled
        from ..local_state.startup import open_local_state
        local=open_local_state() if persistence_enabled() else None
        connection=local.connection if local else None
    service=PerformanceService(store,repository=PerformanceRepository(connection))
    service._runtime_initialized=initialize
    if initialize:
        service.mark_reader=runtime_marks
        from ..local_state.paper_automation import paper_automation_repository
        def controller_state():
            value=paper_automation_repository().get_controller(store.paper_ledger.paper_account_id) or {}
            return {key:value.get(key) for key in ("desired_state","last_status","run","policy_id","heartbeat_at","emergency")}
        service.controller_reader=controller_state
        from ..market_data.live_config import moomoo_host,moomoo_port
        from tools.moomoo.opend_quote_transport import fetch_spy_performance_day
        service.benchmark_reader=lambda day:fetch_spy_performance_day(day,host=moomoo_host(),port=moomoo_port())
    store._paper_performance_service=service
    return service

def start_performance_observer(store):
    """Called only by the separately authorized platform launcher."""
    if store.data_mode!="LIVE_OBSERVATIONAL" or getattr(store,"mode",None)=="DEMO":
        return None
    try:
        service=performance_service(store,initialize=True)
        observer=PerformanceObserver(service)
        observer.start()
        store._paper_performance_observer=observer
        return observer
    except Exception:  # reporting storage failure cannot stop the platform
        return None


class PerformanceObserver:
    def __init__(self,service):
        self.service=service
        self.stop_event=threading.Event()
        self.threads=[]
        self.last_error=None

    def tick(self):
        try:
            self.service.capture()
            self.last_error=None
        except Exception as exc:  # observer failure cannot escape into trading
            self.last_error=type(exc).__name__

    def _loop(self,benchmark=False):
        while not self.stop_event.is_set():
            started=time.monotonic()
            if benchmark:
                try:
                    self.service.recover_benchmark()
                except Exception as exc:
                    self.last_error=type(exc).__name__
            else:
                self.tick()
            self.stop_event.wait(max(0,60-(time.monotonic()-started)))

    def start(self):
        for benchmark in (False,True):
            thread=threading.Thread(target=self._loop,args=(benchmark,),name="paper-performance-"+("benchmark" if benchmark else "capture"),daemon=True)
            self.threads.append(thread)
            thread.start()

    def stop(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=5)
