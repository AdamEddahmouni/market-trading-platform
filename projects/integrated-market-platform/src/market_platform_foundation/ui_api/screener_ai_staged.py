"""Local-first experimental orchestration. Exhaustive operational records are never written."""
from __future__ import annotations
import copy
import time
from collections import Counter
from datetime import UTC, datetime

from ..intelligence.inference.coverage_plan import ELIGIBLE, INELIGIBLE, UNSUPPORTED, chunks, fair_order
from ..intelligence.inference.evidence_compaction import semantic_hash
from ..intelligence.inference.inference_identity import provider_identity
from ..intelligence.inference.local_qualification import (
    METHOD, METHOD_VERSION, SUPPORTED, LocalQualifier, current, evidence_hash,
)
from ..intelligence.inference.run_progress import report_stage
from ..local_state.staged_screener import staged_stores
from .screener_ai_coverage import ScreenerAiCoverage, _Run, _iso, _software_sha
from .screener_ai_universe import enumerate_universe, UniverseEnumerationError

SCHEMA="screener-ai-staged-result/1.0.0"

def local_provider(model_id=None):
    from ..intelligence.inference.local_provider import registered_local_provider
    from ..intelligence.inference.local_runtime import verify_identity_reason
    from ..local_state.external_cache import imp_cache_dir
    try:
        provider=registered_local_provider(imp_cache_dir(), model_id)
    except ValueError:
        return None
    manifest=getattr(getattr(provider,"_server",None),"manifest",None)
    if verify_identity_reason(manifest): return None
    return provider

def local_status(model_id=None):
    from ..intelligence.inference.local_runtime import readiness, apply_profile
    from ..intelligence.inference.local_models import model_manifest, DEFAULT_MODEL_ID
    from ..local_state.external_cache import imp_cache_dir
    server=getattr(local_provider(model_id),"_server",None)
    manifest=getattr(server,'manifest',None) or model_manifest(imp_cache_dir(), model_id)
    if manifest and server is None:
        try:manifest=apply_profile(manifest,manifest.execution_profile)
        except ValueError:pass  # readiness reports the invalid persisted profile
    status = readiness(manifest,process=getattr(server,'_process',None))
    return {**status, 'selected_model_id': model_id or DEFAULT_MODEL_ID}

class _PoolReader:
    def __init__(self,rows,envelope,refresh):
        self.rows,self.envelope,self.refresh=rows,envelope,refresh
    def read(self,**kwargs):
        offset,limit=kwargs["offset"],kwargs["limit"]
        current_rows={r["instrument"]["instrument_id"]:r for r in self.refresh()}
        try:
            rows=[current_rows[r["instrument"]["instrument_id"]] for r in self.rows]
        except KeyError as exc:
            raise ValueError("STAGED_POOL_MEMBERSHIP_CHANGED") from exc
        return {**self.envelope,"rows":rows[offset:offset+limit],"result_count":len(self.rows),
                "offset":offset,"limit":limit,"result_set_id":self.envelope["result_set_id"]}

class _PinnedReducer:
    def __init__(self,reducer,expected,clock,identity_check=lambda:True,should_stop=lambda:False,refresh=lambda c:c):
        self.reducer,self.expected,self.clock=reducer,expected,clock
        self.identity_check,self.should_stop,self.refresh=identity_check,should_stop,refresh
    def __getattr__(self,name):
        return getattr(self.reducer,name)
    def _verify(self,candidates,*,before_dispatch=True):
        if before_dispatch and self.should_stop(): raise ValueError("STOPPED_BY_OPERATOR")
        if not self.identity_check(): raise ValueError("PREMIUM_CONFIGURATION_CHANGED")
        now=_iso(self.clock())
        for c in candidates:
            key=c["instrument"]["instrument_id"]
            if key not in self.expected or evidence_hash(c)!=evidence_hash(self.expected[key]):
                raise ValueError("STAGED_EVIDENCE_CHANGED")
            if not current(c,now):
                raise ValueError("STAGED_EVIDENCE_EXPIRED")
    def estimate(self,scope,candidates,now):
        self._verify(candidates)
        return self.reducer.estimate(scope,candidates,now)
    def preflight(self,scope,candidates,now):
        self._verify(candidates)
        return self.reducer.preflight(scope,candidates,now)
    def reduce(self,scope,candidates,now,**kwargs):
        self._verify(candidates)
        result=self.reducer.reduce(scope,candidates,now,**kwargs)
        try:
            if result.get('provider_id')!=getattr(self.reducer.provider,'provider_id',None) or result.get('model_id')!=getattr(self.reducer.provider,'model_id',None):
                raise ValueError('PREMIUM_RESPONSE_IDENTITY_MISMATCH')
            self._verify(self.refresh(candidates),before_dispatch=False)
        except ValueError as exc:
            # Keep returned usage and raw outcome in a rejected completed receipt.
            result={**result,'state':'INVALID_OUTPUT','reason':str(exc),'candidates':[], 'validation':{**(result.get('validation') or {}),'staged_revalidation':str(exc)}}
        return result

