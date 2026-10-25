"""Replay real past Action Decisions on a local or paid model and grade them with the production validator.

Rebuild step 5 (owner decision 4): pick the free local model and the paid model by evidence, not by name.

``export`` reads the state database READ-ONLY (``mode=ro``) and freezes recent real Action Decision inputs (the
evidence snapshot, selection and context each stored decision carries) to a JSON file. Each case is rebuilt with
the production prompt, and its input hash is recomputed for the model that made it: a case whose hash matches the
stored decision is byte-for-byte the request production built.

``run`` sends every case through the production provider path (``select_synthesis_provider`` for paid engines, the
managed ``llama-server`` for local models) with the production prompt, schema, output bound and timeout, and grades
the answer with ``decode_wire`` + ``parse_proposal`` (accepted or the rejection reason), then ``gate_proposal`` at the
original cutoff (the action it would have led to). Paid runs draw from their own dollar ledger with a hard total
(``--total-usd``): a call that could cross it is refused before it is sent, and the run stops there. Keys are read
from ``--provider-env`` and only their presence is ever reported.

``report`` prints one table and applies the winner rule fixed before any run:
a local candidate replaces Qwen3-4B only if it started within the memory gate, its p95 latency is at most twice
Qwen3-4B's, and its acceptance rate beats Qwen3-4B's by at least 5 points; among those the highest acceptance wins,
then the fastest. The paid pick is the cheapest model per accepted decision whose acceptance is at least the local
winner's (Claude Haiku 5.5 when none qualifies).

Nothing here trades, writes the state database, or changes the engine choice.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

from market_platform_foundation.intelligence.inference.action_decision import (  # noqa: E402
    POLICY_ID, PROMPT_ID, build_conditions, decode_wire, gate_proposal, parse_proposal,
    reasoned_wire_schema as wire_schema,
)
from market_platform_foundation.intelligence.inference.candidate_reduction import ScreenerEvidencePacket  # noqa: E402
from market_platform_foundation.intelligence.inference.config import IntelligenceInferenceConfig  # noqa: E402
from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType  # noqa: E402
from market_platform_foundation.intelligence.inference.hashing import input_hash_from_dict  # noqa: E402
from market_platform_foundation.intelligence.inference.prompts import PromptRegistry  # noqa: E402

SCHEMA = 'ai-decision-benchmark/1.0.0'
BASELINE_MODEL = 'Qwen/Qwen3-4B-GGUF:Q4_K_M'
DEFAULT_PAID_PICK = 'claude-haiku-5-5'
P95_FACTOR = 2.0
ACCEPTANCE_MARGIN_POINTS = 5.0
# A benchmark is a burst well above a trading day's paid traffic; its own ledger caps the dollars.
BENCHMARK_REQUESTS, BENCHMARK_TOKENS = 1_000, 20_000_000


# ------------------------------------------------------------------ export
def _has_news(candidate: dict) -> bool:
    for group in ('current_market_evidence', 'reference_evidence'):
        for item in candidate.get(group, ()):
            if str(item.get('capability', '')).upper() in ('NEWS', 'NEWS_SENTIMENT', 'FILINGS') or \
                    item.get('facts', {}).get('sources'):
                return True
    return False


def rebuild(case: dict) -> dict:
    """The exact production request pieces for a case: data, conditions, schema, rendered prompt, digest."""

    candidate, context, cutoff = case['candidate'], case['context'], case['cutoff']
    conditions = build_conditions(candidate, context, cutoff)
    data = dict(decision_cutoff=cutoff, candidate=candidate, selection=case['selection'], context=context,
                conditions=conditions)
    encoded = json.dumps(data, sort_keys=True, allow_nan=False, separators=(',', ':'))
    schema = wire_schema(candidate, conditions)
    prompt = PromptRegistry().get_by_id(PROMPT_ID)
    rendered = prompt.template.replace('{{evidence_json}}', encoded).replace(
        '{{output_schema}}', json.dumps(schema, separators=(',', ':')))
    return dict(conditions=conditions, schema=schema, rendered=rendered, prompt_hash=prompt.content_hash,
                packet_bytes=len(encoded.encode('utf-8')))


def material_hash(case: dict, *, provider_id: str | None, model_id: str | None, prompt_hash: str) -> str:
    """``ScreenerActionService._build``'s input hash for this case and model."""

    stable = json.loads(json.dumps(case['context']))
    stable['position'].pop('snapshot_at', None)
    stable.pop('forecast_admission', None)
    return input_hash_from_dict(dict(candidate=case['candidate'], candidate_input_hash=case['candidate_input_hash'],
                                     candidate_rank=case['candidate_rank'], context=stable, policy_id=POLICY_ID,
                                     prompt_hash=prompt_hash, provider_id=provider_id, model_id=model_id))


