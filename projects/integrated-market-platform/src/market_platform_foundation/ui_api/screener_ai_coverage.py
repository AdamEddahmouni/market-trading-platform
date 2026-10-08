"""Full-universe AI Screener run: enumerate, account, batch, reduce globally, report truthfully.

One run reads every row of the active Screener query, classifies each with the gates that already exist,
sends every eligible row to the model in bounded batches, and compares the batch finalists until one
request holds them all. That last request's answer, made on evidence acquired for it, is the only thing
stored as a ``candidate_run`` and so the only thing the Action Decision layer can load. Anything short of
that is reported as what it is: batch finalists are provisional and are never stored as a candidate run.

Every model call is the existing ``CandidateReducer`` request (prompt v3, ``ai-screener-wire/3.0.0``).
This module adds no retry, no ranking score and no trading threshold, and has no execution authority.
"""
from __future__ import annotations

import math
import time
from datetime import UTC, datetime
from typing import Any, Callable

from ..intelligence.inference.candidate_reduction import (
    MAX_INTAKE, MAX_PACKET_BYTES, MAX_SELECTED, PROMPT_ID, SCHEMA_VERSION as OUTPUT_SCHEMA_VERSION, WIRE_SCHEMA_VERSION,
)
from ..intelligence.inference.coverage_plan import (
    AI_EVALUATED, ELIGIBLE, INELIGIBLE, METHOD_NAME, METHOD_VERSION, PROVIDER_UNAVAILABLE, UNPROCESSED,
    budget_requirement, chunks, classify, fair_order, reconciles, reduction_rounds, tally,
)
from ..intelligence.inference.hashing import input_hash_from_dict
from ..intelligence.inference.run_progress import relabelled, report_stage
from .screener_ai_universe import UniverseEnumerationError, enumerate_universe

RESULT_SCHEMA_VERSION = "screener-ai-screener/1.0.0"
# Terminal statuses. Only the first stores a candidate run.
GLOBAL_SELECTION_COMPLETE = "GLOBAL_SELECTION_COMPLETE"
COMPLETE_NO_SELECTION = "COMPLETE_NO_SELECTION"
NO_ELIGIBLE_ROWS = "NO_ELIGIBLE_ROWS"
EMPTY_UNIVERSE = "EMPTY_UNIVERSE"
# Nothing was eligible because the quote source itself returned nothing: not a statement about the rows.
EVIDENCE_PROVIDER_UNAVAILABLE = "EVIDENCE_PROVIDER_UNAVAILABLE"
PROVISIONAL_PARTIAL_COVERAGE = "PROVISIONAL_PARTIAL_COVERAGE"
BUDGET_INSUFFICIENT = "AI_COVERAGE_BUDGET_INSUFFICIENT"
ENUMERATION_FAILED = "UNIVERSE_ENUMERATION_FAILED"
STOPPED = "STOPPED"
INTERRUPTED = "INTERRUPTED"
FAILED = "FAILED"
SELECTION_COMPLETE = frozenset({GLOBAL_SELECTION_COMPLETE, COMPLETE_NO_SELECTION, NO_ELIGIBLE_ROWS, EMPTY_UNIVERSE})
# A batch answer the run can build on. EXPIRED is a valid answer whose evidence aged out while the model worked;
# its picks are still finalists, because the final round re-acquires evidence for every finalist.
_ANSWERED = frozenset({"CURRENT", "NO_GROUNDED_CANDIDATES", "EXPIRED"})
_BUDGET_REASONS = frozenset({"SYNTHESIS_RUN_HOLD_EXHAUSTED", "SYNTHESIS_RUN_HOLD_MISSING", "SYNTHESIS_DAILY_REQUEST_LIMIT",
                             "SYNTHESIS_DAILY_TOKEN_LIMIT"})
# A free token count that failed for a reason unrelated to the request itself; the plan keeps its estimate.
_PREFLIGHT_SKIPPED = frozenset({"API_KEY_MISSING", "COUNT_TOKENS_UNSUPPORTED", "ANTHROPIC_TIMEOUT", "ANTHROPIC_UNREACHABLE",
                                "ANTHROPIC_AUTH_FAILED"})
ROWS_PER_RECORD = 2000
# Evidence is re-acquired for every request, so a request can be slightly larger than the packet it was planned
# from. Each planned call is held with this margin; a call that still exceeds its hold ends the run as partial.
PLAN_DRIFT_MARGIN = 1.05
_LIMITATIONS = {
    COMPLETE_NO_SELECTION: "Every eligible row was evaluated and compared; no candidate was selected.",
    NO_ELIGIBLE_ROWS: "Every row was assessed; none had an admissible current price plus additional strong evidence, so no model was called.",
    EMPTY_UNIVERSE: "The active Screener query matched no rows.",
    PROVISIONAL_PARTIAL_COVERAGE: "This run did not finish. Listed finalists are provisional and are not a global selection.",
    BUDGET_INSUFFICIENT: "The shared daily budget cannot pay for every eligible row plus the global comparison; no model was called.",
    ENUMERATION_FAILED: "The Screener result could not be read completely; nothing was evaluated.",
    STOPPED: "Stopped by the operator before the run finished. Listed finalists are provisional.",
    FAILED: "The run failed before it finished.",
    EVIDENCE_PROVIDER_UNAVAILABLE: "The quote source returned nothing, so no row could be assessed as eligible. This says nothing about the rows.",
}
# Kept out of the ledger's terminal record: a long run's finalists with their rationales can exceed a record.
MAX_TERMINAL_FINALISTS = 500
MAX_EXCLUDED_LISTED = 100


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


