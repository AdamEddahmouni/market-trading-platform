"""Bounded real-model validation using the original frozen benchmark and adapter."""
from __future__ import annotations
import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from tools.ai_screener_local_first_benchmark import load
from market_platform_foundation.local_state.external_cache import imp_cache_dir, read_manifest, write_json_atomic
from market_platform_foundation.intelligence.inference.evidence_compaction import semantic_hash
from market_platform_foundation.intelligence.inference.local_runtime import apply_profile, readiness, PROFILES
from market_platform_foundation.intelligence.inference.local_provider import (
    LocalLlamaServer,LocalChatInferenceProvider,SERVER_ALIAS)
from market_platform_foundation.intelligence.inference.local_qualification import LocalQualifier
from market_platform_foundation.intelligence.inference.local_models import MODELS, DEFAULT_MODEL_ID, model_manifest
from tests.support.coverage_universe import NOW

LIMIT=7200
RESERVATION=720  # startup + template + tokenizer + generation timeouts + cleanup margin


@contextmanager
def exclusive_run(state):
    state.mkdir(parents=True,exist_ok=True)
    lock=state/'running.lock'
    try:
        with lock.open('x',encoding='utf-8') as stream:stream.write(str(os.getpid()))
    except FileExistsError as exc:
        raise ValueError('LOCAL_BENCHMARK_ALREADY_RUNNING_OR_INTERRUPTED') from exc
    try:yield
    finally:lock.unlink(missing_ok=True)


def reserve(budget,case_id):
    used=budget.get('used_seconds')
    if isinstance(used,bool) or not isinstance(used,(int,float)) or not math.isfinite(used) or used<0:
        raise ValueError('LOCAL_BENCHMARK_BUDGET_CORRUPT')
    if budget.get('pending'):raise ValueError('PRIOR_INFERENCE_OUTCOME_UNKNOWN')
    if budget['used_seconds']+RESERVATION>LIMIT:raise ValueError('CUMULATIVE_TWO_HOUR_CEILING')
    budget['pending']={'case_id':case_id,'reserved_seconds':RESERVATION}


def quality_summary(records,expected):
    real=[r for r in records if r['assessment'].get('inference_dispatched') and not r['assessment'].get('simulated')]
    valid=[r for r in real if r['assessment']['valid']]
    positive=[r for r in real if r['label']=='POSITIVE']
    excluded=[r for r in positive if r['assessment']['valid'] and r['assessment']['category']=='NO_SUPPORTED_CASE']
    advance=[r for r in real if not r['assessment']['valid'] or r['assessment']['category']!='NO_SUPPORTED_CASE']
    stale=[r for r in records if r['label']=='UNAVAILABLE' and r['assessment'].get('reason')=='LOCAL_EVIDENCE_EXPIRED']
    complete=len(records)==expected and len(real)+len(stale)==expected and bool(real)
    errors=[r['assessment'].get('reason') or '' for r in real if not r['assessment']['valid']]
    return {'real_cases_completed':len(real),'fixture_cases_completed':0,'cases_not_completed':expected-len(real)-len(stale),
        'intentional_stale_exclusions':len(stale),'quality_complete':complete,
        'valid_outputs':len(valid),'failed':len(real)-len(valid),
        'qualified':sum(r['assessment']['category']=='WARRANTS_REVIEW' for r in valid),
        'uncertain':sum(r['assessment']['category']=='UNCERTAIN' for r in valid),
        'proposed_premium_count':len(advance) if real else None,
        'recall':(len(positive)-len(excluded))/len(positive) if complete and positive else None,
        'operational_advancement_recall':(len(positive)-len(excluded))/len(positive) if positive else None,
        'operational_advancement_recall_basis':'DISPATCHED_SUBSET_ONLY' if not complete else 'COMPLETE_ELIGIBLE_SPLIT',
        'false_exclusions':len(excluded) if real else None,
        'invalid_output_rate':len(errors)/len(real) if real else None,
        'evidence_grounding_failures':sum(any(k in e for k in ('REFERENCE','FOREIGN','CONFLICT','SUPPORT','CLAIM')) for e in errors) if real else None,
        'missing_capability_errors':sum('CAPABILITY' in e for e in errors) if real else None,
        'timeout_or_failure_count':len(records)-len(valid)-len(stale) if records else None,
        'qualification_accuracy':None,'reference_top5_recall':None,'inconsistent_decisions':None,
        'unavailable_metrics_reason':'No independent trade ground truth or premium reference; no repetition measurements.',
        'quality_status':'LOCAL_QUALITY_EVALUATED' if complete else 'LOCAL_QUALITY_NOT_PROVEN',
        'recall_basis':'Original controlled-label advancement rubric; invalid and uncertain advance, invalid reported separately.'}


