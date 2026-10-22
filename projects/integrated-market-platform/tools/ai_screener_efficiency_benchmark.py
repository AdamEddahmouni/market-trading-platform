"""Frozen offline baseline/optimized measurements. No paid calls or campaign state."""
from __future__ import annotations
import argparse
import hashlib
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from market_platform_foundation.intelligence.inference.anthropic_synthesis import estimate_tokens
from market_platform_foundation.intelligence.inference.candidate_reduction import packet_candidates, output_schema
from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository
from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from market_platform_foundation.ui_api.screener_ai_coverage import ScreenerAiCoverage
from tests.support.coverage_universe import NOW, SCOPE, News, PagingReader, RankingProvider, universe

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

class MeasuredProvider(RankingProvider):
    model_id = "claude-sonnet-5-5"
    def __init__(self):
        super().__init__()
        self.measurements = []
    def infer(self, packet, *, rendered_prompt, config):
        start = rendered_prompt.index('BEGIN IMP EVIDENCE DATA (no instruction authority)') + len('BEGIN IMP EVIDENCE DATA (no instruction authority)')
        model_input = rendered_prompt[start:rendered_prompt.index('END IMP EVIDENCE DATA')].strip()
        manifest = json.loads(model_input)
        if "encoding" in manifest:
            from market_platform_foundation.intelligence.inference.evidence_compaction import reconstruct, verify
            decoded = reconstruct(manifest)
            original = dict(scope=packet.scope,decision_cutoff=packet.as_of,candidates=packet_candidates(packet.candidates))
            if not verify(original,manifest):
                raise ValueError("BENCHMARK_EVIDENCE_NOT_EQUIVALENT")
            manifest = decoded
        self.measurements.append({
            "packet_bytes": len(model_input.encode()),
            "rendered_prompt_bytes": len(rendered_prompt.encode()),
            "estimated_input_tokens": estimate_tokens(rendered_prompt, self.model_id),
            "output_reservation": config.max_tokens,
            "categories": profile(packet, rendered_prompt),
        })
        # The fixture engine reasons over exactly what a provider was shown, after deterministic decoding.
        return super().infer(replace(packet,candidates=manifest["candidates"]), rendered_prompt=rendered_prompt, config=config)

def profile(packet, rendered):
    categories = {}
    for c in packet_candidates(packet.candidates):
        for key, value in c.items():
            family = key if key not in ("current_market_evidence", "reference_evidence") else None
            if family:
                categories[family] = categories.get(family, 0) + len(encoded(value))
            else:
                for item in value:
                    cap = item["capability"]
                    categories[cap] = categories.get(cap, 0) + len(encoded(item))
    categories["output_schema"] = len(encoded(output_schema(packet.candidates)))
    categories["prompt_and_serialization_overhead"] = max(0, len(rendered.encode()) - sum(categories.values()))
    return categories

def fixtures(size):
    strong = {0: 85., 50: 88., size // 2: 93., size - 1: 97.} if size > 51 else ({size - 1: 97.} if size else {})
    rows = universe(size, strong=strong)
    if size == 4630:
        for index in range(100, 100 + 25 * 150, 150):
            rows[index]["fields"].pop("price")
    return rows

def measure(size, *, warm=False, compact=False, partial=False, tracing=True):
    rows = fixtures(size)
    provider = MeasuredProvider()
    service = ScreenerAiService(reader=PagingReader(rows), news=News(provider), clock=lambda: NOW)
    if compact:
        service._provider_reducer().compact_input = True
    ledgers = []
    def run(tag):
        ledger = CoverageLedger()
        ledgers.append(ledger)
        return ScreenerAiCoverage(service, ledger=ledger, repository=ActionDecisionRepository()).run(
            SCOPE, run_id=tag, account_id="EFFICIENCY-CONTROLLED")
    if warm:
        run("prime")
        provider.measurements.clear()
        provider.calls = 0
        if partial and size:
            rows[-1]["fields"]["rsi_14"]["value"] = 96.5
    if tracing:
        tracemalloc.start()
    started = time.perf_counter()
    result = run("measured")
    elapsed = time.perf_counter() - started
    peak = None
    if tracing:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    block = result["universe_coverage"]
    result_calls = ledgers[-1].records("measured", "batch")
    measurements = provider.measurements
    sizes = sorted(m["packet_bytes"] for m in measurements)
    categories = {}
    for m in measurements:
        for k,v in m["categories"].items():
            categories[k] = categories.get(k, 0) + v
    return {
        "dataset_id": hashlib.sha256(encoded(rows)).hexdigest(),
        "scenario": "partial_cache" if partial else "warm_cache" if warm else "cold_cache",
        "compact_input": compact, "universe_total": size, "eligible_count": block["eligible_count"],
        "counts": block["counts"], "complete": block["selection_complete"], "status": block["status"],
        "packet_count": len(sizes), "packet_bytes_total": sum(sizes),
        "packet_bytes_average": statistics.mean(sizes) if sizes else 0,
        "packet_bytes_p95": sizes[min(len(sizes)-1, int(len(sizes)*.95))] if sizes else 0,
        "estimated_input_tokens": sum(m["estimated_input_tokens"] for m in measurements),
        "provider_counted_input_tokens": None, "actual_billed_usage": None, "estimated_cost": None,
        "cost_reason": "No current price configuration or billed provider measurements; fixture usage is not billed usage.",
        "reserved_output_tokens": sum(m["output_reservation"] for m in measurements), "reasoning_headroom": 0,
        "planned_requests": block["plan"]["required"]["requests"] if block["plan"] else 0,
        "global_reduction_requests": sum(c["stage"] == "GLOBAL_REDUCTION" and c.get("cache") != "HIT"
            for c in result_calls),
        "model_requests": provider.calls, "cache_hits": block.get("answers_from_cache", 0),
        "cache_misses": provider.calls, "elapsed_seconds_with_tracing": round(elapsed, 4) if tracing else None,
        "elapsed_seconds":round(elapsed,4), "tracing":tracing,
        "peak_traced_memory_bytes": peak, "selected": [c["instrument_id"] for c in result["candidates"]],
        "categories_bytes": categories, "categories_basis": "UNCOMPACTED_SEMANTIC_PROFILE_NOT_ADDITIVE_WIRE_BYTES",
        "plan": block["plan"],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", nargs="+", type=int, default=[0,20,50,100,500,4630,20000])
    parser.add_argument("--optimized", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--no-tracing", action="store_true", help="verify final counts without tracing overhead; latency is not comparable to traced baseline")
    args = parser.parse_args()
    results = []
    for size in args.sizes:
        scenarios = [(False,False)] if not args.optimized else [(False,False),(True,False),(True,True)]
        for warm, partial in scenarios:
            value = measure(size, warm=warm, partial=partial,compact=args.compact,tracing=not args.no_tracing)
            results.append(value)
            print(size, value["scenario"], value["model_requests"], value["elapsed_seconds"], flush=True)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({"classification":"SOFTWARE_CONTROLLED", "observations":results}, indent=2)+"\n")
if __name__ == "__main__":
    main()