class _PoolService:
    def __init__(self,source,rows,envelope,expected,scope,pinned_identity,should_stop,query):
        self.source,self._clock,self.expected,self.scope=source,source._clock,expected,scope
        self._reader=_PoolReader(rows,envelope,lambda:enumerate_universe(source._reader,query).rows)
        self.identity=pinned_identity
        self.reducer=_PinnedReducer(source._provider_reducer(),expected,self._clock,
            identity_check=lambda:provider_identity(source._provider_reducer().provider)==pinned_identity,
            should_stop=should_stop,refresh=self._refresh)
        self.news={}
    def _query(self,body):
        return self.source._query(body)
    def _scope(self,query,page):
        return {**self.scope,"experimental_method":METHOD_VERSION,"premium_pool_hash":semantic_hash(sorted(self.expected))}
    def _provider_reducer(self):
        if provider_identity(self.source._provider_reducer().provider)!=self.identity:
            raise ValueError("PREMIUM_CONFIGURATION_CHANGED")
        return self.reducer
    def _news_for(self,universe,rows,*,refresh):
        self.news=self.source._news_for(universe,rows,refresh=refresh)
        return self.news
    def _market(self,*args,**kwargs):
        return self.source._market(*args,**kwargs)
    def _refresh(self,candidates):
        from .screener_news_evidence import attach_news,fit_news
        keys=[c["instrument"]["instrument_id"] for c in candidates]
        page=self._reader.read(offset=0,limit=len(self.expected))
        by_id={r["instrument"]["instrument_id"]:r for r in page["rows"]}
        raw=[by_id[k] for k in keys]
        news=self.source._news_for(self.scope["universe"],raw,refresh=False)
        market,_=self.source._market(self.scope["universe"],raw,acquire=True)
        now=_iso(self._clock())
        fresh,_=self.source._candidates(self.scope["universe"],page,raw,market=market,now=now,include_flow=True)
        for c in fresh:
            key=c["instrument"]["instrument_id"]
            if key in news:attach_news(c,news[key],now=now)
            fit_news(self.scope,[c],news,now=now)
        return fresh
    def _candidates(self,universe,envelope,rows,*,market,now,include_flow):
        from .screener_news_evidence import attach_news, fit_news
        candidates,projected=self.source._candidates(universe,envelope,rows,market=market,now=now,include_flow=include_flow)
        for c in candidates:
            key=c["instrument"]["instrument_id"]
            # Classification refreshes only one news row; fetch each actual request's members.
            news=self.source._news_for(universe,[r for r in rows if r["instrument"]["instrument_id"]==key],refresh=False)
            if key in news: attach_news(c,news[key],now=now)
            fit_news(self.scope,[c],news,now=now)
        self.reducer._verify(candidates)
        return candidates,projected

