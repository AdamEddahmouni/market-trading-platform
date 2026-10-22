"""Local-first controls: no market providers, paid generations or trading authority."""
import json
import unittest

from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository
from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger
from tests.support.coverage_universe import NOW, SCOPE, News, PagingReader, RankingProvider, universe

METHOD = "STAGED_LOCAL_FIRST_EXPERIMENTAL"


class StagedTests(unittest.TestCase):
    def test_exhaustive_and_staged_progress_orders_are_separate(self):
        from market_platform_foundation.ui_api.screener_ai_runs import STAGES, _stage_order
        self.assertNotIn("LOCAL_ASSESSMENT", STAGES)
        self.assertEqual(_stage_order(SCOPE), STAGES)
        self.assertIn("LOCAL_ASSESSMENT", _stage_order({**SCOPE, "method": METHOD}))

    def test_method_is_explicit_and_invalid_method_refused(self):
        service = ScreenerAiService(reader=PagingReader([]), news=News(None), clock=lambda: NOW)
        self.assertEqual(service.validate_scope({**SCOPE, "method": METHOD}).get("method"), METHOD)
        with self.assertRaisesRegex(ValueError, "INVALID_AI_SCREENER_METHOD"):
            service.validate_scope({**SCOPE, "method": "invented"})

    def test_qualification_preserves_uncertainty_and_rejects_foreign_refs(self):
        from market_platform_foundation.intelligence.inference.local_qualification import parse_assessment, SCHEMA
        from tests.support.coverage_universe import row
        service = ScreenerAiService(reader=PagingReader([]), news=News(None), clock=lambda: NOW)
        candidates, _ = service._candidates("US_EQUITIES", {}, [row(0)], market=None,
                                           now="2026-10-02T15:00:00Z", include_flow=False)
        c = candidates[0]
        refs = [e["evidence_id"] for e in c["current_market_evidence"]]
        raw = dict(schema_version=SCHEMA, instrument_id=c["instrument"]["instrument_id"],
                   category="UNCERTAIN", rationale="The admitted observations need further review.",
                   supporting_refs=refs, conflicting_refs=[], uncertainties=["Direction is unresolved."])
        valid, reason = parse_assessment(json.dumps(raw), c)
        self.assertIsNone(reason)
        self.assertEqual(valid["category"], "UNCERTAIN")
        raw["supporting_refs"] = ["invented"]
        self.assertIsNone(parse_assessment(json.dumps(raw), c)[0])

    def _run(self, size=20, local=None, premium=None, **kwargs):
        from market_platform_foundation.ui_api.screener_ai_staged import ScreenerAiStaged
        from market_platform_foundation.local_state.staged_screener import StagedRepository
        from tests.support.local_first import QualificationProvider
        rows = universe(size, strong={size-1: 95.} if size else {})
        provider = premium or RankingProvider()
        service = ScreenerAiService(reader=PagingReader(rows), news=News(provider), clock=lambda: NOW)
        ledger, repo = CoverageLedger(), StagedRepository()
        result = ScreenerAiStaged(service, local=local or QualificationProvider(), ledger=ledger,
                                 repository=repo).run({**SCOPE, "method": METHOD},
                                 run_id="staged-test", account_id="CONTROLLED", **kwargs)
        return result, provider, ledger, repo

    def test_complete_pool_is_separate_from_action_records(self):
        result, premium, ledger, repo = self._run()
        self.assertTrue(result["staged"]["selection_complete"])
        self.assertEqual(result["staged"]["counters"]["local_assessed"], 20)
        self.assertEqual(result["staged"]["counters"]["advanced_to_premium"], 1)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertFalse(result["operationally_approved"])
        self.assertIsNotNone(repo.get(result["run_id"]))
        self.assertIsNone(ActionDecisionRepository().get("candidate_run", result["run_id"]))

    def test_uncertain_and_failed_are_not_excluded(self):
        from tests.support.local_first import QualificationProvider
        result, premium, _, _ = self._run(3, local=QualificationProvider(category="UNCERTAIN"))
        self.assertEqual(result["staged"]["counters"]["advanced_to_premium"], 3)
        result, premium, _, _ = self._run(3, local=QualificationProvider(malformed=True))
        self.assertEqual(result["staged"]["counters"]["local_invalid"], 3)
        self.assertEqual(result["staged"]["counters"]["advanced_to_premium"], 3)
        self.assertFalse(result["staged"]["selection_complete"])

    def test_stop_prevents_premium_dispatch(self):
        result, premium, _, _ = self._run(20, should_stop=lambda: True)
        self.assertEqual(premium.calls, 0)
        self.assertEqual(result["staged"]["status"], "STOPPED")
        self.assertTrue(result["staged"]["reconciled"])

    def test_unsupported_universe_is_not_exclusion(self):
        from market_platform_foundation.ui_api.screener_ai_staged import ScreenerAiStaged
        from market_platform_foundation.local_state.staged_screener import StagedRepository
        from tests.support.local_first import QualificationProvider
        provider = RankingProvider()
        service = ScreenerAiService(reader=PagingReader(universe(2)), news=News(provider), clock=lambda: NOW)
        result = ScreenerAiStaged(service, local=QualificationProvider(), ledger=CoverageLedger(),
                    repository=StagedRepository()).run({**SCOPE, "universe": "CRYPTO", "method": METHOD},
                    run_id="unsupported", account_id="CONTROLLED")
        self.assertEqual(result["staged"]["status"], "METHOD_UNSUPPORTED_UNIVERSE")
        self.assertEqual(result["staged"]["counters"]["universe_total"], 2)
        self.assertEqual(provider.calls, 0)

    def test_expired_local_answer_is_not_a_valid_exclusion(self):
        from market_platform_foundation.intelligence.inference.local_qualification import LocalQualifier
        from tests.support.local_first import QualificationProvider
        from tests.support.coverage_universe import row, NOW_ISO
        clock = [NOW]
        service = ScreenerAiService(reader=PagingReader([]), news=News(None), clock=lambda: clock[0])
        candidates, _ = service._candidates("US_EQUITIES", {}, [row(0)], market=None, now=NOW_ISO, include_flow=False)
        class Slow(QualificationProvider):
            def infer(self, *args, **kwargs):
                answer = super().infer(*args, **kwargs)
                clock[0] += 3600
                return answer
        result = LocalQualifier(Slow(), clock=lambda: clock[0]).assess(SCOPE, candidates[0], NOW_ISO)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "LOCAL_EVIDENCE_EXPIRED_DURING_INFERENCE")

    def test_changed_exclusion_cannot_complete_empty_pool(self):
        from market_platform_foundation.ui_api.screener_ai_staged import ScreenerAiStaged
        from market_platform_foundation.local_state.staged_screener import StagedRepository
        from tests.support.local_first import QualificationProvider
        rows = universe(2)
        class Changed(QualificationProvider):
            def infer(self, *args, **kwargs):
                result = super().infer(*args, **kwargs)
                if self.calls == 2:
                    rows[0]["fields"]["rsi_14"]["value"] = 90
                return result
        service = ScreenerAiService(reader=PagingReader(rows), news=News(RankingProvider()), clock=lambda: NOW)
        result = ScreenerAiStaged(service, local=Changed(), ledger=CoverageLedger(),
                    repository=StagedRepository()).run({**SCOPE, "method": METHOD}, run_id="changed", account_id="CONTROLLED")
        self.assertFalse(result["staged"]["selection_complete"])
        self.assertEqual(result["staged"]["status"], "STAGED_EVIDENCE_CHANGED")

    def test_action_rejects_forged_operational_approval(self):
        from market_platform_foundation.ui_api.screener_action import ScreenerActionService
        repo = ActionDecisionRepository()
        repo.put("candidate_run", "forged", dict(run_id="forged", method=METHOD,
                 operationally_approved=True, staged={"method_version": "ai-screener-local-first/1.0.0"}))
        service = ScreenerActionService(object(), repository=repo)
        with self.assertRaisesRegex(ValueError, "EXPERIMENTAL_METHOD_UNAPPROVED"):
            service.preview({"run_id": "forged", "instrument_id": "EQ:S00000"})


    def test_single_request_cannot_publish_experimental_method(self):
        service = ScreenerAiService(reader=PagingReader([]), news=News(RankingProvider()), clock=lambda: NOW)
        with self.assertRaisesRegex(ValueError, "STAGED_METHOD_REQUIRES_UNIVERSE_RUN"):
            service.run({**SCOPE, "method": METHOD})

    def test_valid_resolved_empty_pool_is_complete_zero_selection(self):
        from tests.support.local_first import QualificationProvider
        result, premium, ledger, _ = self._run(3,local=QualificationProvider(category="NO_SUPPORTED_CASE"))
        self.assertTrue(result["staged"]["selection_complete"])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(premium.calls,0)
        self.assertTrue(result["staged"]["local_coverage_complete"])

    def test_invalid_local_coverage_never_claims_final_selection(self):
        from tests.support.local_first import QualificationProvider
        result, _, _, _ = self._run(3,local=QualificationProvider(malformed=True))
        self.assertEqual(result["staged"]["counters"]["final_selected"],0)
        self.assertEqual(result["candidates"],[])

    def test_oversized_entire_pool_issues_zero_premium_calls(self):
        from tests.support.local_first import QualificationProvider
        from market_platform_foundation.intelligence.inference.anthropic_synthesis import BudgetedProvider, DailyBudget
        inner=RankingProvider()
        budget=DailyBudget(None,max_requests=1,max_tokens=1,clock=lambda:NOW)
        result,_,ledger,_=self._run(100,local=QualificationProvider(category="UNCERTAIN"),premium=BudgetedProvider(inner,budget))
        self.assertEqual(inner.calls,0)
        self.assertEqual(result["staged"]["counters"]["advanced_to_premium"],100)
        self.assertEqual(result["staged"]["status"],"AI_COVERAGE_BUDGET_INSUFFICIENT")
        self.assertFalse(result["staged"]["premium_plan"]["feasible_under_current_limits"])
        self.assertEqual(budget.status()["tokens"],0)

    def test_current_source_replacement_invalidates_advanced_assessment(self):
        from market_platform_foundation.ui_api.screener_ai_staged import ScreenerAiStaged
        from market_platform_foundation.local_state.staged_screener import StagedRepository
        from tests.support.local_first import QualificationProvider
        from tests.support.coverage_universe import row
        rows=universe(1,strong={0:95.})
        class Replacing(QualificationProvider):
            def infer(self,*args,**kwargs):
                result=super().infer(*args,**kwargs)
                rows[0]=row(0,rsi=30.)
                return result
        provider=RankingProvider()
        service=ScreenerAiService(reader=PagingReader(rows),news=News(provider),clock=lambda:NOW)
        result=ScreenerAiStaged(service,local=Replacing(),ledger=CoverageLedger(),repository=StagedRepository()).run(
            {**SCOPE,"method":METHOD},run_id="replacement",account_id="CONTROLLED")
        self.assertFalse(result["staged"]["selection_complete"])
        self.assertEqual(provider.calls,0)
        self.assertIn("STAGED_EVIDENCE_CHANGED",result["staged"]["reason"])

    def test_stop_preserves_returned_premium_outcome_and_usage(self):
        from tests.support.local_first import QualificationProvider
        stopped=[False]
        class StopReturning(RankingProvider):
            def on_call(self,call,packet):
                result=self.respond(packet);stopped[0]=True;return result
        result,provider,ledger,_=self._run(1,local=QualificationProvider(category="WARRANTS_REVIEW"),
            premium=StopReturning(),should_stop=lambda:stopped[0])
        self.assertEqual(provider.calls,1)
        receipts=ledger.records("staged-test-premium","batch")
        self.assertEqual(len(receipts),1)
        self.assertEqual(receipts[0]["tokens_input"],1000)
        self.assertEqual(ledger.unfinished_batches("staged-test-premium"),[])
        self.assertEqual(result["staged"]["status"],"STOPPED")
        self.assertEqual(result["staged"]["counters"]["final_selected"],0)

    def test_local_identity_changes_are_not_valid_assessments(self):
        from tests.support.local_first import QualificationProvider
        class Changed(QualificationProvider):
            def infer(self,*args,**kwargs):
                answer=super().infer(*args,**kwargs);self.model_id="changed";return answer
        result,_,ledger,_=self._run(1,local=Changed())
        self.assertEqual(result["staged"]["counters"]["local_invalid"],1)
        assessment=ledger.records("staged-test","batch")[0]["assessment"]
        self.assertTrue(assessment["raw_text"])
        self.assertTrue(assessment["inference_dispatched"])

    def test_blank_probability_and_unowned_capability_outputs_rejected(self):
        from market_platform_foundation.intelligence.inference.local_qualification import parse_assessment,SCHEMA
        from tests.support.coverage_universe import row,NOW_ISO
        service=ScreenerAiService(reader=PagingReader([]),news=News(None),clock=lambda:NOW)
        cs,_=service._candidates("US_EQUITIES",{},[row(0)],market=None,now=NOW_ISO,include_flow=False)
        c=cs[0]
        raw=dict(schema_version=SCHEMA,instrument_id=c["instrument"]["instrument_id"],category="NO_SUPPORTED_CASE",
            rationale="Admitted observations support no material review case.",supporting_refs=[e["evidence_id"] for e in c["current_market_evidence"]],
            conflicting_refs=[],uncertainties=["Interpretation limited."])
        for text in (" ", "FinBERT confirms adverse language.", "News confirms optimism with 95% confidence of an upward move."):
            with self.subTest(text=text):
                self.assertIsNone(parse_assessment(json.dumps({**raw,"rationale":text}),c)[0])
        for mutate in ({"instrument_id":"FOREIGN"},{"extra":"value"},{"supporting_refs":["foreign"]},{"uncertainties":[" "]}):
            with self.subTest(mutate=mutate):self.assertIsNone(parse_assessment(json.dumps({**raw,**mutate}),c)[0])

    def test_local_inference_exception_is_visible_and_not_an_exclusion(self):
        from tests.support.local_first import QualificationProvider
        class Broken(QualificationProvider):
            def infer(self,*args,**kwargs):raise MemoryError("controlled memory exhaustion")
        result,_,ledger,_=self._run(2,local=Broken())
        self.assertEqual(result["staged"]["counters"]["local_invalid"],2)
        self.assertEqual(result["staged"]["counters"]["advanced_to_premium"],2)
        self.assertTrue(all("MemoryError" in r["assessment"]["reason"] for r in ledger.records("staged-test","batch")))
        self.assertFalse(result["staged"]["selection_complete"])

    def test_provider_failure_and_global_failure_remain_incomplete(self):
        from tests.support.local_first import QualificationProvider
        from tests.support.coverage_universe import FailingProvider
        for fail_on,size in ((1,3),(3,60)):
            result,provider,ledger,_=self._run(size,local=QualificationProvider(category="WARRANTS_REVIEW"),
                premium=FailingProvider(fail_on=fail_on,timeout=True))
            self.assertFalse(result["staged"]["selection_complete"])
            self.assertEqual(result["candidates"],[])
            self.assertTrue(ledger.records("staged-test-premium","batch"))

    def test_staged_store_finalization_is_immutable_and_rejects_authority(self):
        from market_platform_foundation.local_state.staged_screener import StagedRepository
        repo=StagedRepository()
        with self.assertRaisesRegex(ValueError,"AUTHORITY_INVALID"):
            repo.put({"method":METHOD,"operationally_approved":True,"run_id":"unsafe"})
        result,_,_,repo=self._run(1)
        with self.assertRaisesRegex(ValueError,"COLLISION"):
            repo.put({**result,"reason":"changed"})

    def test_restart_discovers_account_scoped_staged_receipts_without_resume(self):
        from unittest.mock import patch
        from market_platform_foundation.ui_api.screener_ai_runs import AiScreenerRuns
        from market_platform_foundation.local_state.staged_screener import StagedRepository
        result,provider,ledger,repo=self._run(1)
        service=ScreenerAiService(reader=PagingReader([]),news=News(provider),clock=lambda:NOW)
        tracker=AiScreenerRuns(service,clock=lambda:NOW)
        with patch("market_platform_foundation.local_state.staged_screener.staged_stores",return_value=(ledger,repo)):
            latest=tracker.current("CONTROLLED")["experimental_latest"]
            self.assertEqual(tracker.read("CONTROLLED",latest["run_id"])["result"]["run_id"],result["run_id"])
            self.assertIsNone(tracker.current("OTHER")["experimental_latest"])
            self.assertIsNone(tracker.current("CONTROLLED")["latest"])
            ledger.append("interrupted","run",{"account_id":"CONTROLLED","method":METHOD,"query":SCOPE,"started_at":"2026-10-02T15:00:00Z"})
            self.assertTrue(any(r["run_id"]=="interrupted" for r in tracker.current("CONTROLLED")["interrupted"]))
            calls=provider.calls
            tracker._recover(service)
            self.assertEqual(ledger.terminal("interrupted")["status"],"INTERRUPTED")
            self.assertEqual(provider.calls,calls)

    def test_qualification_cache_corruption_never_overrides_validation(self):
        from market_platform_foundation.intelligence.inference.local_qualification import LocalQualifier
        from tests.support.local_first import QualificationProvider
        from tests.support.coverage_universe import row,NOW_ISO
        service=ScreenerAiService(reader=PagingReader([]),news=News(None),clock=lambda:NOW)
        cs,_=service._candidates("US_EQUITIES",{},[row(0)],market=None,now=NOW_ISO,include_flow=False)
        class Cache:
            def __init__(self):self.value=None
            def get(self,*args):return (NOW+30,self.value) if self.value else None
            def put(self,digest,expiry,result,now):self.value=dict(result)
        provider=QualificationProvider();cache=Cache();q=LocalQualifier(provider,clock=lambda:NOW,cache=cache)
        first=q.assess(SCOPE,cs[0],NOW_ISO);second=q.assess(SCOPE,cs[0],NOW_ISO)
        self.assertEqual(second["cache"],"HIT");self.assertEqual(provider.calls,1)
        cache.value["category"]="WARRANTS_REVIEW"
        corrupted=q.assess(SCOPE,cs[0],NOW_ISO)
        self.assertFalse(corrupted["valid"]);self.assertEqual(provider.calls,1)
        cache.value["raw_text"]="corrupt"
        third=q.assess(SCOPE,cs[0],NOW_ISO)
        self.assertEqual(provider.calls,1);self.assertFalse(third["valid"]);self.assertEqual(third["reason"],"LOCAL_REUSE_CORRUPT")


    def test_stop_after_lazy_start_prevents_generation(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider
        from market_platform_foundation.intelligence.inference.local_qualification import QualificationPacket,LocalQualifier
        from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
        from market_platform_foundation.intelligence.inference.config import IntelligenceInferenceConfig
        stop=[False];posts=[]
        class Server:
            manifest=SimpleNamespace(context=8192)
            def running(self):return False
            def _ours(self):return None
            def ensure_running(self):stop[0]=True;return None
            def touch(self):pass
        class Monitor:
            failure=None
            def __init__(self,*args):pass
            def start(self):pass
        def post(url,body,timeout):
            posts.append(url)
            return (200,b'{"prompt":"data"}') if url.endswith("apply-template") else (200,b'{"tokens":[1,2]}')
        provider=LocalChatInferenceProvider(base_url="http://127.0.0.1:19999",model_id="fixture",server=Server(),poster=post)
        packet=QualificationPacket(IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION,"i","h","2026-10-02T15:00:00Z",{},[],{},lambda:stop[0])
        result=provider._infer_locked(packet,rendered_prompt="controlled",config=IntelligenceInferenceConfig(),monitor=Monitor())
        self.assertEqual(result.error_message,"STOPPED_BY_OPERATOR")
        self.assertFalse(any(url.endswith("chat/completions") for url in posts))

    def test_queue_is_bounded_and_memory_failure_is_explicit(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference.local_resources import ADMISSION,ResourceMonitor
        from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider
        from market_platform_foundation.intelligence.inference.local_qualification import QualificationPacket
        from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
        from market_platform_foundation.intelligence.inference.config import IntelligenceInferenceConfig
        provider=LocalChatInferenceProvider(base_url="http://127.0.0.1:19999",model_id="fixture")
        packet=QualificationPacket(IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION,"i","h","2026-10-02T15:00:00Z",{},[],{})
        ADMISSION.acquire();ADMISSION.acquire()
        try:
            answer=provider.infer(packet,rendered_prompt="controlled",config=IntelligenceInferenceConfig())
            self.assertEqual(answer.error_message,"LOCAL_INFERENCE_QUEUE_FULL")
        finally:ADMISSION.release();ADMISSION.release()
        with patch("market_platform_foundation.intelligence.inference.local_resources.memory_sample",return_value={"available_bytes":2*1024**3,"process_bytes":7*1024**3}):
            monitor=ResourceMonitor(SimpleNamespace(_process=None))
            self.assertEqual(monitor.check(),"LOCAL_RESOURCE_MEMORY_LIMIT")

    def test_unobservable_external_local_runtime_is_refused(self):
        from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider
        from market_platform_foundation.intelligence.inference.local_qualification import QualificationPacket
        from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
        from market_platform_foundation.intelligence.inference.config import IntelligenceInferenceConfig
        provider=LocalChatInferenceProvider(base_url="http://127.0.0.1:19999",model_id="unverified")
        packet=QualificationPacket(IntelligenceTaskType.SCREENER_LOCAL_QUALIFICATION,"i","h","2026-10-02T15:00:00Z",{},[],{})
        answer=provider.infer(packet,rendered_prompt="controlled",config=IntelligenceInferenceConfig())
        self.assertEqual(answer.error_message,"LOCAL_QUALIFICATION_REQUIRES_OWNED_PINNED_RUNTIME")

    def test_experimental_action_rejection_precedes_model_inference_and_handoff(self):
        from tests.intelligence.test_action_decision import ActionServiceTests
        # Production boundary is exercised with an explicitly isolated fixture account and repository.
        harness=ActionServiceTests("test_browser_cannot_supply_evidence_or_quantities")
        harness.setUp()
        try:
            raw=harness.repo.get("candidate_run",harness.body["run_id"])
            harness.repo.put("candidate_run","LF-forged",{**raw,"run_id":"LF-forged","operationally_approved":True})
            for operation in (harness.service.preview,harness.service.run):
                with self.assertRaisesRegex(ValueError,"EXPERIMENTAL_METHOD_UNAPPROVED"):
                    operation({"run_id":"LF-forged","instrument_id":harness.body["instrument_id"]})
            harness.provider.infer.assert_not_called()
        finally:harness.tearDown()



    def test_foreign_premium_identity_is_rejected_with_usage_receipt(self):
        from dataclasses import replace
        from tests.support.local_first import QualificationProvider
        class Foreign(RankingProvider):
            def on_call(self,call,packet):
                return replace(self.respond(packet),provider_id="foreign",model_id="foreign")
        result,provider,ledger,_=self._run(1,local=QualificationProvider(category="WARRANTS_REVIEW"),premium=Foreign())
        self.assertFalse(result["staged"]["selection_complete"])
        receipt=ledger.records("staged-test-premium","batch")[0]
        self.assertEqual(receipt["reason"],"PREMIUM_RESPONSE_IDENTITY_MISMATCH")
        self.assertEqual(receipt["tokens_input"],1000)

    def test_premium_response_material_change_is_rejected_with_usage_receipt(self):
        from market_platform_foundation.ui_api.screener_ai_staged import ScreenerAiStaged
        from market_platform_foundation.local_state.staged_screener import StagedRepository
        from tests.support.local_first import QualificationProvider
        rows=universe(1,strong={0:95.})
        class Changing(RankingProvider):
            def on_call(self,call,packet):
                result=self.respond(packet);rows[0]["fields"]["price"]["value"]=101.;return result
        provider=Changing();ledger=CoverageLedger()
        service=ScreenerAiService(reader=PagingReader(rows),news=News(provider),clock=lambda:NOW)
        result=ScreenerAiStaged(service,local=QualificationProvider(),ledger=ledger,repository=StagedRepository()).run(
            {**SCOPE,"method":METHOD},run_id="material",account_id="CONTROLLED")
        self.assertFalse(result["staged"]["selection_complete"])
        receipt=ledger.records("material-premium","batch")[0]
        self.assertEqual(receipt["reason"],"STAGED_EVIDENCE_CHANGED")
        self.assertEqual(receipt["tokens_input"],1000)

from tests.trading_correctness.test_trade_lifecycle import _Lifecycle, A, iso

class StagedFixtureCompatibilityTests(_Lifecycle):
    def test_injected_fixture_authority_through_preview_submit_lifecycle_evaluation(self):
        from market_platform_foundation.ui_api.screener_ai_staged import ScreenerAiStaged
        from market_platform_foundation.local_state.staged_screener import StagedRepository
        from tests.support.local_first import QualificationProvider,ExperimentalFixtureAuthority
        from tests.support.coverage_universe import row
        from tests.intelligence.test_action_decision import proposal
        from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
        from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
        from market_platform_foundation.intelligence.contracts.common import IntelligenceScope,QualitySummary
        r=row(0,rsi=95.,price=150.,as_of=iso(self.t))
        r["instrument"].update(instrument_id=A,symbol=A)
        provider=RankingProvider()
        service=ScreenerAiService(reader=PagingReader([r]),news=News(provider),clock=self.clock)
        result=ScreenerAiStaged(service,local=QualificationProvider(),ledger=CoverageLedger(),repository=StagedRepository()).run(
            {**SCOPE,"method":METHOD},run_id="fixture-compat",account_id="CONTROLLED")
        self.assertTrue(result["staged"]["selection_complete"])
        with self.assertRaisesRegex(ValueError,"EXPERIMENTAL_METHOD_UNAPPROVED"):
            self.actions.preview({"run_id":result["run_id"],"instrument_id":A})
        run_id=ExperimentalFixtureAuthority(self.repo).admit(result)
        self.store.strategy_repository.put_opportunity(OpportunityV1("opp-"+run_id,"1",IntelligenceScope((A,)),
            int((self.t-1)*1e9),QualitySummary("GOOD"),side="LONG",valid_until_ns=int((self.t+60)*1e9)))
        def fixture(packet,*,rendered_prompt,config):
            c=packet.candidates[0]
            value=proposal("ENTER","LONG")
            value["supporting_refs"]=[e["evidence_id"] for e in c["current_market_evidence"] if not e["weak_reasons"]]
            value["missing_capabilities"]=[m["capability"] for m in c["missing"]]
            return ProviderInferenceResponse(json.dumps(value),"fixture","controlled",simulated=True)
        self.model.infer=fixture
        self.assertTrue(self.actions.preview({"run_id":run_id,"instrument_id":A})["candidate_current"])
        decision=self.actions.run({"run_id":run_id,"instrument_id":A,"opportunity_id":"opp-"+run_id})
        self.assertEqual(decision["execution_readiness"],"PREVIEW_ALLOWED",decision["blocker_codes"])
        submission=self.governed(decision,quantity=1,price="150.00")
        self.assertEqual(submission["order"]["state"],"FILLED",submission)
        listing=self.listing(run_id)
        self.assertEqual(listing["selected"][0]["stage"],"POSITION_OPEN")
        self.assertEqual(listing["experiment"]["live_capital"],False)
        # Evaluation/lifecycle authorities operate on fixture-owned fills, never the experimental record.
        self.assertGreater(len(self.store.paper_ledger.events),0)
        from market_platform_foundation.ui_api import paper_experiment
        evaluation=paper_experiment.current_experiment_payload(self.store)
        self.assertIsNotNone(evaluation)
        # Reassessment consumes the fixture-authorized record and the actual fixture-owned position.
        self.model.infer=lambda packet, **kwargs: ProviderInferenceResponse(json.dumps({**proposal("HOLD",None),"supporting_refs":[e["evidence_id"] for e in packet.candidates[0]["current_market_evidence"]], "missing_capabilities":[m["capability"] for m in packet.candidates[0]["missing"]]}),"fixture","controlled",simulated=True)
        held=self.actions.run({"run_id":run_id,"instrument_id":A})
        self.assertEqual(held["action_state"],"HOLD")
        self.assertFalse(result["operationally_approved"])


if __name__ == "__main__":
    unittest.main()