def economic_plan(records,cases,cutoff):
    """Offline provider accounting on actual advancement; no credentials or generation."""
    if not records or not any(r['assessment'].get('inference_dispatched') for r in records):
        return {'status':'STAGED_BUDGET_NOT_MEASURED','plans':None,'paid_generations':0}
    from market_platform_foundation.intelligence.inference.anthropic_synthesis import AnthropicSynthesisProvider,BudgetedProvider,DailyBudget
    from market_platform_foundation.intelligence.inference.candidate_reduction import CandidateReducer
    from market_platform_foundation.intelligence.inference.coverage_plan import chunks,reduction_rounds,budget_requirement
    def denied(*args,**kwargs):raise RuntimeError('BENCHMARK_PREMIUM_NETWORK_PROHIBITED')
    provider=BudgetedProvider(AnthropicSynthesisProvider(api_key='',model='claude-sonnet-4-6',poster=denied),DailyBudget(None,clock=lambda:NOW))
    reducer=CandidateReducer(provider=provider,clock=lambda:NOW)
    by_id={c['case_id']:c for c in cases}
    pool=[by_id[r['case_id']] for r in records if not r['assessment']['valid'] or r['assessment']['category']!='NO_SUPPORTED_CASE']
    plans=[]
    for universe in ('US_EQUITIES','US_ETFS'):
        selected=[c for c in pool if c['universe']==universe]
        estimates=[reducer.estimate(group[0]['scope'],[c['candidate'] for c in group],cutoff) for group in chunks(selected)]
        required=budget_requirement([e['tokens'] for e in estimates],reduction_rounds(len(estimates)))
        plans.append({'universe':universe,'proposed_premium_count':len(selected),'estimated_provider_input':sum(e['input_tokens'] for e in estimates),
            'reserved_output_reasoning':sum(e['tokens']-e['input_tokens'] for e in estimates),
            'global_comparison_reserved_tokens':required['reduction_tokens'],'required':required,
            'configured_reference_limits':{'requests':30,'tokens':200000},
            'fits_reference_limits':required['requests']<=30 and required['tokens']<=200000})
    return {'status':'PROJECTED_FROM_OBSERVED_LOCAL_OUTPUTS','plans':plans,'paid_generations':0,
            'limitations':'Partial benchmark pool only; no observed 4630-row pool or savings; reference quotas are not live remaining quota.'}