class _PremiumCoverage(ScreenerAiCoverage):
    def _terminal(self,run,status,reason=None,*,final=None):
        # Reuse planning, quotas, strict inference and tournament behavior without publishing a candidate_run.
        self._release(run)
        block=self._block(run,status,reason)
        complete=bool(block["selection_complete"])
        result={**(final or {}),"schema_version":"screener-ai-screener/1.0.0",
                "run_id":run.run_id,"universe_coverage":block,"scope":run.scope,
                "candidates":(final or {}).get("candidates",[]) if complete else [],
                "evidence":(final or {}).get("evidence",[]),"state":"CURRENT" if complete else "INCOMPLETE",
                "reason":reason or status,"provider_id":self.identity.get("provider_id"),
                "model_id":self.identity.get("model_id"),"runtime":self.identity.get("runtime"),
                "valid_until":(final or {}).get("valid_until",_iso(self.service._clock())),
                "input_hash":(final or {}).get("input_hash",semantic_hash({"run_id":run.run_id,"status":status})),
                "decision_cutoff":(final or {}).get("decision_cutoff",run.cutoffs["classification"]),
                "generated_at":_iso(self.service._clock())}
        self._record_rows(run,"FINAL")
        self.ledger().append(run.run_id,"terminal",{"account_id":run.account_id,"status":status,"reason":reason,
            "finished_at":_iso(self.service._clock()),"candidate_run_id":None,"selected":[],
            "universe_coverage":block,"method":METHOD,"parent_run_id":self.parent_run_id})
        run.terminal=result
        return result