def _software_sha() -> str:
    from ..git_ref import read_git_head

    return read_git_head() or "UNAVAILABLE"


class _Run:
    """Everything one run learns. Lives for the run only; the ledger and the returned result are the record."""

    def __init__(self, run_id: str, account_id: str) -> None:
        self.run_id, self.account_id = run_id, account_id
        self.classes: dict[str, tuple[str, list[str]]] = {}
        self.rows: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.envelope: dict[str, Any] = {}
        self.universe: str = ""
        self.scope: dict[str, Any] = {}
        self.universe_count: int | None = None
        self.enumeration: dict[str, Any] = {"complete": False}
        self.eligible_count = 0
        self.plan: dict[str, Any] | None = None
        self.batches_completed = 0
        self.submitted = 0
        self.calls = 0
        self.cache_hits = 0
        self.query: dict[str, Any] = {}
        self.provider_reason: str | None = None
        self.excluded_finalists: list[dict[str, Any]] = []
        self.final_rows_recorded = False
        self.finalists: list[dict[str, Any]] = []
        self.rounds_completed = 0
        self.budget: dict[str, Any] = {"capped": False}
        self.hold = False
        self.tokens_input = self.tokens_output = 0
        self.timings: dict[str, float] = {}
        self.terminal: dict[str, Any] | None = None
        self.cutoffs: dict[str, str | None] = {"classification": None, "first_batch": None, "last_batch": None, "final": None}