def _case_from_record(record: dict) -> dict | None:
    snapshot = record.get('evidence_snapshot') or {}
    model = record.get('model') or {}
    if not snapshot.get('evidence') or record.get('server_exit') or model.get('latency_ms') is None:
        return None  # a stop-loss exit or a refusal before any model call has nothing to replay
    case = dict(case_id=record['decision_id'], instrument_id=record['instrument_id'], decision_time=record['decision_time'],
                cutoff=snapshot['cutoff'], candidate=snapshot['evidence'], selection=snapshot['selection'],
                context=snapshot['context'], candidate_input_hash=snapshot['candidate_input_hash'],
                candidate_rank=snapshot['candidate_rank'], has_news=_has_news(snapshot['evidence']),
                original=dict(model_id=model.get('model_id'), action_state=record.get('action_state'),
                              blocker_codes=record.get('blocker_codes'), latency_ms=model.get('latency_ms'),
                              tokens_input=model.get('tokens_input'), accepted=record.get('model_proposal') is not None))
    built = rebuild(case)
    # The stored input hash covers the evidence, context and the prompt then in force. With that prompt's hash it
    # proves the inputs are the ones production used; the replay always sends today's production prompt.
    case['input_verified'] = material_hash(case, provider_id=model.get('provider_id'), model_id=model.get('model_id'),
                                           prompt_hash=model.get('prompt_hash')) == record.get('input_hash')
    case['prompt_current'] = built['prompt_hash'] == model.get('prompt_hash')
    case['original_prompt_version'] = model.get('prompt_version')
    case['rebuild_verified'] = case['input_verified'] and case['prompt_current']
    return case


def select_cases(cases: list[dict], count: int) -> list[dict]:
    """A deterministic spread: round-robin over (day, news or not), one instrument at a time, newest first."""

    buckets: dict[tuple[str, bool], list[dict]] = {}
    for case in sorted(cases, key=lambda c: c['decision_time'], reverse=True):
        buckets.setdefault((case['decision_time'][:10], case['has_news']), []).append(case)
    chosen, seen = [], set()
    while len(chosen) < count and any(buckets.values()):
        for key in sorted(buckets, reverse=True):
            bucket = buckets[key]
            if not bucket:
                continue
            index = next((i for i, c in enumerate(bucket) if c['instrument_id'] not in seen), 0)
            case = bucket.pop(index)
            seen.add(case['instrument_id'])
            chosen.append(case)
            if len(chosen) == count:
                break
        if all(c['instrument_id'] in seen for b in buckets.values() for c in b):
            seen.clear()
    return chosen


def export(db: Path, out: Path, *, count: int = 60, limit: int = 5_000) -> dict:
    connection = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True, timeout=10)
    try:
        rows = connection.execute("SELECT payload FROM action_decision_records WHERE kind='decision' "
                                  "ORDER BY decision_time DESC LIMIT ?", (limit,)).fetchall()
    finally:
        connection.close()
    cases = [case for case in (_case_from_record(json.loads(row[0])) for row in rows) if case is not None]
    chosen = select_cases(cases, count)
    payload = dict(schema_version=SCHEMA, exported_at=datetime.now(UTC).isoformat(), source='action_decision_records',
                   source_read_only=True, eligible=len(cases), selected=len(chosen), prompt_id=PROMPT_ID,
                   input_verified=sum(1 for c in chosen if c['input_verified']),
                   rebuild_verified=sum(1 for c in chosen if c['rebuild_verified']), cases=chosen)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding='utf-8')
    return {key: payload[key] for key in ('eligible', 'selected', 'input_verified', 'rebuild_verified')}