class ScreenerAiStaged:
    def __init__(self,service,*,local=None,ledger=None,repository=None,cache=None):
        self.service=service
        self._injected_local = local is not None
        self._cache = cache
        self.local=local if local is not None else local_provider()
        default_ledger,default_repo=staged_stores() if ledger is None or repository is None else (None,None)
        self.ledger,self.repository=ledger or default_ledger,repository or default_repo
        if cache is None and getattr(self.local,"runtime",None)=="LOCAL_MODEL":
            from ..local_state.screener_inference_cache import inference_cache
            cache=inference_cache()
        self.qualifier=LocalQualifier(self.local,clock=service._clock,cache=cache)

    def run(self,body,*,run_id,account_id,should_stop=lambda:False):
        query=self.service._query(body)
        if query.get("method")!=METHOD: raise ValueError("EXPLICIT_STAGED_METHOD_REQUIRED")
        if not self._injected_local:
            self.local = local_provider(query.get('local_model_id'))
            cache = self._cache
            if cache is None and self.local is not None:
                from ..local_state.screener_inference_cache import inference_cache
                cache = inference_cache()
            self.qualifier = LocalQualifier(self.local, clock=self.service._clock, cache=cache)
        start=_iso(self.service._clock())
        self.run_id,self.account_id,self.query=run_id,account_id,query
        self.states,self.assessments,self.expected={},{},{}
        self.enumeration={"complete":False}
        self.scope=self.service._scope(query,{"result_set_id":query["result_set"]})
        self.eligible=0
        self.premium_identity=provider_identity(self.service._provider_reducer().provider)
        self.premium=None
        self.plan=None
        self.ledger.append(run_id,"run",{"account_id":account_id,"method":METHOD,"method_version":METHOD_VERSION,
            "software_sha":_software_sha(),"started_at":start,"query":query,"local_model":provider_identity(self.local),
            "operationally_approved":False,"premium_model":self.premium_identity})
        try:
            report_stage("ENUMERATION")
            try:
                universe=enumerate_universe(self.service._reader,query)
            except UniverseEnumerationError as exc:
                return self._terminal("UNIVERSE_ENUMERATION_FAILED",exc.code)
            self.universe=universe
            self.enumeration={"complete":True,"result_set":universe.result_set,"query_id":universe.query_id,"pages":universe.pages}
            self.scope={**self.service._scope(query,universe.envelope),"method":METHOD}
            self.states={r["instrument"]["instrument_id"]:"ELIGIBILITY_PENDING" for r in universe.rows}
            # Use the exact existing deterministic classifier, then retain classification separately.
            helper=ScreenerAiCoverage(self.service,ledger=self.ledger)
            classified=_Run(run_id,account_id)
            classified.universe,classified.scope,classified.query=query["universe"],self.scope,query
            classified.envelope=universe.envelope
            classified.rows={r["instrument"]["instrument_id"]:r for r in universe.rows}
            classified.order=list(classified.rows)
            report_stage("ELIGIBILITY",universe_count=len(self.states))
            candidates=helper._classify(classified)
            self.classifications=copy.deepcopy(classified.classes)
            for key,(name,_) in classified.classes.items():
                self.states[key]="LOCAL_PENDING" if name==ELIGIBLE else "DETERMINISTICALLY_INELIGIBLE" if name in (INELIGIBLE,UNSUPPORTED) else "EVIDENCE_BLOCKED"
            eligible=[k for k in self.states if self.states[k]=="LOCAL_PENDING"]
            self.eligible=len(eligible)
            if query["universe"] not in SUPPORTED:
                for k in eligible: self.states[k]="METHOD_UNSUPPORTED"
                return self._terminal("METHOD_UNSUPPORTED_UNIVERSE")
            if classified.provider_reason and not eligible:
                return self._terminal("EVIDENCE_PROVIDER_UNAVAILABLE",classified.provider_reason)
            for index,key in enumerate(fair_order(str(universe.result_set),eligible)):
                if should_stop(): return self._terminal("STOPPED","STOPPED_BY_OPERATOR")
                # Freeze the fully admitted per-instrument input before inference.
                raw=[classified.rows[key]]
                news=self.service._news_for(query["universe"],raw,refresh=True)
                market,reason=self.service._market(query["universe"],raw,acquire=True)
                now=_iso(self.service._clock())
                members,_=self.service._candidates(query["universe"],universe.envelope,raw,market=market,now=now,include_flow=True)
                from .screener_news_evidence import attach_news, fit_news
                c=members[0]
                if key in news: attach_news(c,news[key],now=now)
                fit_news(self.scope,[c],news,now=now)
                self.expected[key]=copy.deepcopy(c)
                digest,canonical,_=self.qualifier.input(self.scope,c,now)
                call_id="LOCAL:"+str(index)
                self.ledger.append(run_id,"manifest",{"call_id":call_id,"semantic_hash":digest,"canonical":canonical})
                self.ledger.append(run_id,"batch_started",{"call_id":call_id,"stage":"LOCAL_ASSESSMENT",
                    "instrument_ids":[key],"planned_tokens":0,"request_started_at":now})
                report_stage("LOCAL_ASSESSMENT",local_assessed=len(self.assessments),eligible_count=self.eligible)
                if should_stop():
                    self.ledger.append(run_id,"batch",{"call_id":call_id,"stage":"LOCAL_ASSESSMENT",
                        "instrument_ids":[key],"outcome":"NOT_SENT","reason":"STOPPED_BY_OPERATOR"})
                    return self._terminal("STOPPED","STOPPED_BY_OPERATOR")
                assessment=self.qualifier.assess(self.scope,c,now,should_stop=should_stop)
                self.assessments[key]=assessment
                self.ledger.append(run_id,"batch",{"call_id":call_id,"stage":"LOCAL_ASSESSMENT",
                    "instrument_ids":[key],"assessment":assessment,"outcome":"COMPLETED" if assessment["valid"] else "FAILED"})
                self.states[key]="NOT_ADVANCED_BY_STAGED_METHOD" if assessment["valid"] and assessment["category"]=="NO_SUPPORTED_CASE" else "PREMIUM_PENDING"
            if should_stop(): return self._terminal("STOPPED","STOPPED_BY_OPERATOR")
            pool=[k for k in eligible if self.states[k]=="PREMIUM_PENDING"]
            exclusion_failure=self._revalidate_exclusions(include_pool=True)
            if exclusion_failure:
                return self._terminal(exclusion_failure,exclusion_failure)
            if not pool:
                return self._terminal("STAGED_SELECTION_COMPLETE")
            if provider_identity(self.service._provider_reducer().provider)!=self.premium_identity:
                return self._terminal("PREMIUM_CONFIGURATION_CHANGED")
            provider=self.service._provider_reducer().provider
            # Fixtures are an injected engineering control, never a production routing fallback.
            if provider is None or getattr(provider,"runtime",None) not in ("PAID_API","FIXTURE"):
                return self._terminal("PREMIUM_PROVIDER_UNAVAILABLE","PREMIUM_HOSTED_PROVIDER_REQUIRED")
            envelope={**universe.envelope,"result_set_id":str(universe.result_set)+"|"+METHOD_VERSION}
            service=_PoolService(self.service,[classified.rows[k] for k in pool],envelope,
                                 {k:self.expected[k] for k in pool},self.scope,self.premium_identity,should_stop,
                                 {**query,'result_set':universe.result_set})
            premium=_PremiumCoverage(service,ledger=self.ledger)
            premium.parent_run_id=run_id
            self.premium=premium.run({**query,"result_set":None},run_id=run_id+"-premium",
                                     account_id=account_id,should_stop=should_stop)
            block=self.premium["universe_coverage"]
            self.plan=block.get("plan")
            premium_rows=self.ledger.records(run_id+"-premium","rows")
            final_rows=[r for part in premium_rows if part["phase"]=="FINAL" for r in part["rows"]]
            for key,name,reasons in final_rows:
                self.states[key]="PREMIUM_EVALUATED" if name=="AI_EVALUATED" else "PREMIUM_BLOCKED"
            selected={p["instrument_id"] for p in self.premium["candidates"]}
            for key in selected: self.states[key]="FINAL_STAGED_SELECTION"
            status="STAGED_SELECTION_COMPLETE" if block["selection_complete"] else block["status"]
            if any(not a["valid"] for a in self.assessments.values()) and status=="STAGED_SELECTION_COMPLETE":
                status="LOCAL_ASSESSMENT_INCOMPLETE"
            return self._terminal(status,block.get("reason"))
        except Exception as exc:
            return self._terminal("STAGED_INCOMPLETE",str(exc) if isinstance(exc,ValueError) else "STAGED_RUN_FAILED:"+type(exc).__name__)

    def _revalidate_exclusions(self,*,include_pool=False):
        from .screener_news_evidence import attach_news, fit_news
        keys=[k for k,state in self.states.items() if k in self.expected and (include_pool or state=="NOT_ADVANCED_BY_STAGED_METHOD")]
        if not keys:
            return None
        refreshed=enumerate_universe(self.service._reader,{**self.query,"result_set":self.universe.result_set})
        by_id={r["instrument"]["instrument_id"]:r for r in refreshed.rows}
        raw=[by_id[k] for k in keys]
        news=self.service._news_for(self.query["universe"],raw,refresh=False)
        market,_=self.service._market(self.query["universe"],raw,acquire=True)
        now=_iso(self.service._clock())
        candidates,_=self.service._candidates(self.query["universe"],refreshed.envelope,raw,market=market,now=now,include_flow=True)
        for key,c in zip(keys,candidates):
            if key in news: attach_news(c,news[key],now=now)
            fit_news(self.scope,[c],news,now=now)
            checked_at=_iso(self.service._clock())
            if not current(self.expected[key],checked_at) or not current(c,checked_at):
                return "STAGED_EVIDENCE_EXPIRED"
            if evidence_hash(c)!=evidence_hash(self.expected[key]):
                return "STAGED_EVIDENCE_CHANGED"
        now=_iso(self.service._clock())
        if any(not current(self.expected[k],now) for k in keys): return "STAGED_EVIDENCE_EXPIRED"
        digest=semantic_hash([evidence_hash(self.expected[k]) for k in keys])
        for part,group in enumerate(chunks(keys,500)):
            self.ledger.append(self.run_id,"manifest",{"call_id":"QUALIFICATIONS_REVALIDATED:"+str(part),
                "validated_at":now,"instrument_ids":group,"evidence_hash":digest})
        return None

    def _terminal(self,status,reason=None):
        now=_iso(self.service._clock())
        if status=="STAGED_SELECTION_COMPLETE":
            exclusion_failure=self._revalidate_exclusions(include_pool=True)
            if exclusion_failure: status,reason=exclusion_failure,exclusion_failure
        now=_iso(self.service._clock())
        if status=="STAGED_SELECTION_COMPLETE" and self.premium:
            from ..market_data.freshness_contract import timestamp
            if timestamp(self.premium["valid_until"])<=timestamp(now) or any(not current(c,now) for c in self.premium.get("evidence",[])):
                status,reason="STAGED_EVIDENCE_EXPIRED","STAGED_EVIDENCE_EXPIRED"
        if status!="STAGED_SELECTION_COMPLETE":
            for key,state in self.states.items():
                if state=="FINAL_STAGED_SELECTION": self.states[key]="PREMIUM_EVALUATED"
        counts=Counter(self.states.values())
        valid=[a for a in self.assessments.values() if a["valid"]]
        invalid=len(self.assessments)-len(valid)
        counters={"universe_total":len(self.states),"deterministically_eligible":self.eligible,
            "evidence_blocked":counts["EVIDENCE_BLOCKED"],"local_assessed":len(valid),"local_invalid":invalid,
            "locally_qualified":sum(a["category"]=="WARRANTS_REVIEW" for a in valid),
            "locally_unresolved":invalid+sum(a["category"]=="UNCERTAIN" for a in valid),
            "advanced_to_premium":sum(a["category"]!="NO_SUPPORTED_CASE" or not a["valid"] for a in self.assessments.values()),
            "not_advanced_by_staged_method":counts["NOT_ADVANCED_BY_STAGED_METHOD"],
            "premium_evaluated":counts["PREMIUM_EVALUATED"]+counts["FINAL_STAGED_SELECTION"],
            "premium_blocked":counts["PREMIUM_BLOCKED"],
            "premium_failed":len({key for record in self.ledger.records(self.run_id+"-premium","batch") if record.get("outcome") in ("FAILED","UNKNOWN_PROVIDER_OUTCOME") for key in record.get("instrument_ids",[])}),
            "global_finalists":(self.premium or {}).get("universe_coverage",{}).get("finalist_count",0),
            "final_selected":counts["FINAL_STAGED_SELECTION"]}
        complete=status=="STAGED_SELECTION_COMPLETE"
        picks=(self.premium or {}).get("candidates",[]) if complete else []
        staged={"schema_version":"ai-screener-staged-accounting/1.0.0","method_version":METHOD_VERSION,
            "approval_status":"UNAPPROVED","status":status,"reason":reason,"enumeration":self.enumeration,
            "primary_states":dict(counts),"counters":counters,"counters_basis":"DERIVED_OVERLAPPING",
            "reconciled":bool(self.enumeration["complete"]) and sum(counts.values())==len(self.states),
            "local_coverage_complete":len(valid)==self.eligible and not invalid,
            "selection_complete":complete,"premium_plan":self.plan,
            "local_model":provider_identity(self.local),
            "premium_model":self.premium_identity,
            "premium_coverage":(self.premium or {}).get("universe_coverage"),
            "supported_universes":sorted(SUPPORTED),"premium_coverage_is_subset":True}
        result={**(self.premium or {}),"schema_version":SCHEMA,"run_id":"LF-"+self.run_id,"method":METHOD,
            "operationally_approved":False,"staged":staged,"scope":self.scope,
            "max_intake":50,"result_set":self.scope.get("result_set"),"cache":"MISS",
            "simulated":getattr(self.local,"runtime",None)=="FIXTURE",
            "prompt_id":"screener.local_qualification.v1","prompt_version":"1.0.0",
            "prompt_hash":semantic_hash({"method":METHOD_VERSION}),"coverage":{},
            "state":"CURRENT" if complete and picks else "NO_GROUNDED_CANDIDATES" if complete else "INCOMPLETE",
            "reason":status,"candidates":picks,"evidence":(self.premium or {}).get("evidence",[]) if complete else [],
            "generated_at":now,"valid_until":(self.premium or {}).get("valid_until",now),
            "decision_cutoff":(self.premium or {}).get("decision_cutoff",now),
            "input_hash":semantic_hash({"method":METHOD_VERSION,"assessments":[a["input_hash"] for a in self.assessments.values()]}),
            "matched_count":len(self.states),"intake_count":len(self.assessments),"packet_bytes":0,
            "provider_id":getattr(self.service._provider_reducer().provider,"provider_id",None),
            "model_id":getattr(self.service._provider_reducer().provider,"model_id",None),"runtime":"EXPERIMENTAL",
            "limitations":["Staged subset selection; methodology unapproved; no Action Decision or Paper/Live authority."]}
        result.pop("universe_coverage",None)
        # Bound records and retain per-instrument lineage even on partial or stopped runs.
        for index,group in enumerate(chunks(list(self.states),500)):
            self.ledger.append(self.run_id,"rows",{"phase":"FINAL","part":index,
                "rows":[[k,self.states[k],[]] for k in group],"classifications":{k:self.classifications[k] for k in group} if hasattr(self,"classifications") else {}})
        terminal={"account_id":self.account_id,"method":METHOD,"status":status,"reason":reason,"finished_at":now,
                  "experimental_result_id":result["run_id"],"candidate_run_id":None,"staged":staged,"scope":self.scope}
        self.repository.finalize(self.ledger,self.run_id,result,terminal)
        report_stage("STORED",local_assessed=len(valid),premium_evaluated=counters["premium_evaluated"])
        return result