def run(*,phase='pilot',profile=None,model_id=DEFAULT_MODEL_ID,output=None):
    if model_id not in MODELS:
        raise ValueError('LOCAL_MODEL_NOT_IN_REGISTRY')
    profile = profile or MODELS[model_id].profile
    frozen=load()
    state=imp_cache_dir()/'benchmarks'/'local-runtime-validation'
    attempt=output or ROOT/'artifacts'/'ai-screener-local-runtime'/('attempt-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8])
    with exclusive_run(state):
        attempt.mkdir(parents=True,exist_ok=False)
        started=time.monotonic()
        start=datetime.now(UTC).isoformat()
        records=[];server=None;failure=None;status=None
        budget_path=state/'budget.json'
        old_budget_path=ROOT/'artifacts'/'ai-screener-local-first'/'inference-budget.json'
        old_budget=read_manifest(old_budget_path) or {}
        raw_budget=read_manifest(budget_path)
        budget=raw_budget if raw_budget is not None else {'used_seconds':old_budget.get('used_seconds',0),'limit_seconds':LIMIT}
        config_key=None
        selected=[frozen['cases'][i] for i in frozen['pilot_case_indices']] if phase=='pilot' else [c for c in frozen['cases'] if c['split']==phase]
        try:
            if (budget_path.exists() and (raw_budget is None or 'used_seconds' not in raw_budget)) or (
                    old_budget_path.exists() and 'used_seconds' not in old_budget):
                raise ValueError('LOCAL_BENCHMARK_BUDGET_CORRUPT')
            if budget.get('pending') or old_budget.get('pending'):raise ValueError('PRIOR_INFERENCE_OUTCOME_UNKNOWN')
            reserve(dict(budget),'ADMISSION_RESERVE_VALIDATION')
            base=model_manifest(imp_cache_dir(), model_id)
            if not base:raise ValueError('LOCAL_MODEL_MANIFEST_MISSING')
            if base.model_id != model_id:raise ValueError('LOCAL_MODEL_IDENTITY_MISMATCH')
            manifest=apply_profile(base,profile)
            status=readiness(manifest)
            write_json_atomic(attempt/'admission.json',status)
            if status['rejection_reason']:raise ValueError(status['rejection_reason'])
            config={'manifest_hash':frozen['manifest_hash'],'dataset_hash':frozen['dataset_hash'],
                'prompt_hash':frozen['prompt_hash'],'profile':profile,'runtime':manifest.runtime_version,
                'model_id':model_id,'model_revision':manifest.revision,
                'model_hash':status['model_hash'],'max_tokens':frozen['max_tokens'],'temperature':0,
                'runner_version':'local-runtime-benchmark/1.0.0',
                'source_content_hash':semantic_hash({str(p.relative_to(ROOT)):p.read_text(encoding='utf-8') for p in (
                    Path(__file__),ROOT/'src/market_platform_foundation/intelligence/inference/local_provider.py',
                    ROOT/'src/market_platform_foundation/intelligence/inference/local_resources.py',
                    ROOT/'src/market_platform_foundation/intelligence/inference/local_runtime.py',
                    ROOT/'src/market_platform_foundation/intelligence/inference/local_models.py',
                    ROOT/'src/market_platform_foundation/intelligence/inference/inference_identity.py',
                    ROOT/'src/market_platform_foundation/intelligence/inference/local_qualification.py')})}
            config_key=semantic_hash(config)
            config_path=state/(config_key+'.json')
            history=read_manifest(config_path)
            if config_path.exists() and (history is None or history.get('configuration')!=config or
                    type(history.get('development_complete')) is not bool or type(history.get('holdout_consumed')) is not bool):
                raise ValueError('LOCAL_BENCHMARK_CONFIGURATION_CORRUPT')
            history=history or {'configuration':config,'development_complete':False,'holdout_consumed':False}
            if phase=='holdout' and (not history['development_complete'] or history['holdout_consumed']):
                raise ValueError('HOLDOUT_REQUIRES_FROZEN_COMPLETED_DEVELOPMENT_AND_ONCE_ONLY_EXECUTION')
            write_json_atomic(attempt/'configuration.json',config)
            server=LocalLlamaServer(manifest,log_path=attempt/'runtime.log')
            provider=LocalChatInferenceProvider(base_url=server.base_url,model_id=manifest.model_id,server=server,request_model=SERVER_ALIAS)
            qualifier=LocalQualifier(provider,clock=lambda:NOW)
            for case in selected:
                if time.monotonic()-started+RESERVATION>LIMIT-budget['used_seconds']:
                    raise ValueError('CUMULATIVE_TWO_HOUR_CEILING')
                reserve(budget,case['case_id']);write_json_atomic(budget_path,budget)
                if phase=='holdout' and not history['holdout_consumed']:
                    history['holdout_consumed']=True;write_json_atomic(config_path,history)
                t=time.monotonic()
                answer=qualifier.assess(case['scope'],case['candidate'],frozen['cutoff'])
                record={'case_id':case['case_id'],'split':case['split'],'label':case['label'],'scenario':case['scenario'],
                    'evidence_hash':case['evidence_hash'],'elapsed_seconds':time.monotonic()-t,'assessment':answer,
                    'resource_sample':getattr(provider,'last_resource_sample',{}),'context_sample':getattr(provider,'last_context_sample',None)}
                with (attempt/'results.jsonl').open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(record,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())
                records.append(record)
                budget.pop('pending');write_json_atomic(budget_path,budget)
                if answer.get('reason') and any(token in answer['reason'] for token in ('RESOURCE','RUNTIME','TIMEOUT','STOPPED','PINNED','CHECKSUM')):
                    raise ValueError(answer['reason'])
            if phase=='development':
                q=quality_summary(records,len(selected))
                history['development_complete']=q['quality_complete'] and q['failed']==0
                write_json_atomic(config_path,history)
        except (Exception,KeyboardInterrupt) as exc:
            failure=str(exc) or type(exc).__name__
        finally:
            if server:
                try:server.stop()
                except (OSError,subprocess.TimeoutExpired) as exc:
                    failure='LOCAL_RUNTIME_CLEANUP_FAILED:'+type(exc).__name__
                    budget['pending']={'case_id':'CLEANUP_OUTCOME_UNKNOWN','reserved_seconds':RESERVATION}
            elapsed=time.monotonic()-started
            if failure!='LOCAL_BENCHMARK_BUDGET_CORRUPT':
                budget['used_seconds']+=elapsed
                write_json_atomic(budget_path,budget)
            quality=quality_summary(records,len(selected))
            latencies=[r['elapsed_seconds'] for r in records if r['assessment'].get('inference_dispatched')]
            summary={'schema_version':'local-runtime-benchmark/1.0.0','source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'manifest_hash':frozen['manifest_hash'],'dataset_hash':frozen['dataset_hash'],'configuration_hash':config_key,
                'model_id':model_id,'phase':phase,'execution_profile':profile,'started_at':start,'ended_at':datetime.now(UTC).isoformat(),
                'elapsed_seconds':elapsed,'budget':budget,'admission':status,'rejection_reason':failure,'quality':quality,
                'runtime_starts':server.starts if server else 0,'startup_ms':server.last_start_ms if server else None,
                'real_generation_requests':sum(bool(r['assessment'].get('inference_dispatched')) for r in records),
                'observed_latency_seconds':latencies,'throughput_per_minute':60/statistics.mean(latencies) if latencies else None,
                'projected_workloads':[{'rows':n,'projected_seconds':n*statistics.mean(latencies) if latencies else None,
                    'state':'PROJECTED_FROM_SMALL_SAMPLE' if latencies else 'NOT_MEASURED'} for n in (20,50,100,500,4630)],
                'economic_feasibility':economic_plan(records,frozen['cases'],frozen['cutoff']),
                'operational_activation':'OFF','paid_generations':0,'paper_submissions':0,'live_submissions':0}
            if failure and 'RESOURCE' in failure:summary['quality']['quality_status']='LOCAL_MODEL_QUALITY_NOT_PROVEN_RESOURCE_BLOCKED'
            write_json_atomic(attempt/'summary.json',summary)
            pin = MODELS[model_id]
            write_json_atomic(imp_cache_dir()/'benchmarks'/'local-model-observations'/(pin.filename+'.json'),
                {**summary, 'model_hash':pin.sha256,'revision':pin.revision,'attempt_path':str(attempt),
                 'observed_peak_memory':max((r.get('resource_sample',{}).get('peak_process_bytes') or 0 for r in records), default=0) or None})
            print(json.dumps({'attempt':str(attempt),'rejection_reason':failure,'runtime_starts':summary['runtime_starts'],
                              'real_generation_requests':summary['real_generation_requests'],'quality':summary['quality']},indent=2),flush=True)
        return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('pilot','development','holdout'),default='pilot')
    parser.add_argument('--profile',choices=tuple(PROFILES))
    parser.add_argument('--model',choices=tuple(MODELS),default=DEFAULT_MODEL_ID)
    args=parser.parse_args()
    summary=run(phase=args.phase,profile=args.profile,model_id=args.model)
    return 2 if summary['rejection_reason'] else 0


if __name__=='__main__':raise SystemExit(main())
