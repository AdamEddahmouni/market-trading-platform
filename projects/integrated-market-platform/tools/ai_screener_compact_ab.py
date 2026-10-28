"""Matched quality A/B for IMP_AI_SCREENER_COMPACT_INPUT on the real local model. Read-only on the state store.

Each sampled request is a stored coverage-ledger manifest (the exact canonical packet a live run sent). It is sent
twice through the production ``CandidateReducer`` -- uncompacted (prompt v3) and compacted (prompt v4) -- to the
same loopback llama-server, and both answers go through the production parser and grounding gates. Requests are
sent one at a time and only while no Paper universe run is active, so the live controller keeps the single slot.
Nothing is written to the store; results go to ``--output``.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from market_platform_foundation.intelligence.inference.candidate_reduction import CandidateReducer  # noqa: E402
from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider  # noqa: E402
from market_platform_foundation.local_state.payload_codec import PayloadCodec  # noqa: E402

RUN_OPEN = 'UNIVERSE_RUN_STARTED'
RUN_CLOSED = ('UNIVERSE_RUN_FINISHED', 'UNIVERSE_RUN_INTERRUPTED', 'UNIVERSE_RUN_BLOCKED', 'UNIVERSE_RUN_SKIPPED')


class AttachedServer:
    """The already-running live llama-server: never started or stopped here; its window drives exact admission."""

    def __init__(self, context: int) -> None:
        # No revision/runtime version: the reducer then never reuses a cached answer, so every arm is a real call.
        self.manifest = SimpleNamespace(context=context, revision=None, runtime_version=None)

    def ensure_running(self) -> None:
        return None

    def touch(self) -> None:
        """The live server's idle timer belongs to its owner; nothing to record here."""


def readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)


def live_run_active(state: Path) -> bool:
    with readonly(state) as db:
        row = db.execute("SELECT kind FROM paper_automation_events WHERE kind IN (?,?,?,?,?) ORDER BY sequence DESC LIMIT 1",
                         (RUN_OPEN, *RUN_CLOSED)).fetchone()
    return row is not None and row[0] == RUN_OPEN


def samples(state: Path, count: int, scan_runs: int, per_run: int) -> list[dict]:
    """The newest manifests whose live call reached the model (a MISS with recorded tokens), one per call."""
    picked = []
    with readonly(state) as db:
        codec = PayloadCodec(db)
        runs = [r for (r,) in db.execute("SELECT run_id FROM ai_screener_coverage_records WHERE kind='run' "
                                         "ORDER BY rowid DESC LIMIT ?", (scan_runs,))]
        for run_id in runs:
            batches = {}
            for (payload,) in db.execute("SELECT payload FROM ai_screener_coverage_records WHERE run_id=? AND kind='batch'", (run_id,)):
                batch = json.loads(codec.decode(payload))
                if batch.get('cache') == 'MISS' and batch.get('tokens_input'):
                    batches[batch['call_id']] = batch
            taken = 0
            for (payload,) in db.execute("SELECT payload FROM ai_screener_coverage_records WHERE run_id=? AND kind='manifest' "
                                         "ORDER BY seq", (run_id,)):
                manifest = json.loads(codec.decode(payload))
                live = batches.get(manifest['call_id'])
                if live is None:
                    continue
                canonical = manifest['canonical']
                canonical = json.loads(canonical) if isinstance(canonical, str) else canonical
                picked.append(dict(run_id=run_id, call_id=manifest['call_id'], canonical=canonical, live=live))
                taken += 1
                if taken >= per_run:
                    break
                if len(picked) >= count:
                    return picked
    return picked


def unprojected(candidates: list[dict]) -> list[dict]:
    """Undo ``packet_candidates``: the reducer re-adds the packet-local wire indices itself."""
    out = []
    for c in candidates:
        item = {k: v for k, v in c.items() if k != 'candidate_key'}
        for name in ('current_market_evidence', 'reference_evidence'):
            item[name] = [{k: v for k, v in e.items() if k != 'reference_index'} for e in c[name]]
        out.append(item)
    return out


def arm(provider, sample: dict, compact: bool) -> dict:
    canonical = sample['canonical']
    cutoff = datetime.fromisoformat(canonical['decision_cutoff'].replace('Z', '+00:00')).timestamp()
    # The request is judged at its own cutoff, so evidence freshness gates match the live call.
    reducer = CandidateReducer(provider=provider, clock=lambda: cutoff, compact_input=compact)
    started = time.perf_counter()
    result = reducer.reduce(canonical['scope'], unprojected(canonical['candidates']), canonical['decision_cutoff'])
    return dict(compact=compact, prompt_id=result.get('prompt_id'), state=result.get('state'), reason=result.get('reason'),
                selected=[p['instrument_id'] for p in result.get('candidates') or []],
                packet_bytes=result.get('packet_bytes'), tokens_input=result.get('tokens_input'),
                tokens_output=result.get('tokens_output'), latency_ms=result.get('latency_ms'),
                wall_ms=round((time.perf_counter() - started) * 1000), validation=result.get('validation'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:18089')
    parser.add_argument('--model-id', default='Qwen/Qwen3-4B-GGUF:Q4_K_M')
    parser.add_argument('--request-model', default='imp-local-synthesis')
    parser.add_argument('--context', type=int, default=8192, help='the live server\'s -c value')
    parser.add_argument('--count', type=int, default=30)
    parser.add_argument('--scan-runs', type=int, default=60)
    parser.add_argument('--per-run', type=int, default=2, help='spread samples across runs and stages')
    parser.add_argument('--max-wait-seconds', type=int, default=900, help='give up waiting for an idle gap after this long')
    args = parser.parse_args()
    provider = LocalChatInferenceProvider(base_url=args.base_url, model_id=args.model_id, request_model=args.request_model,
                                          server=AttachedServer(args.context))
    chosen = samples(args.state, args.count, args.scan_runs, args.per_run)[:args.count]
    results = []
    for index, sample in enumerate(chosen, 1):
        pair = dict(run_id=sample['run_id'], call_id=sample['call_id'], candidates=len(sample['canonical']['candidates']),
                    live=dict(state=sample['live'].get('state'), reason=sample['live'].get('reason'),
                              selected=[p['instrument_id'] for p in sample['live'].get('selected') or []],
                              tokens_input=sample['live'].get('tokens_input'), stage=sample['live'].get('stage')))
        # Alternate the order so neither arm always runs on a warm prompt cache.
        for compact in ((False, True) if index % 2 else (True, False)):
            waited = time.monotonic()
            while live_run_active(args.state):
                if time.monotonic() - waited > args.max_wait_seconds:
                    pair['aborted'] = 'NO_IDLE_GAP'
                    break
                time.sleep(5)
            if pair.get('aborted'):
                break
            pair['compact' if compact else 'normal'] = arm(provider, sample, compact)
        results.append(pair)
        args.output.write_text(json.dumps(dict(generated_at=datetime.now().astimezone().isoformat(), samples=len(chosen),
                                               results=results), indent=1), encoding='utf-8')
        print(f"{index}/{len(chosen)} {pair['call_id'][:12]} normal={pair.get('normal', {}).get('state')} "
              f"compact={pair.get('compact', {}).get('state')}", flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
