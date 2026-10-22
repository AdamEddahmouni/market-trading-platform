"""Receipt for full-universe AI Screener coverage: accounting, batching, budget, failure states, scale.

Offline by default and SOFTWARE_CONTROLLED throughout: controlled Screener rows, a controlled engine, the
production enumeration, classification, planning, reducer, budget and ledger code. It reads no market, runs no
workflow, generates nothing with a paid model and writes nothing but the receipt.

Every number in the receipt is measured by this run or copied, with its source named, from a historical
receipt that this tool does not modify.

``--probe`` adds one free provider request per selectable Claude model: the token-count endpoint on one
controlled batch. It bills nothing and generates nothing. No option of this tool makes a generation request.

``--validation FILE`` embeds validation totals recorded from the exact-head validation runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.inference.anthropic_models import TOOL_NAME  # noqa: E402
from market_platform_foundation.intelligence.inference.anthropic_synthesis import (  # noqa: E402
    BYTES_PER_TOKEN, DEFAULT_DAILY_REQUESTS, DEFAULT_DAILY_TOKENS, AnthropicSynthesisProvider, BudgetedProvider, DailyBudget,
    estimate_tokens,
)
from market_platform_foundation.intelligence.inference.candidate_reduction import (  # noqa: E402
    MAX_INTAKE, MAX_PACKET_BYTES, MAX_SELECTED, PROMPT_ID, SCHEMA_VERSION, WIRE_SCHEMA_VERSION, CandidateReducer,
)
from market_platform_foundation.intelligence.inference.coverage_plan import (  # noqa: E402
    INTAKE_METHOD_VERSION, METHOD_NAME, METHOD_VERSION, reduction_rounds,
)
from market_platform_foundation.intelligence.inference.provider import ANTHROPIC_API_URL  # noqa: E402
from market_platform_foundation.intelligence.inference.synthesis_engines import ENGINE_SPECS  # noqa: E402
from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository  # noqa: E402
from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger  # noqa: E402
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService  # noqa: E402
from market_platform_foundation.ui_api.screener_ai_coverage import PLAN_DRIFT_MARGIN, ScreenerAiCoverage  # noqa: E402

RECEIPT = ROOT / "artifacts" / "ai-screener-full-universe-acceptance.json"
OCTOBER_7 = {
    "universe_rows": {"value": 4630, "source": "artifacts/oct1-13-premarket-operational.json"},
    "provider_count_packet_bytes": {"value": 319719, "source": "artifacts/ai-screener-provider-contract-closure.json"},
    "provider_counted_input_tokens": {"source": "docs/engineering/WORK_LOG.md (PR 484 controlled count_tokens, no generation)",
                                      "claude-haiku-4-5-20251001": 120235, "claude-sonnet-5-5": 177826, "claude-opus-5-5": 177826},
    "historical_receipts": ["artifacts/oct1-13-pre-rth-readiness.json", "artifacts/oct1-13-premarket-operational.json",
                            "artifacts/ai-screener-provider-contract-closure.json"],
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixtures():
    from tests.support import coverage_universe as support

    return support


def run_controlled(rows, provider=None, *, should_stop=lambda: False, reader=None, repository=None, tag="acc", clock=None):
    support = fixtures()
    provider = provider if provider is not None else support.RankingProvider()
    reader = reader or support.PagingReader(rows)
    service = ScreenerAiService(reader=reader, news=support.News(provider), clock=clock or (lambda: support.NOW))
    ledger = CoverageLedger()
    repository = repository if repository is not None else ActionDecisionRepository()
    result = ScreenerAiCoverage(service, ledger=ledger, software_sha=git("rev-parse", "HEAD"), repository=repository).run(
        support.SCOPE, run_id=f"{tag}-{time.perf_counter_ns()}", account_id="PAPER-ACCEPTANCE", should_stop=should_stop)
    return result, ledger, provider, service, repository


def scale(sizes: list[int]) -> list[dict]:
    """Timing and memory of the whole controlled run at each universe size. The engine answers in memory, so
    model latency is absent: these are the deterministic costs only."""
    support = fixtures()
    rows_out = []
    for size in sizes:
        strong = {size - 1: 97.0} if size else {}
        rows = support.universe(size, strong=strong)
        # Timed without instrumentation, then repeated under tracemalloc for the peak: tracing slows a run several times.
        started = time.perf_counter()
        result, ledger, provider, _, _ = run_controlled(rows, tag=f"scale{size}")
        elapsed = time.perf_counter() - started
        tracemalloc.start()
        run_controlled(support.universe(size, strong=strong), tag=f"memory{size}")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        block = result["universe_coverage"]
        timings = block["timings_ms"]
        counts = block["counts"]
        eligibility = timings.get("eligibility_ms")
        rows_out.append({
            "universe_rows": size, "status": block["status"], "enumeration_pages": block["enumeration"].get("pages"),
            "assessed": block["assessed_count"], "eligible": block["eligible_count"], "ai_evaluated": counts["evaluated"],
            "primary_row_states": {key: counts[key] for key in ("evaluated", "ineligible", "evidence_blocked", "unprocessed")},
            "classification_counts": counts["by_class"],
            "reconciled": block["reconciled"], "coverage_complete": block["coverage_complete"],
            "selection_complete": block["selection_complete"], "batches_planned": block["batches_planned"],
            "batches_completed": block["batches_completed"], "batch_rows_max": (block["plan"] or {}).get("batch_rows_max"),
            "batch_rows_average": (block["plan"] or {}).get("batch_rows_average"),
            "packet_bytes_max": (block["plan"] or {}).get("packet_bytes_max"),
            "reduction_rounds_planned": (block["plan"] or {}).get("reduction_rounds_planned"),
            "model_calls": block["model_calls"], "largest_request_rows": max((len(seen) for seen in provider.seen), default=0),
            "last_row_selected": bool(size) and [p["instrument_id"] for p in result["candidates"]] == [support.instrument_id(size - 1)],
            "timings_ms": timings, "total_seconds": round(elapsed, 3),
            "eligibility_rows_per_second": round(size / (eligibility / 1000)) if eligibility else None,
            "peak_traced_memory_mib": round(peak / 1048576, 2),
            "ledger_records": len(ledger.records(result["universe_coverage"]["coverage_run_id"])),
        })
    return rows_out


def october_7_replay() -> dict:
    """The recorded October 7 universe size under the method that ran that day and under this one.

    Rows are controlled; only the counts are taken from the historical receipts. This is not market evidence."""
    support = fixtures()
    size = OCTOBER_7["universe_rows"]["value"]
    late = {50: 88.0, size // 2: 93.0, size - 1: 97.0}
    rows = support.universe(size, strong=late)
    # 25 rows carried no vendor price that morning (4,630 admitted, 4,605 returned by the snapshot).
    unpriced = [index for index in range(100, 100 + 25 * 150, 150)]
    for index in unpriced:
        rows[index]["fields"].pop("price")
    expected = [support.instrument_id(index) for index, _ in sorted(late.items(), key=lambda item: -item[1])]

    old_provider = support.RankingProvider()
    old_reader = support.PagingReader(rows)
    old = ScreenerAiService(reader=old_reader, news=support.News(old_provider), clock=lambda: support.NOW).run(support.SCOPE)
    old_seen = {value for seen in old_provider.seen for value in seen}

    result, ledger, provider, _, repository = run_controlled(rows, tag="oct7")
    block = result["universe_coverage"]
    seen = {value for call in ledger.records(block["coverage_run_id"], "batch") if call["stage"] == "BATCH_INFERENCE"
            for value in call["instrument_ids"]}
    return {
        "classification": "CONTROLLED_REPLAY_OF_2026_10_07",
        "note": "Controlled rows and a controlled engine; only the row counts come from the October 7 receipts, which are unchanged.",
        "inputs_from_history": OCTOBER_7,
        "historical_receipt_sha256": {path: sha256(ROOT / path) for path in OCTOBER_7["historical_receipts"]},
        "controlled_strong_positions": sorted(late), "rows_without_a_price": len(unpriced),
        "old_method": {
            "method_version": INTAKE_METHOD_VERSION, "rows_read": old_reader.calls[-1]["limit"], "intake_count": old["intake_count"],
            "matched_count": old["matched_count"], "model_calls": old_provider.calls, "rows_seen_by_model": len(old_seen),
            "late_rows_seen_by_model": sum(support.instrument_id(index) in old_seen for index in late),
            "selected": [pick["instrument_id"] for pick in old["candidates"]],
            "share_of_universe_seen_pct": round(100 * len(old_seen) / size, 2),
            "october_7_intake_bound_at_the_time": 20,
        },
        "new_method": {
            "method_version": METHOD_VERSION, "status": block["status"], "universe_rows": block["universe_count"],
            "assessed": block["assessed_count"], "counts": {k: block["counts"][k] for k in ("evaluated", "ineligible", "evidence_blocked", "unprocessed")},
            "reasons": block["counts"]["reasons"], "reconciled": block["reconciled"], "batches_planned": block["batches_planned"],
            "batches_completed": block["batches_completed"], "model_calls": block["model_calls"], "rows_seen_by_model": len(seen),
            "late_rows_seen_by_model": sum(support.instrument_id(index) in seen for index in late),
            "selected": [pick["instrument_id"] for pick in result["candidates"]], "expected_selected": expected,
            "selection_matches_controlled_expectation": [pick["instrument_id"] for pick in result["candidates"]] == expected,
            "coverage_complete": block["coverage_complete"], "selection_complete": block["selection_complete"],
            "stored_as_candidate_run": repository.get("candidate_run", result["run_id"]) is not None,
        },
    }


def offline_claude(model: str, budget: DailyBudget) -> tuple[BudgetedProvider, dict]:
    """The production Claude provider behind the production budget, with the network replaced: the free count
    endpoint is unreachable and a generation request is answered with a valid empty selection. Nothing leaves."""
    sent = {"count": 0, "generation": 0}

    def poster(url, body, headers, timeout):
        if url != ANTHROPIC_API_URL:
            sent["count"] += 1
            raise URLError("offline receipt: no provider request is made")
        sent["generation"] += 1
        answer = {"schema_version": SCHEMA_VERSION, "candidates": [], "limitations": ["Controlled offline answer."]}
        return 200, json.dumps({"id": "offline", "stop_reason": "tool_use", "usage": {"input_tokens": 1000, "output_tokens": 50},
                                "content": [{"type": "tool_use", "id": "t", "name": TOOL_NAME, "input": answer}]}).encode("utf-8")

    return BudgetedProvider(AnthropicSynthesisProvider(api_key="offline", model=model, poster=poster), budget), sent


def budget_realism() -> dict:
    """What a full run needs against the shared daily allowance, per selectable Claude model.

    Two bounds per batch: the controlled packet this tool builds (current quote and technicals only, so a floor),
    and a packet at the 320,000-byte cap (news-dense, the ceiling ``fit_news`` enforces)."""
    support = fixtures()
    models = [model for model, _ in ENGINE_SPECS["anthropic"].models]
    reducer = CandidateReducer()
    measured = OCTOBER_7["provider_counted_input_tokens"]
    packet = OCTOBER_7["provider_count_packet_bytes"]["value"]
    estimator = {}
    for model in models:
        estimated = estimate_tokens("x" * packet, model)
        estimator[model] = {"bytes_per_token_bound": BYTES_PER_TOKEN[model], "packet_bytes": packet,
                            "provider_counted_input_tokens": measured[model], "estimated_input_tokens": estimated,
                            "former_three_characters_estimate": packet // 3 + 1,
                            "estimate_is_at_least_the_provider_count": estimated >= measured[model],
                            "former_estimate_was_below_the_provider_count": packet // 3 + 1 < measured[model],
                            "margin_over_provider_count_pct": round(100 * (estimated - measured[model]) / measured[model], 1)}
    plans = []
    for model in models:
        for eligible in (40, 150, 500, OCTOBER_7["universe_rows"]["value"] - 25):
            budget = DailyBudget(None, max_requests=DEFAULT_DAILY_REQUESTS, max_tokens=DEFAULT_DAILY_TOKENS, clock=lambda: support.NOW)
            provider, sent = offline_claude(model, budget)
            result, _, _, _, _ = run_controlled(support.universe(eligible), provider, tag=f"budget{eligible}")
            block = result["universe_coverage"]
            plan = block["plan"]
            batches = plan["batches_planned"]
            rounds = reduction_rounds(batches)
            calls = batches + sum(rounds)
            headroom = int(reducer.config.max_tokens) + int(getattr(provider._provider, "reasoning_headroom", 0) or 0)
            ceiling = estimate_tokens("x" * MAX_PACKET_BYTES, model) + 1500 + headroom
            plans.append({
                "model": model, "eligible_rows": eligible, "batches_planned": batches, "reduction_rounds_worst_case": rounds,
                "requests_required": plan["required"]["requests"], "tokens_required_controlled_packets": plan["required"]["tokens"],
                "controlled_packet_bytes_max": plan["packet_bytes_max"], "controlled_batch_tokens_max": plan["batch_tokens_max"],
                "tokens_required_if_every_packet_is_at_the_byte_cap": int(calls * ceiling * PLAN_DRIFT_MARGIN),
                "default_daily_tokens": DEFAULT_DAILY_TOKENS, "default_daily_requests": DEFAULT_DAILY_REQUESTS,
                "status_under_default_allowance": block["status"], "refusal_reason": block["reason"],
                "fits_default_allowance_with_controlled_packets": block["budget"].get("held", False),
                "generation_requests_made": sent["generation"], "count_requests_attempted": sent["count"],
                "budget_tokens_after": budget.status()["tokens"], "hold_left_after": budget.status()["held_tokens"],
                "ai_evaluated": block["counts"]["evaluated"], "unprocessed": block["counts"]["unprocessed"],
            })
    return {"estimator_vs_provider_count": estimator, "drift_margin": PLAN_DRIFT_MARGIN, "plans": plans,
            "reading": "A plan the default allowance cannot pay for is refused before any generation request; the run reports "
                       "AI_COVERAGE_BUDGET_INSUFFICIENT with every eligible row unprocessed. Nothing raises the allowance."}


def failure_injection() -> dict:
    support = fixtures()

    def outcome(result, provider, extra=None):
        block = result["universe_coverage"]
        counts = block["counts"]
        return {"status": block["status"], "reason": block["reason"], "result_state": result["state"], "model_calls": getattr(provider, "calls", None),
                "evaluated": counts["evaluated"], "unprocessed": counts["unprocessed"], "evidence_blocked": counts["evidence_blocked"],
                "reconciled": block["reconciled"], "coverage_complete": block["coverage_complete"],
                "selection_complete": block["selection_complete"], "selected": len(result["candidates"]),
                "provisional_finalists": len(result.get("provisional") or []), **(extra or {})}

    strong = {index: 90.0 for index in range(0, 260, 9)}
    cases = {}

    provider = support.FailingProvider(fail_on=3)
    result, ledger, _, _, repository = run_controlled(support.universe(260, strong=strong), provider)
    cases["provider_failure_mid_scan"] = outcome(result, provider, {"candidate_run_stored": repository.get("candidate_run", "CU-" + result["run_id"]) is not None})

    provider = support.FailingProvider(fail_on=2, reason="ANTHROPIC_TIMEOUT", timeout=True)
    result, ledger, _, _, _ = run_controlled(support.universe(150), provider)
    cases["model_timeout_unknown_outcome"] = outcome(result, provider, {
        "last_call_outcome": ledger.records(result["universe_coverage"]["coverage_run_id"], "batch")[-1]["outcome"]})

    provider = support.FailingProvider(fail_on=1, raw="{not json")
    result, _, _, _, _ = run_controlled(support.universe(120, strong={5: 90.0}), provider)
    cases["malformed_model_output"] = outcome(result, provider)

    bad = ('{"schema_version":"ai-screener-output/1.0.0","limitations":["x"],"candidates":[{"candidate_key":0,"rank":1,'
           '"rationale":"Candidate for review.","supporting_refs":[0,99],"conflicting_refs":[],"uncertainties":[]}]}')
    provider = support.FailingProvider(fail_on=1, raw=bad)
    result, _, _, _, _ = run_controlled(support.universe(120, strong={5: 90.0}), provider)
    cases["malformed_candidate_reference"] = outcome(result, provider)

    provider = support.FailingProvider(fail_on=4)
    result, _, _, _, repository = run_controlled(support.universe(150, strong={10: 90.0, 60: 91.0, 110: 92.0}), provider)
    cases["global_reduction_failure"] = outcome(result, provider, {"candidate_run_stored": repository.get("candidate_run", "CU-" + result["run_id"]) is not None})

    class Moving(support.PagingReader):
        def read(self, **kwargs):
            if kwargs["offset"]:
                raise ValueError("RESULT_SET_CHANGED")
            return super().read(**kwargs)

    provider = support.RankingProvider()
    result, _, _, _, _ = run_controlled([], provider, reader=Moving(support.universe(1200)))
    cases["screener_paging_failure"] = outcome(result, provider, {"enumeration_complete": result["universe_coverage"]["enumeration"]["complete"]})

    stop = [False]
    provider = support.RankingProvider()
    provider.on_call = lambda call, packet: (stop.__setitem__(0, call >= 2), provider.respond(packet))[1]
    result, ledger, _, _, _ = run_controlled(support.universe(300, strong=strong), provider, should_stop=lambda: stop[0])
    cases["operator_stop"] = outcome(result, provider, {"receipts_kept": len(ledger.records(result["universe_coverage"]["coverage_run_id"], "batch"))})

    rows = [support.row(index, price=None) for index in range(70)]
    provider = support.RankingProvider()
    result, _, _, _, _ = run_controlled(rows, provider)
    cases["missing_quote_clocks_for_every_row"] = outcome(result, provider)

    budget = DailyBudget(None, max_requests=30, max_tokens=1, clock=lambda: support.NOW)
    inner = support.RankingProvider()
    result, _, _, _, _ = run_controlled(support.universe(160), BudgetedProvider(inner, budget))
    cases["budget_insufficient_before_start"] = outcome(result, inner, {"budget_tokens_spent": budget.status()["tokens"]})

    provider = support.RankingProvider()
    result, _, _, _, _ = run_controlled(support.universe(260), provider)
    cases["completed_scan_none_selected"] = outcome(result, provider)

    # Ninety seconds pass during the first request: the second batch's quotes are past their sixty-second policy.
    ticks = [support.NOW]
    provider = support.RankingProvider()
    provider.on_call = lambda call, packet: (ticks.__setitem__(0, support.NOW + 90), provider.respond(packet))[1]
    result, _, _, _, repository = run_controlled(support.universe(100, strong={0: 90.0, 99: 95.0}), provider, clock=lambda: ticks[0])
    cases["eligible_rows_stale_before_their_request"] = outcome(result, provider, {
        "ai_coverage_pct": result["universe_coverage"]["ai_coverage_pct"],
        "candidate_run_stored": repository.get("candidate_run", "CU-" + result["run_id"]) is not None})

    # Seventy seconds pass during the only request: the answer arrives after the evidence it cites has expired.
    ticks = [support.NOW]
    provider = support.RankingProvider()
    provider.on_call = lambda call, packet: (ticks.__setitem__(0, ticks[0] + 70), provider.respond(packet))[1]
    result, _, _, _, repository = run_controlled(support.universe(40, strong={7: 90.0}), provider, clock=lambda: ticks[0])
    cases["final_answer_outlived_its_evidence"] = outcome(result, provider, {
        "candidate_run_stored": repository.get("candidate_run", "CU-" + result["run_id"]) is not None})
    from tests.platform.test_screener_ai_coverage import ClockReader
    ticks = [support.NOW]
    provider = support.RankingProvider()
    provider.on_call = lambda call, packet: (ticks.__setitem__(0, ticks[0] + 35), provider.respond(packet))[1]
    clock = lambda: ticks[0]
    reader = ClockReader(support.universe(100, strong={5: 90.0, 99: 95.0}), clock, frozen=(99,))
    result, _, _, _, repository = run_controlled([], provider, reader=reader, clock=clock)
    cases["finalist_excluded_at_global_cutoff"] = outcome(result, provider, {
        "candidate_run_stored": repository.get("candidate_run", "CU-" + result["run_id"]) is not None,
        "excluded_finalists": result["universe_coverage"]["reduction"]["finalists_excluded_count"]})

    stop = [False]
    provider = support.RankingProvider()
    provider.on_call = lambda call, packet: (stop.__setitem__(0, True), provider.respond(packet))[1]
    result, _, _, _, repository = run_controlled(support.universe(40, strong={39: 95.0}), provider, should_stop=lambda: stop[0])
    cases["stop_during_final_inflight_call"] = outcome(result, provider, {
        "candidate_run_stored": repository.get("candidate_run", "CU-" + result["run_id"]) is not None})
    return cases


def provider_count(probe: bool) -> dict:
    """One free token count per selectable Claude model on one controlled batch. No generation request exists here."""
    if not probe:
        return {"run": False, "reason": "NOT_RUN: offline receipt; pass --probe for the free token-count request"}
    from market_platform_foundation.news.config import configured_value

    key = (configured_value("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        return {"run": False, "reason": "NOT_RUN: ANTHROPIC_API_KEY is not configured"}
    support = fixtures()
    out = {"run": True, "generation_requests": 0, "models": {}}
    for model, _ in ENGINE_SPECS["anthropic"].models:
        provider = AnthropicSynthesisProvider(api_key=key, model=model)
        service = ScreenerAiService(reader=support.PagingReader(support.universe(MAX_INTAKE)), news=support.News(provider), clock=lambda: support.NOW)
        scope, candidates, now, _ = service._packet(support.SCOPE)
        reducer = CandidateReducer(provider=provider, clock=lambda: support.NOW)
        estimate = reducer.estimate(scope, candidates, now)
        counted = reducer.preflight(scope, candidates, now)
        tokens = counted.get("input_tokens")
        out["models"][model] = {
            "packet_rows": len(candidates), "packet_bytes": estimate["packet_bytes"], "estimated_input_tokens": estimate["input_tokens"],
            "provider": {key_: counted.get(key_) for key_ in ("accepted", "input_tokens", "context_window", "context_fit", "reason")},
            "estimate_is_at_least_the_provider_count": (estimate["input_tokens"] >= tokens) if isinstance(tokens, int) else None,
        }
    return out


def packet_composition() -> dict:
    """Where the bytes of one controlled 50-row batch go. Measured, to say what bounds batch cost."""
    from market_platform_foundation.intelligence.inference.candidate_reduction import packet_candidates

    support = fixtures()
    service = ScreenerAiService(reader=support.PagingReader(support.universe(MAX_INTAKE)), news=support.News(support.RankingProvider()),
                                clock=lambda: support.NOW)
    scope, candidates, now, _ = service._packet(support.SCOPE)
    packet = packet_candidates(candidates)
    size = lambda value: len(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    one = packet[0]
    return {"rows": len(packet), "packet_bytes": size({"scope": scope, "decision_cutoff": now, "candidates": packet}),
            "bytes_per_candidate": size(one), "bytes_by_field": {key: size(value) for key, value in one.items()},
            "evidence_items_per_candidate": len(one["current_market_evidence"]) + len(one["reference_evidence"]),
            "note": "Quote and technicals only, no news. The per-candidate missing-capability list and per-item provenance are "
                    "the fixed cost of the PR 484 packet shape; this feature does not change that shape."}


def gates(scale_rows, replay, budget, failures, validation) -> dict:
    big = next(row for row in scale_rows if row["universe_rows"] >= 4600)
    partial = [failures[name] for name in ("provider_failure_mid_scan", "model_timeout_unknown_outcome", "malformed_model_output",
                                           "malformed_candidate_reference", "global_reduction_failure", "operator_stop")]
    suites = (validation or {}).get("gate_suites") or {}
    passed = lambda name: "PASS" if suites.get(name) == "PASS" else "NOT_DEMONSTRATED_BY_THIS_TOOL: see validation"
    return {
        "G1_complete_universe_enumerated": "PASS" if all(row["assessed"] == row["universe_rows"] for row in scale_rows) else "FAIL",
        "G2_no_silent_first_n_limit": "PASS" if replay["new_method"]["late_rows_seen_by_model"] == 3 and replay["old_method"]["late_rows_seen_by_model"] == 0 else "FAIL",
        "G3_every_row_accounted_for": "PASS" if all(row["reconciled"] for row in scale_rows if row["universe_rows"]) and all(f["reconciled"] for f in partial) else "FAIL",
        "G4_existing_deterministic_gates_preserved": passed("deterministic_gates"),
        "G5_missing_evidence_distinct_from_ineligibility": "PASS" if failures["missing_quote_clocks_for_every_row"]["evidence_blocked"] == 70 and failures["missing_quote_clocks_for_every_row"]["model_calls"] == 0 else "FAIL",
        "G6_bounded_batch_planning": "PASS" if all((row["largest_request_rows"] or 0) <= MAX_INTAKE and (row["packet_bytes_max"] or 0) <= MAX_PACKET_BYTES for row in scale_rows) else "FAIL",
        "G7_conservative_token_reservations": "PASS" if all(item["estimate_is_at_least_the_provider_count"] for item in budget["estimator_vs_provider_count"].values()) else "FAIL",
        "G8_shared_budget_preserved": "PASS" if all(plan["hold_left_after"] == 0 and plan["budget_tokens_after"] <= DEFAULT_DAILY_TOKENS for plan in budget["plans"]) else "FAIL",
        "G9_compact_schema_compatibility_preserved": passed("wire_contract"),
        "G10_useful_evidence_survives_packet_fitting": passed("news_evidence"),
        "G11_temporal_correctness": "PASS" if suites.get("temporal") == "PASS"
        and failures["eligible_rows_stale_before_their_request"]["status"] == "PROVISIONAL_PARTIAL_COVERAGE"
        and failures["eligible_rows_stale_before_their_request"]["ai_coverage_pct"] == 50.0
        and not failures["final_answer_outlived_its_evidence"]["candidate_run_stored"]
        and failures["final_answer_outlived_its_evidence"]["reason"] == "FINAL_SELECTION_EXPIRED_DURING_INFERENCE"
        else "FAIL",
        "G12_cross_instrument_reference_isolation": "PASS" if failures["malformed_candidate_reference"]["reason"] == "BATCH_FAILED:WIRE_REFERENCE_INDEX_INVALID" else "FAIL",
        "G13_batch_order_bias_controlled": passed("fairness"),
        "G14_intermediate_candidates_never_final": "PASS" if not failures["provider_failure_mid_scan"]["candidate_run_stored"] and not failures["global_reduction_failure"]["candidate_run_stored"] and failures["global_reduction_failure"]["provisional_finalists"] == 3 else "FAIL",
        "G15_global_zero_to_five_selection": "PASS" if replay["new_method"]["selection_matches_controlled_expectation"] and big["last_row_selected"] else "FAIL",
        "G16_budget_exhaustion_reports_incomplete": "PASS" if failures["budget_insufficient_before_start"]["status"] == "AI_COVERAGE_BUDGET_INSUFFICIENT" and failures["budget_insufficient_before_start"]["model_calls"] == 0 and not failures["budget_insufficient_before_start"]["coverage_complete"] else "FAIL",
        "G17_truthful_progress_and_terminal_status": passed("run_tracker"),
        "G18_stop_restart_idempotency": passed("run_tracker"),
        "G19_zero_result_reasons_distinct": "PASS" if len({failures[name]["status"] for name in ("completed_scan_none_selected", "missing_quote_clocks_for_every_row", "budget_insufficient_before_start", "screener_paging_failure", "provider_failure_mid_scan", "operator_stop")}) == 6 else "FAIL",
        "G20_action_decision_integration_preserved": passed("downstream"),
        "G21_paper_risk_stop_lifecycle_preserved": passed("downstream"),
        "G22_no_live_capital_authority": passed("downstream"),
        "G23_october_7_controlled_replay": "PASS" if replay["new_method"]["reconciled"] and replay["new_method"]["selection_complete"] and replay["old_method"]["share_of_universe_seen_pct"] < 2 else "FAIL",
        "G24_large_universe_scale": "PASS" if big["selection_complete"] and big["reconciled"] else "FAIL",
        "G25_validation_and_protected_ci": (validation or {}).get("G25", "NOT_DEMONSTRATED: validation totals not supplied to this run"),
    }


def build(probe: bool, validation: dict | None) -> dict:
    scale_rows = scale([0, 30, 50, 51, 100, 500, 4600, 20000])
    replay = october_7_replay()
    budget = budget_realism()
    failures = failure_injection()
    reducer = CandidateReducer()
    prompt = reducer.registry.get_by_id(PROMPT_ID)
    return {
        "receipt": "ai-screener-full-universe-acceptance", "classification": "SOFTWARE_CONTROLLED",
        "schema_version": "ai-screener-full-universe-acceptance/1.0.0",
        "base_sha": git("merge-base", "HEAD", "origin/main"), "implementation_sha": git("rev-parse", "HEAD"),
        "implementation_tree": git("rev-parse", "HEAD^{tree}"),
        "method": {"version": METHOD_VERSION, "name": METHOD_NAME, "previous_method": INTAKE_METHOD_VERSION,
                   "max_batch_rows": MAX_INTAKE, "max_selected": MAX_SELECTED, "max_packet_bytes": MAX_PACKET_BYTES,
                   "batch_order": "sha256(result_set|instrument_id)", "drift_margin": PLAN_DRIFT_MARGIN},
        "inference_contract": {"prompt_id": PROMPT_ID, "prompt_version": prompt.version, "prompt_hash": prompt.content_hash,
                               "wire_schema_version": WIRE_SCHEMA_VERSION, "stored_schema_version": SCHEMA_VERSION,
                               "request_timeout_seconds": reducer.config.timeout_seconds, "max_output_tokens": reducer.config.max_tokens,
                               "retries": 0},
        "scale": scale_rows, "october_7_controlled_replay": replay, "budget": budget, "failure_injection": failures,
        "provider_token_count": provider_count(probe), "paid_generation_calls": 0,
        "packet_composition": packet_composition(),
        "LIVE_RTH_ACCEPTANCE": "NOT_OBSERVED: no prospective or live-market session was run for this feature",
        "validation": validation or "NOT_RUN_BY_THIS_TOOL",
        "independent_review": (validation or {}).get("independent_review", "NOT_SUPPLIED"),
        "gates": gates(scale_rows, replay, budget, failures, validation),
        "remaining_limitations": [
            "Under the default shared allowance (200,000 tokens, 30 requests per UTC day) an unfiltered multi-thousand-row "
            "universe cannot be AI-evaluated; the run refuses it before any model call. Narrowing the Screener query or the "
            "owner raising IMP_SYNTHESIS_DAILY_* are the only ways to complete it.",
            "A batch holds at most 50 rows: the only strict-schema grammar size the provider has been shown to accept.",
            "No run is resumed after a server restart; quote evidence expires after 60 seconds, so a new Run is a new run.",
            "A final answer that arrives more than 60 seconds after its evidence cutoff is not a selection. Request timeouts are "
            "45 seconds (300 for a local model), so a slow engine will end runs as partial; that is reported, not hidden.",
            "For a universe with no bulk snapshot source (futures, bonds, crypto) a request is only as fresh as the quotes the "
            "Screener already serves for those rows.",
            "Quota-file locking coordinates instances in one serving process; independent servers sharing a quota file are not supported.",
            "Per-instrument news providers are cache-only during a run; rows outside those caches carry shared-source news only.",
            "Automatic reevaluation passes keep the single-request method and never claim coverage.",
            "Selection is the documented tournament of bounded comparisons made by the configured model. It is not a ranking "
            "score and not a claim of best return; a model may choose differently in a different comparison context.",
            "No paid generation was made under this method: controlled engines answer in every test and in this receipt.",
            "The controlled packets here carry quote and technicals only; real news-dense packets reach the 320,000-byte cap, "
            "so real per-batch token cost is far above the controlled figures (see budget.plans).",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--probe", action="store_true", help="also make one free token-count request per Claude model")
    parser.add_argument("--validation", type=Path, help="JSON of validation totals recorded from the exact-head runs")
    parser.add_argument("--out", type=Path, default=RECEIPT)
    args = parser.parse_args()
    validation = json.loads(args.validation.read_text(encoding="utf-8")) if args.validation else None
    receipt = build(args.probe, validation)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"implementation_sha": receipt["implementation_sha"], "gates": receipt["gates"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