# ------------------------------------------------------------------ grading
def grade(case: dict, built: dict, response: Any) -> dict:
    result: dict[str, Any] = dict(case_id=case['case_id'], latency_ms=getattr(response, 'latency_ms', None),
                                  tokens_input=getattr(response, 'tokens_input', None),
                                  tokens_output=getattr(response, 'tokens_output', None))
    timings = (getattr(response, 'diagnostics', None) or {}).get('runtime_timings') or {}
    result['generation_tps'] = timings.get('predicted_per_second')
    result['prompt_tps'] = timings.get('prompt_per_second')
    if response.error_code is not None:
        return dict(result, outcome='PROVIDER_ERROR', reason=response.error_message or response.error_code.value)
    canonical, error = decode_wire(response.raw_text, case['candidate'], built['conditions'])
    if error:
        return dict(result, outcome='INVALID_OUTPUT', reason=error)
    proposal, error = parse_proposal(canonical, case['candidate'], built['conditions'])
    if error:
        return dict(result, outcome='REJECTED', reason=error)
    gated = gate_proposal(proposal, case['candidate'], case['context'], now=case['cutoff'])
    return dict(result, outcome='ACCEPTED', reason=None, proposed_state=proposal.get('proposal_state'),
                action_state=gated.get('action_state'), blockers=gated.get('blocker_codes'))


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))]


def summarize(results: list[dict]) -> dict:
    sent = [r for r in results if r['outcome'] != 'NOT_SENT']
    outcomes = Counter(r['outcome'] for r in sent)
    latencies = [r['latency_ms'] for r in sent if r['outcome'] != 'PROVIDER_ERROR' and r.get('latency_ms') is not None]
    answered = len(sent) - outcomes['PROVIDER_ERROR']
    dollars = sum(r.get('dollars') or 0 for r in sent)
    accepted = outcomes['ACCEPTED']
    tps = [r['generation_tps'] for r in sent if r.get('generation_tps')]
    return dict(cases=len(sent), provider_errors=outcomes['PROVIDER_ERROR'],
                valid_output_pct=round(100 * (accepted + outcomes['REJECTED']) / len(sent), 1) if sent else None,
                accepted=accepted, accepted_pct=round(100 * accepted / len(sent), 1) if sent else None,
                accepted_of_answered_pct=round(100 * accepted / answered, 1) if answered else None,
                rejections=dict(Counter(r['reason'] for r in sent if r['outcome'] in ('REJECTED', 'INVALID_OUTPUT'))),
                provider_error_reasons=dict(Counter(r['reason'] for r in sent if r['outcome'] == 'PROVIDER_ERROR')),
                proposed_states=dict(Counter(r.get('proposed_state') for r in sent if r['outcome'] == 'ACCEPTED')),
                p50_latency_ms=_percentile(latencies, 0.5), p95_latency_ms=_percentile(latencies, 0.95),
                median_generation_tps=round(statistics.median(tps), 1) if tps else None,
                dollars=round(dollars, 6), dollars_per_case=round(dollars / len(sent), 6) if sent else None,
                dollars_per_accepted=round(dollars / accepted, 6) if accepted else None)


# ------------------------------------------------------------------ providers
class GpuMemoryProbe:
    """Polls nvidia-smi once a second for used VRAM; absent nvidia-smi means no reading, never a guess."""

    def __init__(self, run: Callable[..., Any] = subprocess.run) -> None:
        self._run, self.samples, self._stop = run, [], threading.Event()
        self.available = shutil.which('nvidia-smi') is not None
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def read(self) -> int | None:
        if not self.available:
            return None
        try:
            out = self._run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, timeout=10)
            return int(out.stdout.strip().splitlines()[0])
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return None

    def _loop(self) -> None:
        while not self._stop.wait(1.0):
            value = self.read()
            if value is not None:
                self.samples.append(value)

    def __enter__(self):
        self.baseline_mib = self.read()
        if self.available:
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    @property
    def peak_mib(self) -> int | None:
        return max(self.samples) if self.samples else None


