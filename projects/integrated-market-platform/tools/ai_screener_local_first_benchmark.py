"""Frozen zero-spend local qualification research; fixtures are never premium judgments."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from market_platform_foundation.intelligence.inference.local_qualification import LocalQualifier, PROMPT, METHOD_VERSION, evidence_hash
from market_platform_foundation.intelligence.inference.evidence_compaction import semantic_hash
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from tests.support.coverage_universe import NOW, NOW_ISO, SCOPE, PagingReader, News, row

OUT = ROOT / "artifacts" / "ai-screener-local-first"
SCENARIOS = ("tail_strong", "strong_little_news", "weak_positive_news", "sentiment_technical_conflict",
 "rapid_price", "stale_evidence", "provider_disagreement", "no_direction", "incomplete_flow",
 "similar_competitors", "unusual_risk", "below_cutoff", "categorical_uncertainty")
TARGETS = {"reference_top5_recall":1., "labeled_positive_recall":.95, "invalid_refs_accepted":0,
 "invalid_output_rate":.01, "qualification_disagreement":.05, "paid_token_reduction":.90}
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n",encoding="utf-8")
def cases():
    result=[]
    for universe in ("US_EQUITIES","US_ETFS"):
        for split in ("development","holdout"):
            for i,name in enumerate(SCENARIOS):
                r=row(i + (100 if split=="holdout" else 0),rsi=50. if name=="weak_positive_news" else 85.)
                r["instrument"]["universe"]=universe
                r["instrument"]["asset_class"]="ETF" if universe=="US_ETFS" else "EQUITY"
                if name=="rapid_price": r["fields"]["change_pct"]["value"]=8.5
                if name=="no_direction": r["fields"].pop("rsi_14");r["fields"].pop("change_pct")
                if name=="unusual_risk":r["fields"]["change_pct"]["value"]=-9.5
                service=ScreenerAiService(reader=PagingReader([]),news=News(None),clock=lambda:NOW)
                cs,_=service._candidates(universe,{},[r],market=None,now=NOW_ISO,include_flow=False)
                c=cs[0]
                if name=="stale_evidence":
                    for e in c["current_market_evidence"]:e["valid_until"]="2026-10-02T14:59:00Z"
                if name in ("weak_positive_news","sentiment_technical_conflict","provider_disagreement"):
                    cap="SENTIMENT" if name=="sentiment_technical_conflict" else "NEWS"
                    e=copy.deepcopy(c["current_market_evidence"][0]);e.update(evidence_id=name+":ref",capability=cap,role="REFERENCE_CONTEXT")
                    e["facts"]={"headline":"Controlled favorable headline language; several syndicated copies." if cap=="NEWS" else "Controlled negative language"}
                    c["reference_evidence"].append(e)
                    if cap=="SENTIMENT":c["alignments"]=[{"result":"CONFLICTING","sentiment_refs":[e["evidence_id"]],"cutoff":NOW_ISO}]
                    if name=="provider_disagreement": c["uncertainty_context"]="Controlled quote providers disagree; do not reconcile by inventing a value."
                if name in ("categorical_uncertainty","below_cutoff","similar_competitors","incomplete_flow"):
                    c["research_context"]={"categorical_uncertainty":"Interpretation ambiguous; review unresolved.",
                     "below_cutoff":"No shortlist cutoff is permitted.", "similar_competitors":"Independent assessment; no competitors supplied.",
                     "incomplete_flow":"Optional flow absent; no exclusion from absence."}[name]
                label="NEGATIVE" if name=="weak_positive_news" else "UNAVAILABLE" if name=="stale_evidence" else "POSITIVE"
                result.append({"case_id":universe+":"+split+":"+name,"universe":universe,"split":split,
                 "scenario":name,"candidate":c,"label":label,"label_basis":"BLINDED_CONTROLLED_REVIEW_RELEVANCE",
                 "evidence_hash":evidence_hash(c),"scope":{**SCOPE,"universe":universe}})
    return result
def freeze():
    path=OUT/"manifest.json"
    if path.exists():raise ValueError("FROZEN_MANIFEST_ALREADY_EXISTS")
    data=cases()
    payload={"schema_version":"local-first-benchmark/1.0.0","frozen_at":datetime.now(UTC).isoformat(),
     "evidence_class":"SOFTWARE_CONTROLLED_HISTORICAL_REPLAY","cutoff":NOW_ISO,"method":METHOD_VERSION,
     "source_sha":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,encoding="utf-8").strip(),
     "targets":TARGETS,"prompt":PROMPT,"prompt_hash":semantic_hash(PROMPT),"max_tokens":384,"threads":4,
     "context":8192,"inference_limit_seconds":7200,"cases":data,"dataset_hash":semantic_hash(data),
     "references":{"matching_stored_premium":"UNAVAILABLE","exact_context_replay":"UNAVAILABLE",
      "controlled_labels":"Synthetic interpretation relevance; no returns or real premium judgments."},
     "metrics":{"recall":"Advanced positive / eligible labeled positive; uncertain/invalid advance; invalid separately reported.",
      "precision":"Positive advanced / all labeled advanced.","false_exclusions":"Valid NO_SUPPORTED_CASE on labeled POSITIVE.",
      "disagreement":"Different categories or validation result for preassigned repetitions.",
      "ties":"No local rank; premium ties instrument identity; real rank correlation unavailable.",
      "exclusions":"Only explicitly stale inputs excluded from labeled recall denominator; reported independently."},
     "pilot_case_indices":[0,1,4],"repeat_case_indices":[1,3,9],
     "perturbations":["identical repeat","reverse evidence order","JSON indentation/order"],
     "scales":[20,50,100,500,4630,20000],"operationally_approved":False,"paid_generations":0}
    payload["manifest_hash"]=semantic_hash(payload)
    write(path,payload);print("Frozen",payload["manifest_hash"],len(data),"cases",flush=True)
def load():
    m=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    digest=m.pop("manifest_hash")
    if semantic_hash(m)!=digest or semantic_hash(m["cases"])!=m["dataset_hash"] or m["prompt_hash"]!=semantic_hash(PROMPT):
        raise ValueError("FROZEN_BENCHMARK_DRIFT")
    m["manifest_hash"]=digest;return m
def real():
    from market_platform_foundation.intelligence.inference.local_provider import LocalModelManifest,LocalLlamaServer,LocalChatInferenceProvider
    from market_platform_foundation.intelligence.inference.inference_identity import provider_identity
    from market_platform_foundation.intelligence.inference.local_resources import memory_sample
    from market_platform_foundation.intelligence.inference.local_provider import MANIFEST_RELATIVE
    from market_platform_foundation.local_state.external_cache import imp_cache_dir
    m=load()
    manifest_path=imp_cache_dir()/MANIFEST_RELATIVE
    base=LocalModelManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
    if not base or base.revision!="bc640142c66e1fdd12af0bd68f40445458f3869b" or base.runtime_version!="b11269":
        raise ValueError("PINNED_LOCAL_MODEL_REQUIRED")
    if hashlib.file_digest(base.model_path.open("rb"),"sha256").hexdigest()!="7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5":
        raise ValueError("MODEL_CHECKSUM_FAILED")
    budget_file=OUT/"inference-budget.json"
    budget=json.loads(budget_file.read_text(encoding="utf-8")) if budget_file.exists() else {"used_seconds":0.,"calls":0,"limit_seconds":7200}
    if budget.get("pending"): raise ValueError("PRIOR_INFERENCE_OUTCOME_UNKNOWN; charge reserved time before manual research resumption")
    runs=[]; pilot_stats=[]
    def call(provider,qualifier,case,phase,variant="original"):
        remaining=7200-budget["used_seconds"]
        if remaining<720:raise TimeoutError("CUMULATIVE_TWO_HOUR_CEILING")
        budget["pending"]={"reserved_seconds":720,"case_id":case["case_id"]};write(budget_file,budget)
        started=time.perf_counter()
        c=copy.deepcopy(case["candidate"])
        if variant=="reverse evidence order":c["current_market_evidence"].reverse();c["reference_evidence"].reverse()
        original_input=qualifier.input
        if variant=="JSON indentation/order":
            def formatted(*args):
                digest,canonical,rendered=original_input(*args)
                prefix=rendered.split("\nEVIDENCE DATA\n")[0]
                return digest,canonical,prefix+"\nEVIDENCE DATA\n"+json.dumps(canonical,indent=2,sort_keys=False)
            qualifier.input=formatted
        try:answer=qualifier.assess(case["scope"],c,m["cutoff"])
        finally:qualifier.input=original_input
        elapsed=time.perf_counter()-started
        budget["used_seconds"]+=elapsed;budget["calls"]+=1;budget.pop("pending");write(budget_file,budget)
        record={"phase":phase,"variant":variant,"case_id":case["case_id"],"universe":case["universe"],
         "split":case["split"],"scenario":case["scenario"],"label":case["label"],"elapsed_seconds":elapsed,
         "identity":provider_identity(provider),"resource_sample":getattr(provider,"last_resource_sample",{}),
         "system_memory":memory_sample(),"assessment":answer}
        with (OUT/"real-results.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(record,sort_keys=True)+"\n")
        runs.append(record);print(phase,case["case_id"],answer["valid"],answer["category"],round(elapsed,2),flush=True)
        return record
    for name,layers,port in (("VULKAN",99,18190),("CPU",0,18191)):
        server=LocalLlamaServer(replace(base,gpu_layers=layers,threads=4),port=port,log_path=OUT/(name.lower()+"-runtime.log"))
        provider=LocalChatInferenceProvider(base_url=server.base_url,model_id=base.model_id,server=server)
        qualifier=LocalQualifier(provider,clock=lambda:NOW)
        try:
            samples=[call(provider,qualifier,m["cases"][i],name+"_PILOT") for i in m["pilot_case_indices"]]
            pilot_stats.append({"backend":name,"gpu_layers":layers,"startup_ms":server.last_start_ms,
             "elapsed_seconds":sum(s["elapsed_seconds"] for s in samples),"valid":sum(s["assessment"]["valid"] for s in samples),
             "resource_failures":sum(bool(s["resource_sample"].get("failure")) for s in samples)})
        finally:server.stop()
    acceptable=[s for s in pilot_stats if not s["resource_failures"] and s["valid"]==3]
    if not acceptable:
        write(OUT/"real-summary.json",{"manifest_hash":m["manifest_hash"],"pilot_comparison":pilot_stats,"scales":[{"scale":n,"completed":0,"state":"BLOCKED_RESOURCE_OR_RELIABILITY"} for n in m["scales"]],"inference_budget":budget,"generation_requests_dispatched":sum(bool(r["assessment"].get("inference_dispatched")) for r in runs),"real_generations":sum(bool(r["assessment"].get("inference_dispatched")) and bool(r["assessment"].get("raw_text")) for r in runs),"paid_generations":0,"operationally_approved":False,"suitability":"UNPROVEN"})
        print("No compliant pilot; real-model scale evaluation blocked",flush=True)
        return
    # Quality failures preserve results and prevent a suitability claim. Choose speed for measurement only if no compliant pilot.
    selected=min(acceptable or pilot_stats,key=lambda s:s["elapsed_seconds"])
    write(OUT/"pilot-comparison.json",{"pilots":pilot_stats,"selected_for_measurement":selected,
     "suitability":"UNPROVEN","selection_basis":"Fastest reliable contract-compliant pilot, else diagnostic speed only.",
     "integrated_gpu":"Shared system memory; adapter marketing capacity is not dedicated VRAM."})
    server=LocalLlamaServer(replace(base,gpu_layers=selected["gpu_layers"],threads=4),port=18192,log_path=OUT/"selected-runtime.log")
    provider=LocalChatInferenceProvider(base_url=server.base_url,model_id=base.model_id,server=server)
    qualifier=LocalQualifier(provider,clock=lambda:NOW)
    scales=[]
    try:
        for c in m["cases"]:call(provider,qualifier,c,"FROZEN_EVALUATION")
        for i in m["repeat_case_indices"]:
            for variant in m["perturbations"]:
                call(provider,qualifier,m["cases"][i],"REPEAT_PERTURBATION",variant)
        for scale in m["scales"]:
            started=time.perf_counter();completed=0
            try:
                # Independent software-controlled measurements at each scale, with no paid engine.
                for i in range(scale):
                    call(provider,qualifier,m["cases"][i%len(m["cases"])],"SCALE_"+str(scale))
                    completed+=1
            except TimeoutError:
                scales.append({"scale":scale,"completed":completed,"state":"INTERRUPTED_TWO_HOUR_CEILING",
                 "elapsed_seconds":time.perf_counter()-started});break
            scales.append({"scale":scale,"completed":completed,"state":"MEASURED",
             "elapsed_seconds":time.perf_counter()-started})
    finally:
        server.stop()
        for scale in m["scales"]:
            if not any(s["scale"]==scale for s in scales):scales.append({"scale":scale,"completed":0,"state":"NOT_MEASURED_CEILING"})
        write(OUT/"real-summary.json",{"manifest_hash":m["manifest_hash"],"pilot_comparison":pilot_stats,
         "scales":scales,"inference_budget":budget,"paid_generations":0,"operationally_approved":False})
def controls():
    """Software-only full-engine scales; all fixture authority is constructor-injected."""
    import tempfile
    from market_platform_foundation.local_state.connection import LocalStateConnection
    from market_platform_foundation.local_state.staged_screener import StagedLedger,StagedRepository
    from market_platform_foundation.ui_api.screener_ai_staged import ScreenerAiStaged
    from market_platform_foundation.intelligence.inference.anthropic_synthesis import BudgetedProvider,DailyBudget
    from tests.support.coverage_universe import universe,RankingProvider
    from tests.support.local_first import QualificationProvider
    m=load();results=[]
    for scale in m["scales"]:
        with tempfile.TemporaryDirectory(prefix="imp-local-first-control-") as directory:
            connection=LocalStateConnection(Path(directory)/"staged.sqlite")
            rows=universe(scale,strong={scale-1:95.})
            inner=RankingProvider();budget=DailyBudget(None,max_requests=30,max_tokens=200000,clock=lambda:NOW)
            provider=BudgetedProvider(inner,budget)
            service=ScreenerAiService(reader=PagingReader(rows),news=News(provider),clock=lambda:NOW)
            local=QualificationProvider();started=time.perf_counter()
            result=ScreenerAiStaged(service,local=local,ledger=StagedLedger(connection),repository=StagedRepository(connection)).run(
                {**SCOPE,"method":"STAGED_LOCAL_FIRST_EXPERIMENTAL"},run_id="control-"+str(scale),account_id="BENCHMARK_FIXTURE")
            elapsed=time.perf_counter()-started
            assert result["staged"]["selection_complete"] and result["staged"]["reconciled"]
            assert result["staged"]["counters"]["universe_total"]==scale
            results.append({"scale":scale,"state":"SOFTWARE_CONTROLLED","seconds":elapsed,"staged":result["staged"],
                "paid_generations":0,"fixture_premium_calls":inner.calls,"fixture_local_calls":local.calls,
                "input_hash":semantic_hash(rows)})
            connection.close()
            print("CONTROL",scale,round(elapsed,2),flush=True)
        write(OUT/"engineering-scales.json",{"manifest_hash":m["manifest_hash"],"scales":results,"evidence_class":"SOFTWARE_CONTROLLED","paid_generations":0})

def main():
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=("freeze","real","controls"));args=parser.parse_args()
    if args.action=="freeze":freeze()
    elif args.action=="controls":controls()
    else:real()
if __name__=="__main__":main()
