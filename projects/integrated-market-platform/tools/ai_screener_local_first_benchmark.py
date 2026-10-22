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
    # The same frozen manifest, adapter and cumulative budget; no legacy bypass.
    from tools.local_runtime_benchmark import run
    return run(phase="pilot")


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