def local_provider(model_id: str, *, base_manifest: Path, models_dir: Path | None, log_dir: Path):
    """The managed llama-server for a pinned model, built in memory: no manifest is written."""

    from market_platform_foundation.intelligence.inference.local_models import MODELS
    from market_platform_foundation.intelligence.inference.local_provider import (
        SERVER_ALIAS, LocalChatInferenceProvider, LocalLlamaServer, LocalModelManifest,
    )
    from market_platform_foundation.intelligence.inference.local_runtime import apply_profile

    base = LocalModelManifest.from_dict(json.loads(base_manifest.read_text(encoding='utf-8')))
    if base is None:
        raise ValueError('LOCAL_MANIFEST_UNREADABLE')
    pin = MODELS[model_id]
    if model_id == base.model_id:
        manifest = apply_profile(base, base.execution_profile)
    else:
        found = sorted((models_dir or Path('.')).glob(f'*/{pin.filename}'))
        if not found:
            raise ValueError('LOCAL_MODEL_FILE_NOT_FOUND')
        manifest = apply_profile(LocalModelManifest(base.runtime_path, found[0], model_id, pin.revision,
                                                    base.runtime_version), pin.profile)
    log_dir.mkdir(parents=True, exist_ok=True)
    server = LocalLlamaServer(manifest, log_path=log_dir / f'llama-server-{pin.filename}.log')
    return LocalChatInferenceProvider(base_url=server.base_url, model_id=model_id, server=server,
                                      request_model=SERVER_ALIAS), server


def paid_provider(engine: str, model: str, *, keys: dict[str, str], ledger_dir: Path, total_usd: float):
    """The production paid provider, behind a benchmark-only dollar ledger capped at ``total_usd`` in all."""

    from market_platform_foundation.intelligence.inference.local_provider import select_synthesis_provider

    settings = {'IMP_PAID_AI_DAILY_USD': f'{total_usd:.2f}', 'IMP_PAID_AI_MONTHLY_USD': f'{total_usd:.2f}',
                'IMP_SYNTHESIS_DAILY_REQUESTS': str(BENCHMARK_REQUESTS),
                'IMP_SYNTHESIS_DAILY_TOKENS': str(BENCHMARK_TOKENS), **keys}
    selection = select_synthesis_provider(settings.get, cache_dir=ledger_dir, engine=engine, model=model)
    return selection.provider, selection.reason


def read_keys(path: Path | None) -> dict[str, str]:
    """The three paid keys from a provider file. Values stay in memory; only names are ever reported."""

    if path is None or not path.is_file():
        return {}
    from market_platform_foundation.ui_api.operator_config import _read_values

    values = _read_values(path)
    return {name: values[name] for name in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY')
            if (values.get(name) or '').strip()}


# ------------------------------------------------------------------ run
def run_cases(cases: list[dict], provider: Any, *, local: bool, ledger: Any = None,
              should_continue: Callable[[], bool] = lambda: True) -> tuple[list[dict], str | None]:
    """Each case once through the production request path. Returns (results, why the run stopped early)."""

    results, stopped = [], None
    for case in cases:
        if not should_continue():
            stopped = 'STOPPED'
            break
        built = rebuild(case)
        config = IntelligenceInferenceConfig(prompt_id=PROMPT_ID, default_task_type=IntelligenceTaskType.SCREENER_ACTION_DECISION,
                                             max_tokens=2000, timeout_seconds=300 if local else 45)
        packet = ScreenerEvidencePacket(IntelligenceTaskType.SCREENER_ACTION_DECISION, 'BENCH-' + case['case_id'],
                                        built['prompt_hash'], case['cutoff'], case['context'], [case['candidate']],
                                        built['schema'])
        before = ledger.status() if ledger is not None else None
        response = provider.infer(packet, rendered_prompt=built['rendered'], config=config)
        result = grade(case, built, response)
        if ledger is not None:
            after = ledger.status()
            result['dollars'] = round(after['spent_month_usd'] - before['spent_month_usd'], 6)
        if local:
            sample = getattr(provider, 'last_resource_sample', None) or {}
            result['peak_process_bytes'] = sample.get('peak_process_bytes')
        if result['outcome'] == 'PROVIDER_ERROR' and str(result['reason']).startswith(('PAID_AI_', 'PAID_MODEL_')):
            # The dollar cap refused the call before it was sent: nothing was spent, and the run ends here.
            results.append(dict(result, outcome='NOT_SENT'))
            stopped = result['reason']
            break
        results.append(result)
    return results, stopped