class ScreenerAiCoverage:
    def __init__(self, service: Any, *, ledger: Any | None = None, software_sha: str | None = None,
                 repository: Any | None = None) -> None:
        self.service = service
        self._ledger = ledger
        self._software_sha = software_sha
        # Where the one final candidate run is stored: the same repository the Action Decision layer reads.
        self._repository = repository

    def ledger(self) -> Any:
        if self._ledger is None:
            from ..local_state.ai_screener_coverage import coverage_ledger

            self._ledger = coverage_ledger()
        return self._ledger

    # ------------------------------------------------------------------ run

    def run(self, body: dict[str, Any], *, run_id: str, account_id: str,
            should_stop: Callable[[], bool] = lambda: False) -> dict[str, Any]:
        service = self.service
        query = service._query(body)
        reducer = service._provider_reducer()
        provider = reducer.provider
        prompt = reducer.registry.get_by_id(PROMPT_ID)
        run = _Run(run_id, account_id)
        run.scope = service._scope(query, {"result_set_id": query["result_set"]})
        run.query = query
        self.identity = {
            "account_id": account_id, "method_version": METHOD_VERSION, "method_name": METHOD_NAME,
            "software_sha": self._software_sha or _software_sha(),
            "provider_id": getattr(provider, "provider_id", None), "model_id": getattr(provider, "model_id", None),
            "runtime": (getattr(provider, "runtime", None) or "PAID_API") if provider is not None else None,
            "prompt_id": prompt.prompt_id, "prompt_version": prompt.version, "prompt_hash": prompt.content_hash,
            "wire_schema_version": WIRE_SCHEMA_VERSION, "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "limits": {"max_batch_rows": MAX_INTAKE, "max_selected": MAX_SELECTED, "max_packet_bytes": MAX_PACKET_BYTES},
            "query": {key: query[key] for key in ("universe", "search", "sort", "descending", "filters", "view", "screen")},
            "requested_result_set": query["result_set"], "started_at": _iso(service._clock()),
        }
        self.ledger().append(run_id, "run", self.identity)
        self._reducer, self._provider, self._budget = reducer, provider, getattr(provider, "budget", None)
        try:
            return self._execute(run, query, should_stop)
        except Exception as exc:  # noqa: BLE001 - a run always ends with a terminal record; the tracker reports the failure
            code = str(exc)
            if run.terminal is None:
                try:
                    self._terminal(run, FAILED, code if code.isupper() and code.replace("_", "").isalnum() else "AI_SCREENER_RUN_FAILED")
                except Exception:  # noqa: BLE001 - the original failure is the one reported
                    pass
            raise
        finally:
            self._release(run)

    def _execute(self, run: _Run, query: dict[str, Any], should_stop: Callable[[], bool]) -> dict[str, Any]:
        service = self.service
        mark = time.perf_counter()

        report_stage("ENUMERATION")
        started = _iso(service._clock())
        try:
            universe = enumerate_universe(service._reader, query)
        except UniverseEnumerationError as exc:
            run.enumeration = {"complete": False, "reason": exc.code, "started_at": started, "ended_at": _iso(service._clock())}
            return self._terminal(run, ENUMERATION_FAILED, exc.code)
        run.universe, run.envelope, run.universe_count = query["universe"], universe.envelope, universe.result_count
        run.scope = service._scope(query, universe.envelope)
        run.order = [row["instrument"]["instrument_id"] for row in universe.rows]
        run.rows = dict(zip(run.order, universe.rows))
        run.enumeration = {"complete": True, "reason": None, "pages": universe.pages, "started_at": started,
                           "ended_at": _iso(service._clock()), "result_set": universe.result_set, "query_id": universe.query_id}
        run.timings["enumeration_ms"] = (time.perf_counter() - mark) * 1000
        report_stage("ENUMERATION", universe_count=run.universe_count)
        if not run.order:
            return self._terminal(run, EMPTY_UNIVERSE)

        mark = time.perf_counter()
        report_stage("ELIGIBILITY", universe_count=run.universe_count)
        candidates = self._classify(run)
        run.timings["eligibility_ms"] = (time.perf_counter() - mark) * 1000
        eligible = [key for key in run.order if run.classes[key][0] == ELIGIBLE]
        run.eligible_count = len(eligible)
        report_stage("ELIGIBILITY", assessed_count=len(run.classes), eligible_count=run.eligible_count)
        if not eligible:
            if run.provider_reason:
                return self._terminal(run, EVIDENCE_PROVIDER_UNAVAILABLE, run.provider_reason)
            return self._terminal(run, NO_ELIGIBLE_ROWS)
        refusal = self._engine_refusal()
        if refusal:
            for key in eligible:
                run.classes[key] = (UNPROCESSED, [refusal])
            return self._terminal(run, FAILED, refusal)

        mark = time.perf_counter()
        report_stage("PLANNING", eligible_count=run.eligible_count)
        batches = self._plan(run, eligible, candidates)
        del candidates
        run.timings["planning_ms"] = (time.perf_counter() - mark) * 1000
        report_stage("PLANNING", batches_planned=len(batches), required_tokens=run.plan["required"]["tokens"] if self._budget is not None else None)
        if run.plan.get("preflight_rejected"):
            self._unprocessed(run, batches, "PROVIDER_PREFLIGHT_REJECTED")
            return self._terminal(run, FAILED, run.plan["preflight_rejected"])
        if not batches:
            return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "NO_ROW_FITS_ONE_REQUEST")
        if self._budget is not None:
            held = self._budget.hold(run.run_id, requests=run.plan["required"]["requests"], tokens=run.plan["required"]["tokens"])
            run.budget = {"capped": True, **held}
            if not held["held"]:
                self._unprocessed(run, batches, "BUDGET_INSUFFICIENT")
                return self._terminal(run, BUDGET_INSUFFICIENT, held["reason"])
            run.hold = True
            report_stage("BUDGET_HELD", held_tokens=held["required_tokens"], held_requests=held["required_requests"])
        self.ledger().append(run.run_id, "plan", {"plan": run.plan, "budget": run.budget})

        mark = time.perf_counter()
        last: dict[str, Any] | None = None
        for index, batch in enumerate(batches):
            if should_stop():
                self._unprocessed(run, batches[index:], "STOPPED_BY_OPERATOR")
                return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")
            outcome = self._call(run, batch["instrument_ids"], stage="BATCH_INFERENCE", index=index, total=len(batches),
                                 planned_tokens=batch["tokens"], first_pass=True)
            if outcome["failure"]:
                self._unprocessed(run, [{"instrument_ids": outcome["submitted"]}], "BATCH_FAILED:" + outcome["failure"])
                self._unprocessed(run, batches[index + 1:], "NOT_STARTED_AFTER_BATCH_FAILURE")
                return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, self._partial_reason(outcome["failure"]))
            run.batches_completed += 1
            last = outcome["result"] or last
            report_stage("BATCH_INFERENCE", batch=index + 1, batches_planned=len(batches), batches_completed=run.batches_completed,
                         rows_evaluated=run.submitted)
        run.timings["batch_inference_ms"] = (time.perf_counter() - mark) * 1000

        if any(name == UNPROCESSED for name, _ in run.classes.values()):
            # Every planned call ran, but a row that could not be sent (too large, thinned below sufficiency) remains.
            return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "ELIGIBLE_ROWS_NOT_SUBMITTED")
        if not run.finalists:
            return self._terminal(run, COMPLETE_NO_SELECTION)
        if len(batches) == 1 and last is not None:
            # One request already compared every eligible row; its evidence was acquired for that request.
            return self._final(run, last)

        mark = time.perf_counter()
        pool = list(dict.fromkeys(item["instrument_id"] for item in run.finalists))
        number = 0
        while True:
            number += 1
            groups = chunks(fair_order(f"{run.scope['result_set']}|round-{number}", pool))
            winners: list[str] = []
            final: dict[str, Any] | None = None
            admitted = False
            for index, group in enumerate(groups):
                if should_stop():
                    return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")
                outcome = self._call(run, group, stage="GLOBAL_REDUCTION", index=index, total=len(groups),
                                     planned_tokens=run.plan["largest_batch_tokens"], first_pass=False, round_number=number)
                if outcome["failure"]:
                    return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "GLOBAL_REDUCTION_INCOMPLETE:" + outcome["failure"])
                final = outcome["result"]
                admitted = admitted or bool(outcome["submitted"])
                winners.extend(pick["instrument_id"] for pick in (final or {}).get("candidates", []))
            run.rounds_completed = number
            self.ledger().append(run.run_id, "round", {"round": number, "calls": len(groups), "entrants": len(pool), "advanced": len(winners)})
            report_stage("GLOBAL_REDUCTION", round=number, finalists=len(winners))
            if not winners:
                run.timings["global_reduction_ms"] = (time.perf_counter() - mark) * 1000
                if not admitted:
                    # No finalist had admissible evidence when the comparison was due: nothing was compared.
                    return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "NO_FINALIST_ADMISSIBLE_AT_FINAL_CUTOFF")
                return self._terminal(run, COMPLETE_NO_SELECTION, "NO_FINALIST_SELECTED_IN_GLOBAL_COMPARISON")
            if len(groups) == 1:
                run.timings["global_reduction_ms"] = (time.perf_counter() - mark) * 1000
                return self._final(run, final)
            pool = list(dict.fromkeys(winners))

    def _final(self, run: _Run, final: dict[str, Any] | None) -> dict[str, Any]:
        """The last comparison's answer becomes the result only while its own evidence is still current."""
        if final is None or final.get("state") != "CURRENT":
            # The answer arrived after the evidence it cites had expired: a selection nobody may act on is not final.
            if final is not None:
                run.finalists = [{"instrument_id": pick["instrument_id"], "batch": 0, "rank_in_batch": pick["rank"],
                                  "rationale": pick["rationale"], "evidence_cutoff": final["decision_cutoff"],
                                  "valid_until": final["valid_until"]} for pick in final.get("candidates", [])] or run.finalists
            return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "FINAL_SELECTION_EXPIRED_DURING_INFERENCE")
        return self._terminal(run, GLOBAL_SELECTION_COMPLETE, "FINALISTS_EXCLUDED_AT_FINAL_CUTOFF" if run.excluded_finalists else None, final=final)

    def _current_rows(self, run: _Run, instrument_ids: list[str]) -> list[dict[str, Any]]:
        """These rows as the Screener serves them now, so a request's row evidence is not older than the request.

        The enumeration's membership stands: a row that has since left the result is read from the enumeration and
        its own clocks decide whether it is still admissible. If the result cannot be read again the enumerated rows
        are used the same way. Nothing is acquired here beyond what the Screener already serves."""
        try:
            now = enumerate_universe(self.service._reader, {**run.query, "result_set": None})
        except (UniverseEnumerationError, ValueError):
            return [run.rows[key] for key in instrument_ids]
        fresh = {row["instrument"]["instrument_id"]: row for row in now.rows}
        return [fresh.get(key, run.rows[key]) for key in instrument_ids]

    # ------------------------------------------------------- classification

    def _classify(self, run: _Run) -> dict[str, dict[str, Any]]:
        """Class and reasons for every row, from the existing gates. Returns the eligible rows' candidates."""
        service = self.service
        raw = [run.rows[key] for key in run.order]
        # Shared news is refreshed before short-lived quotes are taken, as the single-request method does.
        service._news_for(run.universe, raw[:1], refresh=True)
        market, market_reason = service._market(run.universe, raw, acquire=True)
        run.provider_reason = market_reason
        now = _iso(service._clock())
        run.cutoffs["classification"] = now
        # Order flow is read here as it is for every request, so a row is classified on the evidence it would be sent with.
        candidates, _ = service._candidates(run.universe, run.envelope, raw, market=market, now=now, include_flow=True)
        refused = market.refused if market is not None else frozenset()
        kept: dict[str, dict[str, Any]] = {}
        maybe: list[str] = []
        for key, candidate in zip(run.order, candidates):
            name, reasons = classify(candidate, provider_reason=market_reason, refused=key in refused)
            run.classes[key] = (name, reasons)
            if name == ELIGIBLE:
                kept[key] = candidate
            elif name == INELIGIBLE and reasons == ["NO_SECOND_STRONG_EVIDENCE"]:
                maybe.append(key)
                kept[key] = candidate
        # A row with a current price and nothing else may still be lifted by admitted news, exactly as the
        # existing sufficiency rule allows. Only those rows are projected here; the rest are read per batch.
        from .screener_news_evidence import attach_news

        for group in chunks(maybe):
            news = service._news_for(run.universe, [run.rows[key] for key in group], refresh=True)
            for key in group:
                if key in news:
                    attach_news(kept[key], news[key], now=now)
                if kept[key]["sufficient"]:
                    run.classes[key] = (ELIGIBLE, [])
                else:
                    del kept[key]
        self._record_rows(run, "CLASSIFIED")
        return kept

    def _engine_refusal(self) -> str | None:
        if self._provider is None:
            return self._reducer.reason
        contract = self._reducer.contract()
        return contract["reason"] if contract is not None and not contract["supported"] else None

    # -------------------------------------------------------------- planning

    def _context_window(self) -> int | None:
        from ..intelligence.inference.anthropic_models import CLAUDE_MODELS

        known = CLAUDE_MODELS.get(getattr(self._provider, "model_id", "") or "")
        if known is not None:
            return known.context_window
        try:
            ai = self.service.ai_status()
        except Exception:  # noqa: BLE001 - an unknown window only means the plan does not split on it
            return None
        current = next((engine for engine in ai.get("engines") or [] if engine.get("id") == ai.get("engine")), None)
        window = (current or {}).get("context_window")
        return int(window) if isinstance(window, int) and window > 0 else None

    def _plan(self, run: _Run, eligible: list[str], candidates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Bounded batches in an order no sort or page can bias, sized by rows, bytes and the model's window."""
        from .screener_news_evidence import attach_news, fit_news

        service, reducer = self.service, self._reducer
        now = run.cutoffs["classification"]
        window = self._context_window()
        output = int(reducer.config.max_tokens) + int(getattr(self._provider, "reasoning_headroom", 0) or 0)
        ordered = fair_order(str(run.scope["result_set"]), eligible)
        pending = chunks(ordered)
        batches: list[dict[str, Any]] = []
        thinned = 0
        while pending:
            group = pending.pop(0)
            members = [candidates[key] for key in group]
            news = service._news_for(run.universe, [run.rows[key] for key in group], refresh=True)
            for key, member in zip(group, members):
                if key in news and "news" not in member:
                    attach_news(member, news[key], now=now)
            reason = None
            try:
                before = sum(len(member["reference_evidence"]) for member in members)
                fit_news(run.scope, members, news, now=now)
                thinned += before - sum(len(member["reference_evidence"]) for member in members)
                estimate = reducer.estimate(run.scope, members, now)
                if window is not None and estimate["input_tokens"] + output > window:
                    reason = "PACKET_EXCEEDS_CONTEXT_WINDOW"
            except ValueError as exc:
                if str(exc) != "EVIDENCE_PACKET_BOUND_EXCEEDED":
                    raise
                reason = "IRREDUCIBLE_PACKET_OVERSIZE"
            if reason is not None:
                if len(group) == 1:
                    run.classes[group[0]] = (UNPROCESSED, [reason])
                else:
                    half = math.ceil(len(group) / 2)
                    pending[:0] = [group[:half], group[half:]]
                continue
            batches.append({"instrument_ids": group, "packet_bytes": estimate["packet_bytes"], "input_tokens": estimate["input_tokens"],
                            "tokens": estimate["tokens"] if estimate["tokens"] is not None else estimate["input_tokens"] + output,
                            "members": members})
        measured = None
        rejected = None
        if batches and self._budget is not None:
            # The provider's own count of the first request, where it offers one. It bills and reserves nothing.
            check = reducer.preflight(run.scope, batches[0]["members"], now)
            if check is not None:
                measured = {key: check.get(key) for key in ("accepted", "input_tokens", "context_window", "context_fit", "reason")}
                measured["estimated_input_tokens"] = batches[0]["input_tokens"]
                tokens = check.get("input_tokens")
                if check.get("accepted") and isinstance(tokens, int) and tokens > batches[0]["input_tokens"]:
                    # The estimate was under the provider's count: raise every batch by the same ratio plus a margin.
                    factor = tokens / batches[0]["input_tokens"] * 1.05
                    measured["plan_scaled_by"] = round(factor, 4)
                    for batch in batches:
                        batch["tokens"] = math.ceil(batch["tokens"] * factor)
                elif not check.get("accepted") and check.get("reason") not in _PREFLIGHT_SKIPPED:
                    rejected = str(check.get("reason") or "PROVIDER_PREFLIGHT_REJECTED")
        for batch in batches:
            del batch["members"]
            batch["tokens"] = math.ceil(batch["tokens"] * PLAN_DRIFT_MARGIN)
        rounds = reduction_rounds(len(batches))
        tokens = [batch["tokens"] for batch in batches]
        sizes = [len(batch["instrument_ids"]) for batch in batches]
        run.plan = {
            "order": "sha256(result_set|instrument_id)", "batches_planned": len(batches), "reduction_rounds_planned": rounds,
            "rows_planned": sum(sizes), "batch_rows_max": max(sizes, default=0),
            "batch_rows_average": round(sum(sizes) / len(sizes), 2) if sizes else 0,
            "packet_bytes_max": max((batch["packet_bytes"] for batch in batches), default=0),
            "batch_tokens_max": max(tokens, default=0), "largest_batch_tokens": max(tokens, default=0),
            "context_window": window, "reserved_output_tokens": output, "reference_evidence_thinned": thinned,
            "drift_margin": PLAN_DRIFT_MARGIN,
            "required": budget_requirement(tokens, rounds), "budget_basis": "PROVIDER_WORST_CASE" if self._budget is not None else "UNCAPPED_ENGINE",
            "provider_count": measured, "preflight_rejected": rejected,
        }
        return batches

    # ------------------------------------------------------------ model call

    def _call(self, run: _Run, instrument_ids: list[str], *, stage: str, index: int, total: int, planned_tokens: int,
              first_pass: bool, round_number: int | None = None) -> dict[str, Any]:
        """One bounded request on evidence acquired for it. Never retried."""
        from ..intelligence.inference.anthropic_synthesis import drawing_from_hold
        from .screener_news_evidence import attach_news, fit_news

        service = self.service
        raw = self._current_rows(run, instrument_ids)
        news = service._news_for(run.universe, raw, refresh=True)
        market, market_reason = service._market(run.universe, raw, acquire=True)
        now = _iso(service._clock())
        run.cutoffs["first_batch"] = run.cutoffs["first_batch"] or now
        run.cutoffs["last_batch" if first_pass else "final"] = now
        candidates, _ = service._candidates(run.universe, run.envelope, raw, market=market, now=now, include_flow=True)
        for key, candidate in zip(instrument_ids, candidates):
            if key in news:
                attach_news(candidate, news[key], now=now)
        refused = market.refused if market is not None else frozenset()
        dropped: dict[str, list[Any]] = {}
        keep: list[dict[str, Any]] = []
        for key, candidate in zip(instrument_ids, candidates):
            if candidate["sufficient"]:
                keep.append(candidate)
            else:
                # Sufficient when classified, not at this request's cutoff: reported by its own reason, never sent.
                dropped[key] = list(classify(candidate, provider_reason=market_reason, refused=key in refused))
        call_id = f"{stage}:{round_number or 0}:{index}"
        result: dict[str, Any] | None = None
        failure: str | None = None
        try:
            fit_news(run.scope, keep, news, now=now)
            for candidate in [item for item in keep if not item["sufficient"]]:
                # Reference evidence removed to fit the packet was this row's only second item.
                keep.remove(candidate)
                dropped[candidate["instrument"]["instrument_id"]] = [UNPROCESSED, ["EVIDENCE_THINNED_BY_PACKET_CAP"]]
            submitted = [candidate["instrument"]["instrument_id"] for candidate in keep]
            if keep:
                self.ledger().append(run.run_id, "batch_started", {
                    "call_id": call_id, "stage": stage, "round": round_number, "index": index, "of": total,
                    "instrument_ids": submitted, "evidence_cutoff": now, "planned_tokens": planned_tokens,
                    "request_started_at": _iso(service._clock())})
                position = {"batch": index + 1, "batches_planned": total} if first_pass else {"group": index + 1, "groups": total}
                with relabelled(stage, round=round_number, **position):
                    if run.hold:
                        with drawing_from_hold(run.run_id, planned_tokens):
                            result = self._reducer.reduce(run.scope, keep, now)
                    else:
                        result = self._reducer.reduce(run.scope, keep, now)
                # A request answered from the reducer's cache was not sent again and is not counted as a model call.
                if result.get("cache") == "HIT":
                    run.cache_hits += 1
                else:
                    run.calls += 1
                if result["state"] not in _ANSWERED:
                    failure = str(result.get("reason") or result["state"])
        except ValueError as exc:
            if str(exc) != "EVIDENCE_PACKET_BOUND_EXCEEDED":
                raise
            submitted = [candidate["instrument"]["instrument_id"] for candidate in keep]
            failure = "EVIDENCE_PACKET_BOUND_EXCEEDED"
            # The request was announced and never sent: close its receipt so it is not read as an unknown outcome.
            self.ledger().append(run.run_id, "batch", {
                "call_id": call_id, "stage": stage, "round": round_number, "index": index, "of": total, "outcome": "NOT_SENT",
                "state": "FAILED", "reason": failure, "evidence_cutoff": now, "instrument_ids": submitted, "dropped": dropped, "selected": []})
        picks = (result or {}).get("candidates", []) if failure is None else []
        if result is not None:
            if result.get("cache") == "MISS":
                run.tokens_input += int(result.get("tokens_input") or 0)
                run.tokens_output += int(result.get("tokens_output") or 0)
            unknown = failure is not None and failure.endswith("TIMEOUT")
            self.ledger().append(run.run_id, "batch", {
                "call_id": call_id, "stage": stage, "round": round_number, "index": index, "of": total,
                "outcome": "COMPLETED" if failure is None else "UNKNOWN_PROVIDER_OUTCOME" if unknown else "FAILED",
                "state": result["state"], "reason": result.get("reason"), "validation": result.get("validation"),
                "reduction_run_id": result["run_id"], "input_hash": result["input_hash"], "packet_bytes": result["packet_bytes"],
                "output_schema_hash": result["output_schema_hash"], "cache": result["cache"],
                "tokens_input": result.get("tokens_input"), "tokens_output": result.get("tokens_output"),
                "latency_ms": result.get("latency_ms"), "provider_request_id": result.get("provider_request_id"),
                "evidence_cutoff": now, "completed_at": result.get("generated_at"), "valid_until": result.get("valid_until"),
                "instrument_ids": submitted, "dropped": dropped,
                "selected": [{"instrument_id": pick["instrument_id"], "rank": pick["rank"]} for pick in picks]})
        if first_pass:
            for key, value in dropped.items():
                # Eligible when classified, not sendable at this request: an eligible row the model never saw. It is
                # unprocessed, with the reason it could not be sent, and the run cannot be complete.
                reasons = list(value[1]) if value[0] == UNPROCESSED else [f"{value[0]}_AT_REQUEST_CUTOFF", *value[1]]
                run.classes[key] = (UNPROCESSED, reasons)
            if failure is None:
                for key in submitted:
                    run.classes[key] = (AI_EVALUATED, [])
                run.submitted += len(submitted)
                run.finalists.extend({"instrument_id": pick["instrument_id"], "batch": index + 1, "rank_in_batch": pick["rank"],
                                      "rationale": pick["rationale"], "evidence_cutoff": now,
                                      "valid_until": result["valid_until"]} for pick in picks)
        else:
            run.excluded_finalists.extend({"instrument_id": key, "round": round_number, "class": value[0], "reasons": list(value[1]),
                                           "evidence_cutoff": now} for key, value in dropped.items())
        return {"result": result if failure is None else None, "failure": failure, "submitted": submitted, "dropped": dropped}

    @staticmethod
    def _partial_reason(failure: str) -> str:
        return "BUDGET_EXHAUSTED_MID_RUN" if failure in _BUDGET_REASONS else "BATCH_FAILED:" + failure

    @staticmethod
    def _unprocessed(run: _Run, batches: list[dict[str, Any]], reason: str) -> None:
        for batch in batches:
            for key in batch["instrument_ids"]:
                if run.classes[key][0] in (ELIGIBLE, UNPROCESSED):
                    run.classes[key] = (UNPROCESSED, [reason])

    # -------------------------------------------------------------- terminal

    def _release(self, run: _Run) -> None:
        if run.hold and self._budget is not None:
            run.budget["released"] = self._budget.release(run.run_id)
            run.hold = False

    def _record_rows(self, run: _Run, phase: str) -> None:
        if phase == "FINAL":
            if run.final_rows_recorded:
                return
            run.final_rows_recorded = True
        rows = [[key, *run.classes[key]] for key in run.order if key in run.classes]
        for index, group in enumerate(chunks(rows, ROWS_PER_RECORD)):
            self.ledger().append(run.run_id, "rows", {"phase": phase, "part": index, "rows": group})

    def _block(self, run: _Run, status: str, reason: str | None) -> dict[str, Any]:
        counts = tally(run.classes)
        # Every enumerated row is in exactly one bucket, or the run is not complete whatever else happened.
        reconciled = bool(run.enumeration.get("complete")) and reconciles(counts, run.universe_count or 0)
        planned = (run.plan or {}).get("batches_planned", 0)
        coverage_complete = reconciled and counts["unprocessed"] == 0 and run.batches_completed == planned \
            and status not in (FAILED, STOPPED, ENUMERATION_FAILED, BUDGET_INSUFFICIENT, PROVISIONAL_PARTIAL_COVERAGE, INTERRUPTED,
                               EVIDENCE_PROVIDER_UNAVAILABLE)
        eligible_now = counts["evaluated"] + counts["unprocessed"]
        return {
            "method_version": METHOD_VERSION, "method_name": METHOD_NAME, "coverage_run_id": run.run_id,
            "software_sha": self.identity["software_sha"], "status": status, "reason": reason,
            "universe_count": run.universe_count, "enumeration": run.enumeration, "assessed_count": len(run.classes),
            "eligible_count": run.eligible_count, "counts": counts, "reconciled": reconciled,
            "ai_evaluated_count": counts["evaluated"],
            "ai_coverage_pct": round(100 * counts["evaluated"] / eligible_now, 2) if eligible_now else None,
            "batches_planned": planned, "batches_completed": run.batches_completed, "model_calls": run.calls,
            "answers_from_cache": run.cache_hits,
            "plan": run.plan, "reduction": {"rounds_planned": len((run.plan or {}).get("reduction_rounds_planned", [])),
                                           "rounds_completed": run.rounds_completed,
                                           # Finalists whose evidence was no longer admissible when a comparison was due.
                                           "finalists_excluded": run.excluded_finalists[:MAX_EXCLUDED_LISTED],
                                           "finalists_excluded_count": len(run.excluded_finalists)},
            "finalist_count": len({item["instrument_id"] for item in run.finalists}),
            "budget": {**run.budget, "tokens_input": run.tokens_input, "tokens_output": run.tokens_output},
            "coverage_complete": coverage_complete, "selection_complete": coverage_complete and status in SELECTION_COMPLETE,
            "cutoffs": run.cutoffs, "timings_ms": {key: round(value, 1) for key, value in run.timings.items()},
        }

    def _terminal(self, run: _Run, status: str, reason: str | None = None, *, final: dict[str, Any] | None = None) -> dict[str, Any]:
        service = self.service
        self._release(run)
        block = self._block(run, status, reason)
        now = _iso(service._clock())
        common = {"scope": run.scope or None, "matched_count": run.universe_count or 0, "intake_count": run.submitted,
                  "max_intake": MAX_INTAKE, "result_set": (run.scope or {}).get("result_set")}
        if status == GLOBAL_SELECTION_COMPLETE and final is not None and block["selection_complete"]:
            block["selected_count"] = len(final["candidates"])
            block["reduction_run_id"] = final["run_id"]
            # Stored under this run's own id: the reducer's request id stays on the receipt as reduction_run_id.
            record = {**final, "run_id": "CU-" + run.run_id[:40], "universe_coverage": block}
            if run.excluded_finalists:
                record["limitations"] = [*record.get("limitations", []), f"{len(run.excluded_finalists)} batch finalist(s) had no admissible "
                                         "current evidence when the final comparison was made and were not compared."]
            repository = self._repository
            if repository is None:
                from ..local_state.action_decisions import action_repository

                repository = action_repository()
            report_stage("STORED")
            try:
                repository.put("candidate_run", record["run_id"], record)
            except ValueError as exc:
                # The final record could not be stored (for example it exceeds the store's bound): nothing is actionable.
                final, status, reason = None, FAILED, str(exc)
                block = self._block(run, status, reason)
            else:
                result = {**record, "schema_version": RESULT_SCHEMA_VERSION, **common}
        if not (status == GLOBAL_SELECTION_COMPLETE and final is not None and block["selection_complete"]):
            if status == GLOBAL_SELECTION_COMPLETE:
                # Never label a run complete that the accounting says is not.
                status, block["status"], block["reason"] = PROVISIONAL_PARTIAL_COVERAGE, PROVISIONAL_PARTIAL_COVERAGE, "ACCOUNTING_INCOMPLETE"
            block["selected_count"] = 0
            provisional = [] if block["selection_complete"] else [dict(item) for item in run.finalists]
            result = {
                "schema_version": RESULT_SCHEMA_VERSION, "run_id": run.run_id, "candidates": [], "evidence": [],
                "state": "NO_GROUNDED_CANDIDATES" if block["selection_complete"] else "INCOMPLETE", "reason": status,
                "provisional": provisional, "universe_coverage": block, "decision_cutoff": run.cutoffs["last_batch"] or run.cutoffs["classification"] or now,
                "generated_at": now, "valid_until": now, "input_hash": input_hash_from_dict({"run_id": run.run_id, "status": status}),
                "packet_bytes": 0, "cache": "MISS", "simulated": False, "limitations": [_LIMITATIONS.get(status, status)],
                "coverage": {"candidate_intake": run.submitted, "selected": 0, "evidence_items": 0, "blocked_items": 0, "missing_items": 0},
                **{key: self.identity[key] for key in ("provider_id", "model_id", "runtime", "prompt_id", "prompt_version", "prompt_hash", "wire_schema_version")},
                **common}
        if run.classes:
            self._record_rows(run, "FINAL")
        self.ledger().append(run.run_id, "terminal", {
            "account_id": run.account_id, "status": status, "reason": block["reason"], "finished_at": now,
            "candidate_run_id": result["run_id"] if status == GLOBAL_SELECTION_COMPLETE else None,
            "selected": [{"instrument_id": pick["instrument_id"], "rank": pick["rank"]} for pick in result["candidates"]],
            # Identities only, bounded: rationales stay in the per-request receipts and the returned result.
            "provisional": [{key: item[key] for key in ("instrument_id", "batch", "rank_in_batch")}
                            for item in result.get("provisional", [])[:MAX_TERMINAL_FINALISTS]],
            "provisional_count": len(result.get("provisional", [])),
            "universe_coverage": {key: value for key, value in block.items() if key != "plan"}, "scope": run.scope or None})
        run.terminal = result
        return result


def interrupt_open_runs(ledger: Any, *, tracked: Any, release: Callable[[str], Any], clock: Callable[[], float] = time.time) -> list[str]:
    """Close runs a previous process left open. Nothing is resumed: quote evidence older than a minute cannot
    be reused, so a new Run is a new run. A call left without an outcome stays charged; only the part of the
    run's hold that was never reserved is released."""
    closed = []
    for run_id in ledger.open_runs():
        # Asked per run, at the moment of closing it: a run that started while this loop ran is never closed.
        if run_id in tracked:
            continue
        head = ledger.records(run_id, "run")[0]
        unfinished = ledger.unfinished_batches(run_id)
        completed = ledger.records(run_id, "batch")
        try:
            released = release(run_id)
        except Exception:  # noqa: BLE001 - recovery never fails startup; an unreleased hold expires with the UTC day
            released = None
        ledger.append(run_id, "terminal", {
            "account_id": head.get("account_id"), "status": INTERRUPTED, "reason": "SERVER_RESTARTED_DURING_RUN",
            "finished_at": _iso(clock()), "candidate_run_id": None, "selected": [], "provisional": [],
            "unknown_provider_outcomes": [{"call_id": item["call_id"], "instrument_ids": item["instrument_ids"],
                                           "planned_tokens": item["planned_tokens"]} for item in unfinished],
            "calls_completed": len(completed), "hold_released": released,
            "universe_coverage": {"method_version": METHOD_VERSION, "method_name": METHOD_NAME, "coverage_run_id": run_id,
                                  "status": INTERRUPTED, "reason": "SERVER_RESTARTED_DURING_RUN",
                                  "coverage_complete": False, "selection_complete": False},
            "scope": None})
        closed.append(run_id)
    return closed


__all__ = ["BUDGET_INSUFFICIENT", "COMPLETE_NO_SELECTION", "EMPTY_UNIVERSE", "ENUMERATION_FAILED", "EVIDENCE_PROVIDER_UNAVAILABLE", "FAILED",
           "GLOBAL_SELECTION_COMPLETE", "INTERRUPTED", "NO_ELIGIBLE_ROWS", "PROVISIONAL_PARTIAL_COVERAGE",
           "SELECTION_COMPLETE", "STOPPED", "ScreenerAiCoverage", "interrupt_open_runs"]