def _slug(text: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '.-' else '_' for ch in text)


def run(args) -> dict:
    payload = json.loads(Path(args.cases).read_text(encoding='utf-8'))
    cases = payload['cases'][:args.limit] if args.limit else payload['cases']
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = dict(schema_version=SCHEMA, engine=args.engine, model=args.model,
                                  started_at=datetime.now(UTC).isoformat(), cases_file=str(args.cases))
    if args.engine == 'local':
        provider, server = local_provider(args.model, base_manifest=Path(args.base_manifest),
                                          models_dir=Path(args.models_dir) if args.models_dir else None,
                                          log_dir=out / 'logs')
        with GpuMemoryProbe() as probe:
            try:
                started = time.monotonic()
                reason = server.ensure_running()
                record.update(start_reason=reason, start_ms=round((time.monotonic() - started) * 1000),
                              load_ms=server.last_start_ms, preread=server.last_preread,
                              readiness={k: (server.last_readiness or {}).get(k) for k in (
                                  'execution_profile', 'estimated_peak_memory', 'estimated_gpu_memory',
                                  'cpu_moe_layers', 'process_limit_bytes', 'rejection_reason')},
                              gpu_fallback=server.gpu_fallback, profile=server.manifest.execution_profile)
                results, stopped = ([], reason) if reason else run_cases(cases, provider, local=True)
            finally:
                server.stop()
            record.update(vram_baseline_mib=probe.baseline_mib, vram_peak_mib=probe.peak_mib)
        record['peak_process_bytes'] = max((r.get('peak_process_bytes') or 0 for r in results), default=0) or None
    else:
        keys = read_keys(Path(args.provider_env) if args.provider_env else None)
        from market_platform_foundation.intelligence.inference.synthesis_engines import ENGINE_SPECS

        credential = ENGINE_SPECS[args.engine].credential_env
        record['key_present'] = credential in keys
        if credential not in keys:
            record.update(skipped=True, reason=f'{credential}_NOT_SET', results=[], summary=summarize([]))
            (out / f'{_slug(args.engine)}--{_slug(args.model)}.json').write_text(json.dumps(record, indent=1), encoding='utf-8')
            return {'skipped': True, 'reason': record['reason']}
        provider, reason = paid_provider(args.engine, args.model, keys=keys, ledger_dir=Path(args.ledger_dir),
                                         total_usd=args.total_usd)
        if provider is None:
            results, stopped = [], reason
        else:
            results, stopped = run_cases(cases, provider, local=False, ledger=provider.ledger)
            record['ledger_after'] = provider.ledger.status()
    record.update(finished_at=datetime.now(UTC).isoformat(), stopped=stopped, results=results,
                  summary=summarize(results))
    path = out / f'{_slug(args.engine)}--{_slug(args.model)}.json'
    path.write_text(json.dumps(record, indent=1, sort_keys=True), encoding='utf-8')
    return {'file': str(path), 'stopped': stopped, **record['summary']}


# ------------------------------------------------------------------ report
def pick_local(runs: list[dict]) -> tuple[str, list[str]]:
    """The winner rule; returns (model, plain reasons per candidate)."""

    local = {r['model']: r for r in runs if r['engine'] == 'local'}
    base = local.get(BASELINE_MODEL)
    if base is None or base['summary']['accepted_pct'] is None:
        return BASELINE_MODEL, ['Qwen3-4B has no result, so it stays.']
    notes, passing = [], []
    for model, item in local.items():
        if model == BASELINE_MODEL:
            continue
        s = item['summary']
        if item.get('start_reason'):
            notes.append(f'{model}: did not start ({item["start_reason"]}).')
            continue
        slow = (s['p95_latency_ms'] or math.inf) > P95_FACTOR * (base['summary']['p95_latency_ms'] or 0)
        better = (s['accepted_pct'] or 0) >= (base['summary']['accepted_pct'] or 0) + ACCEPTANCE_MARGIN_POINTS
        if slow:
            notes.append(f'{model}: p95 latency over {P95_FACTOR:g}x Qwen3-4B.')
        elif not better:
            notes.append(f'{model}: acceptance not {ACCEPTANCE_MARGIN_POINTS:g} points above Qwen3-4B.')
        else:
            passing.append(item)
            notes.append(f'{model}: passes the rule.')
    if not passing:
        return BASELINE_MODEL, notes
    best = max(passing, key=lambda r: (r['summary']['accepted_pct'], -(r['summary']['p50_latency_ms'] or math.inf)))
    return best['model'], notes


def pick_paid(runs: list[dict], local_accepted_pct: float | None) -> str:
    candidates = [r for r in runs if r['engine'] != 'local' and not r.get('skipped')
                  and r['summary']['dollars_per_accepted'] is not None
                  and (r['summary']['accepted_pct'] or 0) >= (local_accepted_pct or 0)]
    if not candidates:
        return DEFAULT_PAID_PICK
    return min(candidates, key=lambda r: r['summary']['dollars_per_accepted'])['model']


REFERENCE_MODELS = ('claude-sonnet-5-5', 'claude-haiku-5-5')


def agreement(run: dict, reference: dict) -> tuple[int, int]:
    """(same proposed state, cases both accepted) between two runs over the same frozen cases."""

    theirs = {r['case_id']: r.get('proposed_state') for r in reference['results'] if r['outcome'] == 'ACCEPTED'}
    ours = {r['case_id']: r.get('proposed_state') for r in run['results'] if r['outcome'] == 'ACCEPTED'}
    both = theirs.keys() & ours.keys()
    return sum(1 for case in both if theirs[case] == ours[case]), len(both)


def agreement_lines(runs: list[dict]) -> list[str]:
    lines = []
    for name in REFERENCE_MODELS:
        reference = next((r for r in runs if r['model'] == name and r.get('results')), None)
        if reference is None:
            continue
        for run in runs:
            if run is reference or not run.get('results'):
                continue
            same, both = agreement(run, reference)
            if both:
                lines.append(f'- {run["model"]} vs {name}: {same} of {both} ({round(100 * same / both)}%)')
    return lines


def load_runs(results_dir: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(results_dir.glob('*--*.json'))]


def publish(runs: list[dict], cache_dir: Path) -> Path:
    """The summary the Setup card shows (``setup_ai.BENCHMARK_RELATIVE``). Results only: it selects nothing."""

    from market_platform_foundation.local_state.external_cache import write_json_atomic
    from market_platform_foundation.ui_api.setup_ai import BENCHMARK_RELATIVE

    winner, notes = pick_local(runs)
    winner_pct = next((r['summary']['accepted_pct'] for r in runs if r['engine'] == 'local' and r['model'] == winner), None)
    keep = ('cases', 'accepted_pct', 'valid_output_pct', 'p50_latency_ms', 'p95_latency_ms', 'median_generation_tps',
            'dollars_per_case', 'dollars_per_accepted')
    payload = dict(schema_version=SCHEMA, generated_at=datetime.now(UTC).isoformat(), local_winner=winner,
                   local_notes=notes, paid_pick=pick_paid(runs, winner_pct), paid_stays_off=True,
                   runs=[dict(engine=r['engine'], model=r['model'], skipped=bool(r.get('skipped')), reason=r.get('reason'),
                              start_reason=r.get('start_reason'), vram_peak_mib=r.get('vram_peak_mib'),
                              **{k: r['summary'].get(k) for k in keep}) for r in runs])
    path = cache_dir / BENCHMARK_RELATIVE
    write_json_atomic(path, payload)
    return path


def report(results_dir: Path) -> str:
    runs = load_runs(results_dir)
    lines = ['| Engine | Model | Cases | Accepted | Valid output | p50 / p95 latency | Gen tok/s | Peak VRAM | Dollars | $ per accepted | Top rejections |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in runs:
        s = r['summary']
        if r.get('skipped'):
            lines.append(f"| {r['engine']} | {r['model']} | skipped: {r['reason']} | | | | | | | | |")
            continue
        top = ', '.join(f'{k} {v}' for k, v in Counter({**s['rejections'], **s['provider_error_reasons']}).most_common(3))
        latency = (f"{(s['p50_latency_ms'] or 0)/1000:.1f} / {(s['p95_latency_ms'] or 0)/1000:.1f} s"
                   if s['p50_latency_ms'] is not None else '-')
        vram = f"{r['vram_peak_mib']} MiB" if r.get('vram_peak_mib') else '-'
        start = f" (not started: {r['start_reason']})" if r.get('start_reason') else ''
        lines.append(f"| {r['engine']} | {r['model']}{start} | {s['cases']} | {s['accepted']} ({s['accepted_pct']}%) | "
                     f"{s['valid_output_pct']}% | {latency} | {s['median_generation_tps'] or '-'} | {vram} | "
                     f"${s['dollars']:.4f} | {('$%.4f' % s['dollars_per_accepted']) if s['dollars_per_accepted'] else '-'} | {top} |")
    agreement = agreement_lines(runs)
    if agreement:
        lines += ['', 'Same proposal as a reference model on the cases both answered (informational; not part of the rule):',
                  *agreement]
    winner, notes = pick_local(runs)
    winner_pct = next((r['summary']['accepted_pct'] for r in runs if r['engine'] == 'local' and r['model'] == winner), None)
    paid_total = sum(r['summary']['dollars'] for r in runs if r['engine'] != 'local')
    lines += ['', f'Local winner: **{winner}**' + (' (Qwen3-4B stays)' if winner == BASELINE_MODEL else ''),
              *[f'- {note}' for note in notes], '',
              f'Paid pick (preselected, paid stays off): **{pick_paid(runs, winner_pct)}**',
              f'Paid dollars spent in total: ${paid_total:.4f}']
    return '\n'.join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    e = sub.add_parser('export')
    e.add_argument('--db', required=True)
    e.add_argument('--out', required=True)
    e.add_argument('--count', type=int, default=60)
    r = sub.add_parser('run')
    r.add_argument('--cases', required=True)
    r.add_argument('--engine', choices=('local', 'anthropic', 'openai', 'gemini'), required=True)
    r.add_argument('--model', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--limit', type=int, default=0)
    r.add_argument('--base-manifest', help='local: the installed local-llm.json (runtime and Qwen3-4B paths)')
    r.add_argument('--models-dir', help='local: folder holding <repo>/<file>.gguf for the other pins')
    r.add_argument('--provider-env', help='paid: provider file holding the keys (values are never printed)')
    r.add_argument('--ledger-dir', help='paid: benchmark-only cache folder for the dollar ledger')
    r.add_argument('--total-usd', type=float, default=3.0)
    p = sub.add_parser('report')
    p.add_argument('--results', required=True)
    p.add_argument('--publish', help='IMP cache folder: also write the summary the Setup card shows')
    args = parser.parse_args(argv)
    if args.command == 'export':
        print(json.dumps(export(Path(args.db), Path(args.out), count=args.count)))
    elif args.command == 'run':
        if args.engine != 'local' and not args.ledger_dir:
            parser.error('--ledger-dir is required for a paid run')
        print(json.dumps(run(args), sort_keys=True))
    else:
        print(report(Path(args.results)))
        if args.publish:
            print(f'Published {publish(load_runs(Path(args.results)), Path(args.publish))}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
