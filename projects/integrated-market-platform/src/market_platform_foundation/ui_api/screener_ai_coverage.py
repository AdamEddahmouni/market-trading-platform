"""Full-universe AI Screener run: enumerate, account, shortlist, batch, reduce globally, report truthfully.

One run reads every row of the active Screener query and classifies each with the gates that already exist.
By default the deterministic opportunity shortlist (``opportunity_shortlist``) then ranks every eligible row
and only its model-sized head is sent; ``IMP_AI_SCREENER_SHORTLIST=0`` sends every eligible row as before.
Rows are sent in bounded batches, and the batch finalists are compared until one request holds them all.
That last request's answer, made on evidence acquired for it, is the only thing stored as a
``candidate_run`` and so the only thing the Action Decision layer can load. Anything short of that is
reported as what it is: batch finalists are provisional and are never stored as a candidate run.

Every model call is the existing ``CandidateReducer`` request (prompt v3, ``ai-screener-wire/3.0.0``).
This module adds no retry and no trading threshold, and has no execution authority.
"""
from __future__ import annotations

import math
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

from ..intelligence.inference.candidate_reduction import (
    MAX_INTAKE, MAX_PACKET_BYTES, MAX_SELECTED, PROMPT_ID, SCHEMA_VERSION as OUTPUT_SCHEMA_VERSION, WIRE_SCHEMA_VERSION,
    output_schema,
)
from ..intelligence.inference.coverage_plan import (
    AI_EVALUATED, AI_REJECTED, ELIGIBLE, INELIGIBLE, METHOD_NAME, METHOD_VERSION, NOT_SHORTLISTED, PROVIDER_UNAVAILABLE,
    UNPROCESSED, budget_requirement, chunks, classify, fair_order, reconciles, reduction_rounds, tally,
)
from ..intelligence.inference import opportunity_shortlist
from ..intelligence.inference.hashing import input_hash_from_dict
from ..intelligence.inference.evidence_compaction import OPTIMIZER_VERSION, semantic_hash
from ..intelligence.inference.run_progress import relabelled, report_stage
from .screener_ai_universe import UniverseEnumerationError, enumerate_universe

RESULT_SCHEMA_VERSION = "screener-ai-screener/1.0.0"
# One identity per serving process. A run ledger head carries it, so recovery can distinguish a genuine
# previous-process restart from a run of this process whose terminal receipt was lost to a write failure.
BOOT_ID = uuid.uuid4().hex
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
# A rolling slice (an AUTOMATION run with a slice plan): every row deterministically classified, the AI applied to
# the rows its time budget reached in coverage-epoch order, those rows' finalists compared. Never a global selection.
SLICE_SELECTION_COMPLETE = "SLICE_SELECTION_COMPLETE"
SLICE_COMPLETE_NO_SELECTION = "SLICE_COMPLETE_NO_SELECTION"
SLICE_STATUSES = frozenset({SLICE_SELECTION_COMPLETE, SLICE_COMPLETE_NO_SELECTION})
# A model answer the unchanged validator rejected (or one that reached its output allowance) is that row's outcome:
# the row is AI_REJECTED and the run continues. Too many in one run end it, as a provider fault would.
REJECTION_BREAKER_MIN_REJECTED = 10
REJECTION_BREAKER_RATE = 0.5
# In a slice the time box bounds the cost, so only an engine that answers nothing acceptably stops dispatch.
REJECTION_SYSTEMIC_MIN_REJECTED = 20
# A batch answer the run can build on. EXPIRED is a valid answer whose evidence aged out while the model worked;
# its picks are still finalists, because the final round re-acquires evidence for every finalist.
_ANSWERED = frozenset({"CURRENT", "NO_GROUNDED_CANDIDATES", "EXPIRED"})
_BUDGET_REASONS = frozenset({"SYNTHESIS_RUN_HOLD_EXHAUSTED", "SYNTHESIS_RUN_HOLD_MISSING", "SYNTHESIS_DAILY_REQUEST_LIMIT",
                             "SYNTHESIS_DAILY_TOKEN_LIMIT", "PAID_AI_DAILY_DOLLAR_CAP", "PAID_AI_MONTHLY_DOLLAR_CAP"})
# A free token count that failed for a reason unrelated to the request itself; the plan keeps its estimate.
_PREFLIGHT_SKIPPED = frozenset({"API_KEY_MISSING", "COUNT_TOKENS_UNSUPPORTED", "ANTHROPIC_TIMEOUT", "ANTHROPIC_UNREACHABLE",
                                "ANTHROPIC_AUTH_FAILED"})
ROWS_PER_RECORD = 2000
# Evidence is re-acquired for every request, so a request can be slightly larger than the packet it was planned
# from. Each planned call is held with this margin; a call that still exceeds its hold ends the run as partial.
PLAN_DRIFT_MARGIN = 1.05
# Local context-fit resends: canonical JSON measured 2.86 bytes per Qwen token on the October 16 crypto packet;
# a lower ratio removes more evidence per attempt, so fewer attempts are needed.
CONTEXT_FIT_ATTEMPTS = 2
CONTEXT_FIT_BYTES_PER_TOKEN = 2.5
# A local reduction is planned against the exact context budget before the request is sent. The provider's
# free count is authoritative; a group over budget is split without generation. The hard bounds below stop a
# pathological finalist set from turning that split into an unbounded run. They are call/time budgets, not
# selection thresholds: exceeding one defers the remaining finalists with their own reasons.
REDUCTION_DEADLINE_SECONDS = 180.0
REDUCTION_REQUESTS_PER_FINALIST = 6
REDUCTION_REQUESTS_FLOOR = 12
# 2026-10-23 crypto: six finalists in pairs and byes, both pairs' answers rejected, and the run ended with every
# entrant advanced. A round that advances everyone is followed by at most this many freshly paired rounds.
NO_PROGRESS_ROUNDS = 2
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
    SLICE_SELECTION_COMPLETE: "A rolling slice: every row was classified, but only the rows this run's time budget reached were evaluated by the model and compared. This is not a global selection.",
    SLICE_COMPLETE_NO_SELECTION: "A rolling slice: the rows this run's time budget reached were evaluated and compared; none was selected. Rows outside the slice were not evaluated.",
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
        # Exact counts of requests refused before generation (context fit). Never model input or spend.
        self.counted_not_sent = 0
        self.rejected = 0
        self.first_rejection: str | None = None
        # Local comparisons: the smallest group the exact send-time count refused in this run, and how many groups
        # were split before sending because they were at least that large.
        self.refused_group: int | None = None
        self.presplit = 0
        # Context-bounded reduction receipts: requests attempted (including refusals before generation), the
        # groups/rounds they formed, and the budget the plan was measured against.
        self.reduction_requests = 0
        self.reduction_not_sent = 0
        self.reduction_budget: dict[str, Any] = {}
        self.reduction_rounds: list[dict[str, Any]] = []
        # Pairs/singles whose exact count still refused the full evidence: the comparison saw current-market
        # evidence plus one non-news reference item, never a truncated current quote. The full evidence
        # remains in the first-pass batch receipts.
        self.comparison_compacted = 0
        # Slices only: finalists that could not be compared (not admissible at the comparison cutoff, thinned below
        # sufficiency, or whose single-finalist comparison answer was rejected). They are deferred, never selected.
        self.deferred_finalists = 0
        self.comparison_rejected = 0
        # True once this run, under a slice plan, ends with eligible rows the model did not answer.
        self.sliced = False
        self.timings: dict[str, float] = {}
        # The opportunity shortlist this run applied, or None when every eligible row was sent.
        self.shortlist: dict[str, Any] | None = None
        self.terminal: dict[str, Any] | None = None
        self.cutoffs: dict[str, str | None] = {"classification": None, "first_batch": None, "last_batch": None, "final": None}


class ScreenerAiCoverage:
    def __init__(self, service: Any, *, ledger: Any | None = None, software_sha: str | None = None,
                 repository: Any | None = None, adaptive_batches: bool | None = None, shortlist: bool | None = None) -> None:
        self.service = service
        self._ledger = ledger
        self._software_sha = software_sha
        # Where the one final candidate run is stored: the same repository the Action Decision layer reads.
        self._repository = repository
        self.adaptive_batches = (os.environ.get("IMP_AI_SCREENER_ADAPTIVE_BATCHES") == "1"
                                 if adaptive_batches is None else adaptive_batches)
        self.shortlist = opportunity_shortlist.enabled() if shortlist is None else shortlist

    def ledger(self) -> Any:
        if self._ledger is None:
            from ..local_state.ai_screener_coverage import coverage_ledger

            self._ledger = coverage_ledger()
        return self._ledger

    # ------------------------------------------------------------------ run

    def run(self, body: dict[str, Any], *, run_id: str, account_id: str,
            should_stop: Callable[[], bool] = lambda: False, spend_limit: dict[str, int] | None = None,
            slice_plan: dict[str, Any] | None = None) -> dict[str, Any]:
        # AUTO-01: an owner cap on what an unattended run may hold. It can only refuse a plan, never enlarge one.
        self._spend_limit = spend_limit
        # A rolling slice, local engine only: ``deadline_epoch`` ends the first pass on the service clock, and
        # ``last_turn`` (instrument id -> epoch seconds of the row's last evaluated, rejected or refused outcome)
        # orders rows with no recent turn first, then the oldest turn, so a row whose answer was just rejected waits
        # behind the rest instead of heading every slice. ``last_evaluated`` (AI_EVALUATED only) is reported, and
        # orders the slice when no turns are given. The fair order breaks every tie. No score, no threshold.
        self._slice = dict(slice_plan) if slice_plan else None
        service = self.service
        query = service._query(body)
        reducer = service._provider_reducer()
        provider = reducer.provider
        prompt = reducer.registry.get_by_id(reducer.prompt_id)
        run = _Run(run_id, account_id)
        run.scope = service._scope(query, {"result_set_id": query["result_set"]})
        run.query = query
        runtime = (getattr(provider, "runtime", None) or "PAID_API") if provider is not None else None
        # Sized to the engine that will run; an invalid override refuses the run before anything is recorded.
        self._shortlist_size = opportunity_shortlist.size_for(runtime) if self.shortlist else None
        self.identity = {
            "account_id": account_id,
            "method_version": opportunity_shortlist.METHOD_VERSION if self.shortlist else METHOD_VERSION,
            "method_name": opportunity_shortlist.METHOD_NAME if self.shortlist else METHOD_NAME,
            "shortlist": {"policy_id": opportunity_shortlist.POLICY_ID, "size": self._shortlist_size} if self.shortlist else None,
            "optimizer_version": OPTIMIZER_VERSION, "compact_input": reducer.compact_input,
            "software_sha": self._software_sha or _software_sha(), "boot_id": BOOT_ID,
            "provider_id": getattr(provider, "provider_id", None), "model_id": getattr(provider, "model_id", None),
            "runtime": runtime, "prompt_id": prompt.prompt_id, "prompt_version": prompt.version, "prompt_hash": prompt.content_hash,
            "wire_schema_version": WIRE_SCHEMA_VERSION, "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "limits": {"max_batch_rows": MAX_INTAKE, "max_selected": MAX_SELECTED, "max_packet_bytes": MAX_PACKET_BYTES},
            "query": {key: query[key] for key in ("universe", "search", "sort", "descending", "filters", "view", "screen")},
            "requested_result_set": query["result_set"], "started_at": _iso(service._clock()),
        }
        if self._slice and getattr(provider, "runtime", None) != "LOCAL_MODEL":
            self._slice = None  # a paid engine plans and holds the whole run; it is never sliced
        if self._slice:
            self.identity["slice_plan"] = {"epoch": self._slice.get("epoch"), "deadline": _iso(float(self._slice["deadline_epoch"]))
                                           if self._slice.get("deadline_epoch") is not None else None,
                                           "rows_with_prior_evaluation": len(self._slice.get("last_evaluated") or {})}
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
        if self.shortlist:
            mark = time.perf_counter()
            report_stage("SHORTLIST", eligible_count=run.eligible_count)
            eligible = self._shortlist(run, eligible, candidates)
            run.timings["shortlist_ms"] = (time.perf_counter() - mark) * 1000
            report_stage("SHORTLIST", eligible_count=run.eligible_count, shortlisted_count=len(eligible))
            if not eligible:
                return self._terminal(run, NO_ELIGIBLE_ROWS, "NO_ROW_ABOVE_TRADABILITY_FLOOR")
        refusal = self._engine_refusal()
        if refusal:
            for key in eligible:
                run.classes[key] = (UNPROCESSED, [refusal])
            return self._terminal(run, FAILED, refusal)

        mark = time.perf_counter()
        report_stage("PLANNING", eligible_count=run.eligible_count)
        report_stage("TOKEN_PLANNING", eligible_count=run.eligible_count)
        batches = self._plan(run, eligible, candidates, should_stop=should_stop)
        del candidates
        run.timings["planning_ms"] = (time.perf_counter() - mark) * 1000
        report_stage("REUSE_ASSESSMENT", batches_planned=len(batches), required_tokens=run.plan["required"]["tokens"] if self._budget is not None else None)
        if run.plan.get("preflight_rejected"):
            if should_stop():
                # A Stop reached the exact count: planned rows were cancelled, not rejected by the provider.
                self._unprocessed(run, batches, "STOPPED_BY_OPERATOR")
                return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")
            self._unprocessed(run, batches, "PROVIDER_PREFLIGHT_REJECTED")
            return self._terminal(run, FAILED, run.plan["preflight_rejected"])
        if run.shortlist is not None:
            run.plan["shortlist"] = run.shortlist
        if not batches:
            return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "NO_ROW_FITS_ONE_REQUEST")
        limit = getattr(self, "_spend_limit", None)
        if self._budget is not None and limit is not None and (
                run.plan["required"]["requests"] > limit["requests"] or run.plan["required"]["tokens"] > limit["tokens"]):
            # Nothing is held and no model is called: the plan exceeds what the owner authorized for unattended runs.
            run.budget = {"capped": True, "held": False, "reason": "AUTONOMOUS_SPENDING_LIMIT",
                          "required_requests": run.plan["required"]["requests"], "required_tokens": run.plan["required"]["tokens"],
                          "available_requests": limit["requests"], "available_tokens": limit["tokens"],
                          "available_basis": "OWNER_AUTONOMOUS_LIMIT"}
            run.plan.update(feasible_under_current_limits=False)
            self._unprocessed(run, batches, "BUDGET_INSUFFICIENT")
            return self._terminal(run, BUDGET_INSUFFICIENT, "AUTONOMOUS_SPENDING_LIMIT")
        if self._budget is not None:
            held = self._budget.hold(run.run_id, requests=run.plan["required"]["requests"], tokens=run.plan["required"]["tokens"])
            run.budget = {"capped": True, **held}
            run.plan.update(available_request_budget=held["available_requests"],available_token_budget=held["available_tokens"],
                            feasible_under_current_limits=held["held"])
            if not held["held"]:
                self._unprocessed(run, batches, "BUDGET_INSUFFICIENT")
                return self._terminal(run, BUDGET_INSUFFICIENT, held["reason"])
            run.hold = True
            report_stage("BUDGET_HELD", held_tokens=held["required_tokens"], held_requests=held["required_requests"])
        self.ledger().append(run.run_id, "plan", {"plan": run.plan, "budget": run.budget})

        mark = time.perf_counter()
        last: dict[str, Any] | None = None
        sent_failure: str | None = None  # first true provider/outcome failure; reported as the terminal reason
        deadline = (self._slice or {}).get("deadline_epoch")
        for index, batch in enumerate(batches):
            if should_stop():
                self._unprocessed(run, batches[index:], "STOPPED_BY_OPERATOR")
                return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")
            if deadline is not None and service._clock() >= float(deadline):
                # The slice's time budget is spent: the rest are deferred to later slices of this epoch, not dropped.
                self._unprocessed(run, batches[index:], "DEFERRED_TO_NEXT_SLICE")
                break
            outcome = self._call(run, batch["instrument_ids"], stage="BATCH_INFERENCE", index=index, total=len(batches),
                                 planned_tokens=batch["tokens"], first_pass=True, reuse_only=batch.get("cached",False), should_stop=should_stop)
            if outcome["failure"]:
                if should_stop():
                    self._unprocessed(run, [{"instrument_ids": outcome["submitted"]}], "STOPPED_BY_OPERATOR")
                    self._unprocessed(run, batches[index + 1:], "STOPPED_BY_OPERATOR")
                    return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")
                if outcome["rejected"]:
                    # The model answered and the unchanged validator refused the answer: this row's outcome only.
                    for key in outcome["submitted"]:
                        run.classes[key] = (AI_REJECTED, [outcome["failure"]])
                    run.rejected += 1
                    run.first_rejection = run.first_rejection or outcome["failure"]
                    run.batches_completed += 1
                    if self._slice:
                        # October 17-18: about two thirds of the news-heavy rows were rejected, so the half-rejected
                        # breaker ended every slice after 14 requests. The time box bounds a slice; only an engine
                        # whose every answer is rejected is stopped.
                        tripped = run.rejected >= REJECTION_SYSTEMIC_MIN_REJECTED and run.rejected == run.batches_completed
                        reason = "AI_REJECTION_SYSTEMIC"
                    else:
                        tripped = run.rejected >= REJECTION_BREAKER_MIN_REJECTED and run.rejected > REJECTION_BREAKER_RATE * run.batches_completed
                        reason = "AI_REJECTION_RATE_EXCEEDED"
                    if tripped:
                        self._unprocessed(run, batches[index + 1:], "NOT_STARTED_AFTER_REJECTION_RATE")
                        return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, reason)
                    continue
                self._unprocessed(run, [{"instrument_ids": outcome["submitted"]}], "BATCH_FAILED:" + outcome["failure"])
                if sent_failure is None:
                    sent_failure = outcome["failure"]
                if outcome["failure"] == "LOCAL_CONTEXT_EXCEEDED":
                    # The send-time exact-fit gate is per request. Evidence re-acquired for this batch's own cutoff
                    # rendered over the window, but each remaining batch is its own bounded request measured again
                    # by the same gate when it is sent, so one batch's oversize is evidence about that request only.
                    continue
                self._unprocessed(run, batches[index + 1:], "NOT_STARTED_AFTER_BATCH_FAILURE")
                return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, self._partial_reason(outcome["failure"]))
            run.batches_completed += 1
            last = outcome["result"] or last
            report_stage("BATCH_INFERENCE", batch=index + 1, batches_planned=len(batches), batches_completed=run.batches_completed,
                         rows_evaluated=run.submitted)
        run.timings["batch_inference_ms"] = (time.perf_counter() - mark) * 1000

        if should_stop():
            return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")

        if run.rejected and not self._slice:
            # Every row was sent, but some answers were rejected: the comparison cannot include those rows.
            return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "BATCH_FAILED:" + str(run.first_rejection))
        if run.rejected:
            run.sliced = True  # rejected rows are not evaluated for the epoch; later slices take them first
        if any(name == UNPROCESSED for name, _ in run.classes.values()):
            if not self._slice:
                # Every planned call ran, but a row that could not be sent (too large, thinned below sufficiency) remains.
                reason = self._partial_reason(sent_failure) if sent_failure is not None else "ELIGIBLE_ROWS_NOT_SUBMITTED"
                return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, reason)
            # A slice: unanswered rows keep their own reasons and later slices of the epoch take them first.
            run.sliced = True
        if not run.finalists:
            return self._terminal(run, SLICE_COMPLETE_NO_SELECTION if run.sliced else COMPLETE_NO_SELECTION)
        if run.batches_completed - run.rejected == 1 and last is not None:
            # One answer holds every finalist (rejected answers hold none); its evidence was acquired for it.
            return self._final(run, last)

        mark = time.perf_counter()
        pool = list(dict.fromkeys(item["instrument_id"] for item in run.finalists))
        number = 0
        local = getattr(self._provider, "runtime", None) == "LOCAL_MODEL"
        stalled = 0
        reduction_started = time.monotonic()
        reduction_requests = max(REDUCTION_REQUESTS_FLOOR, REDUCTION_REQUESTS_PER_FINALIST * len(pool))
        run.reduction_budget.update(
            context_window=self._context_window(), configured_output=int(self._reducer.config.max_tokens),
            finalists=len(pool), max_requests=reduction_requests, max_seconds=REDUCTION_DEADLINE_SECONDS)
        while True:
            number += 1
            # Once the exact count has refused a comparison size, a round is planned in groups one smaller, so a round
            # is not first planned at the intake size and then halved down to pairs and byes.
            size = run.refused_group - 1 if local and run.refused_group else MAX_INTAKE
            groups = chunks(fair_order(f"{run.scope['result_set']}|round-{number}", pool), size)
            winners: list[str] = []
            final: dict[str, Any] | None = None
            answers: list[dict[str, Any]] = []
            admitted = False
            index = 0
            sequence = 0  # every request of the round has its own call id, including the halves of a split
            round_requests = run.reduction_requests
            round_not_sent = run.reduction_not_sent
            round_compacted = run.comparison_compacted
            while index < len(groups):
                group = groups[index]
                if should_stop():
                    return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")
                exhausted = (run.reduction_requests >= reduction_requests
                             or time.monotonic() - reduction_started > REDUCTION_DEADLINE_SECONDS)
                if exhausted:
                    # The split is bounded. Remaining finalists keep their own reasons and are never selected
                    # on evidence the comparison did not reach.
                    remaining = list(dict.fromkeys(key for later in groups[index:] for key in later))
                    for key in remaining:
                        run.classes[key] = (UNPROCESSED, ["GLOBAL_REDUCTION_BUDGET_EXCEEDED"])
                    run.reduction_budget["exhausted"] = (
                        "REQUESTS" if run.reduction_requests >= reduction_requests else "SECONDS")
                    return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "GLOBAL_REDUCTION_BUDGET_EXCEEDED")
                if local and run.refused_group is not None and len(group) > 1 and len(group) >= run.refused_group:
                    # The send-time count already refused a comparison this large in this run: split it without
                    # another request that would be refused. The halves keep the fair order and each is still counted
                    # exactly when it is sent, so a group that fits is never skipped on a guess.
                    half = math.ceil(len(group) / 2)
                    groups[index:index + 1] = [group[:half], group[half:]]
                    run.presplit += 1
                    continue
                outcome = self._call(run, group, stage="GLOBAL_REDUCTION", index=sequence, total=len(groups),
                                     planned_tokens=run.plan["largest_batch_tokens"], first_pass=False, round_number=number,
                                     reuse_only=run.plan.get("global_reuse_only",False), should_stop=should_stop)
                sequence += 1
                if self._slice and outcome["dropped"]:
                    # In a slice, a finalist that cannot be compared at this cutoff is deferred to a later slice with
                    # its reason; it is never selected, and the slice stays a selection among the rows it compared.
                    self._defer_finalists(run, outcome["dropped"])
                if outcome["failure"]:
                    if should_stop():
                        return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")
                    if self._slice and outcome["invalid"]:
                        # The unchanged validator rejected a comparison answer: compare the group in halves (new requests
                        # on evidence acquired for each); a single finalist whose answer was rejected is deferred.
                        if len(outcome["submitted"]) > 1:
                            half = math.ceil(len(group) / 2)
                            groups[index:index + 1] = [group[:half], group[half:]]
                            continue
                        for key in outcome["submitted"]:
                            run.classes[key] = (AI_REJECTED, ["COMPARISON:" + str(outcome["failure"])])
                        run.comparison_rejected += len(outcome["submitted"])
                        run.sliced = True  # not every eligible row was compared: never a global selection
                        index += 1
                        continue
                    if local and outcome["failure"] in ("LOCAL_CONTEXT_EXCEEDED", "EVIDENCE_PACKET_BOUND_EXCEEDED") \
                            and (self._slice or not outcome["dropped"]
                                 or outcome["failure"] == "EVIDENCE_PACKET_BOUND_EXCEEDED"):
                        # In a slice the dropped finalists were deferred above; the rest of the group is still compared.
                        sendable = [key for key in group if key not in outcome["dropped"]]
                        if len(sendable) > 1:
                            if len(sendable) > 2:
                                # A pair is thinned before it is refused, so a refused pair never shrinks later rounds.
                                run.refused_group = min(run.refused_group or len(sendable), len(sendable))
                            # The exact send-time gate refused this comparison even after thinning: compare it in two
                            # halves, in the same fair order. Each half is its own request on evidence acquired for it.
                            half = math.ceil(len(sendable) / 2)
                            groups[index:index + 1] = [sendable[:half], sendable[half:]]
                            continue
                        if self._slice:
                            # One finalist whose own packet does not fit even thinned: deferred to a later slice with
                            # its reason, never selected; the slice stays a selection among the rows it compared.
                            self._defer_finalists(run, {key: [UNPROCESSED, ["COMPARISON_CONTEXT_EXCEEDED"]] for key in sendable})
                            index += 1
                            continue
                    return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "GLOBAL_REDUCTION_INCOMPLETE:" + outcome["failure"])
                final = outcome["result"]
                if final is not None:
                    answers.append(final)
                admitted = admitted or bool(outcome["submitted"])
                winners.extend(pick["instrument_id"] for pick in (final or {}).get("candidates", []))
                index += 1
            if should_stop():
                return self._terminal(run, STOPPED, "STOPPED_BY_OPERATOR")
            run.rounds_completed = number
            round_receipt = {
                "round": number, "groups": len(groups), "calls": run.reduction_requests - round_requests,
                "entrants": len(pool), "advanced": len(winners),
                "chunk_sizes": [len(group) for group in groups],
                "not_sent": run.reduction_not_sent - round_not_sent,
                "compacted": run.comparison_compacted - round_compacted,
                "context_window": run.reduction_budget.get("context_window"),
                "configured_output": run.reduction_budget.get("configured_output"),
            }
            run.reduction_rounds.append(round_receipt)
            self.ledger().append(run.run_id, "round", round_receipt)
            report_stage("GLOBAL_REDUCTION", round=number, finalists=len(winners))
            if len(groups) > 1 and len(set(winners)) >= len(pool):
                # Every comparison advanced every entrant: another round of the same groups cannot reduce the pool.
                run.timings["global_reduction_ms"] = (time.perf_counter() - mark) * 1000
                if run.excluded_finalists and admitted:
                    return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "FINALISTS_EXCLUDED_AT_FINAL_CUTOFF")
                if len(set(winners)) <= MAX_SELECTED:
                    # Within the selection cap, each entrant was compared and kept by its own group; the union is
                    # recorded as exactly that, with every member answer, and is final only if each is current.
                    return self._final(run, self._union(run, answers))
                if size > 1 and stalled < NO_PROGRESS_ROUNDS:
                    # The next round's fair order is salted by its number, so its groups pair different entrants.
                    stalled += 1
                    pool = list(dict.fromkeys(winners))
                    continue
                return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "GLOBAL_COMPARISON_NO_PROGRESS")
            if run.excluded_finalists and admitted:
                # Required finalists were not compared. Neither a winner nor an abstention
                # from the remaining subset is a completed global selection.
                return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "FINALISTS_EXCLUDED_AT_FINAL_CUTOFF")
            if not winners:
                run.timings["global_reduction_ms"] = (time.perf_counter() - mark) * 1000
                if not admitted:
                    # No finalist had admissible evidence when the comparison was due: nothing was compared.
                    return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "NO_FINALIST_ADMISSIBLE_AT_FINAL_CUTOFF")
                return self._terminal(run, SLICE_COMPLETE_NO_SELECTION if run.sliced else COMPLETE_NO_SELECTION,
                                      "NO_FINALIST_SELECTED_IN_GLOBAL_COMPARISON")
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
        if run.excluded_finalists:
            return self._terminal(run, PROVISIONAL_PARTIAL_COVERAGE, "FINALISTS_EXCLUDED_AT_FINAL_CUTOFF")
        return self._terminal(run, SLICE_SELECTION_COMPLETE if run.sliced else GLOBAL_SELECTION_COMPLETE, final=final)

    def _union(self, run: _Run, answers: list[dict[str, Any]]) -> dict[str, Any] | None:
        """One result from comparisons that each kept all their entrants, within the selection cap.

        Nothing is re-ranked by a new score: picks keep their own group rank and ties go to the fair order. The
        result is CURRENT only while every contributing answer is CURRENT and none of their evidence has expired;
        its lifetime is the shortest of theirs. Each member answer stays on its own receipt."""
        members = [answer for answer in answers if answer.get("candidates")]
        if not members:
            return None
        salt = f"{run.scope['result_set']}|union"
        tie = {key: position for position, key in
               enumerate(fair_order(salt, list(dict.fromkeys(p["instrument_id"] for a in members for p in a["candidates"]))))}
        picks = sorted((pick for answer in members for pick in answer["candidates"]), key=lambda p: (p["rank"], tie[p["instrument_id"]]))
        first: dict[str, dict[str, Any]] = {}
        for pick in picks:
            first.setdefault(pick["instrument_id"], pick)
        candidates = [{**pick, "rank": rank} for rank, pick in enumerate(first.values(), 1)]
        evidence = list({e["instrument"]["instrument_id"]: e for a in members for e in a.get("evidence", [])
                         if e["instrument"]["instrument_id"] in first}.values())
        valid_until = min(a["valid_until"] for a in members)
        now = _iso(self.service._clock())
        current = all(a.get("state") == "CURRENT" for a in members) and now < valid_until
        ids = [a["run_id"] for a in members]
        return {**members[0], "candidates": candidates, "evidence": evidence, "state": "CURRENT" if current else "EXPIRED",
                "valid_until": valid_until, "decision_cutoff": min(a["decision_cutoff"] for a in members),
                "generated_at": max(a.get("generated_at") or now for a in members),
                "run_id": "UN-" + input_hash_from_dict({"members": ids})[:32],
                "input_hash": input_hash_from_dict({"members": [a["input_hash"] for a in members]}),
                "tokens_input": sum(int(a.get("tokens_input") or 0) for a in members),
                "tokens_output": sum(int(a.get("tokens_output") or 0) for a in members),
                "coverage": {**(members[0].get("coverage") or {}), "selected": len(candidates)},
                "composition": {"method": "UNION_OF_GROUP_ANSWERS_WITHIN_SELECTION_CAP", "member_reduction_run_ids": ids}}

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

    def _shortlist(self, run: _Run, eligible: list[str], candidates: dict[str, dict[str, Any]]) -> list[str]:
        """Score every eligible row and keep the model-sized head, best first. The rest are NOT_SHORTLISTED.

        News already received is attached from the cache only (no provider is asked) for every row a full catalyst
        part could still lift into the shortlist, so a row's catalyst does not depend on whether the classification
        happened to read news for it. Nothing here is a trading threshold: the score decides which rows the model
        sees, and the model still makes the pick."""
        from .screener_news_evidence import attach_news

        service = self.service
        now = run.cutoffs["classification"]
        size, salt = int(self._shortlist_size), str(run.scope["result_set"])
        scored = {key: opportunity_shortlist.score(candidates[key], run.rows[key], now=now) for key in eligible}
        unread = {key for key in eligible if "news" not in candidates[key]}
        reach, capped = opportunity_shortlist.news_reach(scored, size=size, salt=salt, unread=unread)
        for group in chunks(reach):
            news = service._news_for(run.universe, [run.rows[key] for key in group], refresh=False)
            for key in group:
                if key in news:
                    attach_news(candidates[key], news[key], now=now)
                scored[key] = opportunity_shortlist.score(candidates[key], run.rows[key], now=now)
        chosen = opportunity_shortlist.shortlist(scored, size=size, salt=salt)
        kept = set(chosen)
        floored = 0
        for key in eligible:
            if key in kept:
                continue
            reason = scored[key]["floor_reason"] or opportunity_shortlist.BELOW_SHORTLIST_CUTOFF
            floored += reason == opportunity_shortlist.BELOW_TRADABILITY_FLOOR
            run.classes[key] = (NOT_SHORTLISTED, [reason])
        run.shortlist = {
            "policy_id": opportunity_shortlist.POLICY_ID, "size": size, "eligible_before_shortlist": len(eligible),
            "shortlisted": len(chosen), "below_tradability_floor": floored,
            "news_read": len(reach), "news_read_capped": capped,
            "cutoff_score": scored[chosen[-1]]["total"] if chosen else None,
            "ranked": [{"instrument_id": key, "rank": index + 1, "total": scored[key]["total"], "parts": scored[key]["parts"],
                        "missing": scored[key]["missing"]} for index, key in enumerate(chosen)],
        }
        return chosen

    def _engine_refusal(self) -> str | None:
        if self._provider is None:
            return self._reducer.reason
        contract = self._reducer.contract()
        return contract["reason"] if contract is not None and not contract["supported"] else None

    # -------------------------------------------------------------- planning

    def _context_window(self) -> int | None:
        from ..intelligence.inference.anthropic_models import CLAUDE_MODELS

        if getattr(self._provider, 'runtime', None) == 'LOCAL_MODEL':
            window = getattr(getattr(getattr(self._provider, '_server', None), 'manifest', None), 'context', None)
            return window if type(window) is int and window > 0 else None
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

    @staticmethod
    def _order_label(run: _Run) -> str:
        return "opportunity_score_desc_then_sha256(result_set|instrument_id)" if run.shortlist is not None \
            else "sha256(result_set|instrument_id)"

    def _plan(self, run: _Run, eligible: list[str], candidates: dict[str, dict[str, Any]], *,
              should_stop: Callable[[], bool] = lambda: False) -> list[dict[str, Any]]:
        """Bounded batches in an order no sort or page can bias, sized by rows, bytes and the model's window."""
        from .screener_news_evidence import attach_news, fit_news

        if getattr(self._provider, 'runtime', None) == 'LOCAL_MODEL':
            return self._plan_local(run, eligible)
        service, reducer = self.service, self._reducer
        now = run.cutoffs["classification"]
        window = self._context_window()
        output = int(reducer.config.max_tokens) + int(getattr(self._provider, "reasoning_headroom", 0) or 0)
        # A shortlist arrives best first; otherwise no sort or page may bias the order.
        ordered = list(eligible) if run.shortlist is not None else fair_order(str(run.scope["result_set"]), eligible)
        pending = chunks(ordered)
        batches: list[dict[str, Any]] = []
        thinned = 0
        measured = None
        rejected = None
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
                if getattr(self._provider, 'runtime', None) == 'LOCAL_MODEL' and not estimate['cached']:
                    check = reducer.preflight(run.scope, members, now, should_stop=should_stop)
                    if check is None:
                        reason = 'LOCAL_CONTEXT_PREFLIGHT_FAILED'
                    elif check.get('context_fit') is False:
                        reason = 'PACKET_EXCEEDS_CONTEXT_WINDOW'
                    elif not check.get('accepted') or type(check.get('input_tokens')) is not int:
                        reason = check.get('reason') or 'LOCAL_CONTEXT_PREFLIGHT_FAILED'
                    else:
                        measured = {key: check.get(key) for key in ('accepted', 'input_tokens', 'context_window', 'context_fit', 'reason')}
                        measured['estimated_input_tokens'] = estimate['input_tokens']
                        estimate['input_tokens'] = check['input_tokens']
                        estimate['tokens'] = check['input_tokens'] + output
                elif window is not None and estimate["input_tokens"] + output > window and not (
                        getattr(self._provider, 'runtime', None) == 'LOCAL_MODEL' and estimate['cached']):
                    reason = "PACKET_EXCEEDS_CONTEXT_WINDOW"
            except ValueError as exc:
                if str(exc) != "EVIDENCE_PACKET_BOUND_EXCEEDED":
                    raise
                reason = "IRREDUCIBLE_PACKET_OVERSIZE"
            if reason is not None:
                if getattr(self._provider, 'runtime', None) == 'LOCAL_MODEL' and reason not in (
                        'PACKET_EXCEEDS_CONTEXT_WINDOW', 'IRREDUCIBLE_PACKET_OVERSIZE'):
                    # An unavailable exact tokenizer/readiness cannot be cured by splitting or restarting.
                    rejected = reason
                    for remaining in [group, *pending]:
                        for key in remaining:
                            run.classes[key] = (UNPROCESSED, [reason])
                    break
                if len(group) == 1:
                    run.classes[group[0]] = (UNPROCESSED, [reason])
                else:
                    half = math.ceil(len(group) / 2)
                    if self.adaptive_batches and reason == "PACKET_EXCEEDS_CONTEXT_WINDOW":
                        # Longest fitting prefix in the same identity order, within the existing 50-row group.
                        # This changes comparison composition and is gated off pending provider quality controls.
                        low, high, fit = 1, len(group)-1, 0
                        while low <= high:
                            middle = (low+high)//2
                            part = reducer.estimate(run.scope,members[:middle],now)
                            if part["input_tokens"] + output <= window:
                                fit, low = middle, middle+1
                            else:
                                high = middle-1
                        half = fit or 1
                    pending[:0] = [group[:half], group[half:]]
                continue
            batches.append({"instrument_ids": group, "packet_bytes": estimate["packet_bytes"], "input_tokens": estimate["input_tokens"],
                            "tokens": estimate["tokens"] if estimate["tokens"] is not None else estimate["input_tokens"] + output,
                            "cached":estimate["cached"], "cached_selected":estimate.get("cached_selected",[]),
                            "members": members})
        misses = [batch for batch in batches if not batch["cached"]]
        if misses and self._budget is not None:
            # The provider's own count of the first request, where it offers one. It bills and reserves nothing.
            check = reducer.preflight(run.scope, misses[0]["members"], now)
            if check is not None:
                measured = {key: check.get(key) for key in ("accepted", "input_tokens", "context_window", "context_fit", "reason")}
                measured["estimated_input_tokens"] = misses[0]["input_tokens"]
                tokens = check.get("input_tokens")
                if check.get("context_fit") is False:
                    rejected = str(check.get("reason") or "PROVIDER_CONTEXT_EXCEEDED")
                elif check.get("accepted") and isinstance(tokens, int) and tokens > misses[0]["input_tokens"]:
                    # The estimate was under the provider's count: raise every batch by the same ratio plus a margin.
                    factor = tokens / misses[0]["input_tokens"] * 1.05
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
        # Complete unchanged first-pass answers determine the comparison context exactly.
        # Reuse a global comparison only if every round is itself an exact valid cache hit.
        global_reuse = bool(batches) and not misses
        pool = list(dict.fromkeys(key for batch in batches for key in batch["cached_selected"]))
        number = 0
        while global_reuse and pool and len(batches) > 1:
            number += 1
            winners = []
            groups = chunks(fair_order(f"{run.scope['result_set']}|round-{number}", pool))
            for group in groups:
                check = reducer.estimate(run.scope, [candidates[key] for key in group], now)
                if not check["cached"]:
                    global_reuse = False
                    break
                winners.extend(check["cached_selected"])
            if len(groups) == 1:
                break
            pool = list(dict.fromkeys(winners))
        required = budget_requirement(tokens, rounds)
        required["batch_tokens"] = sum(batch["tokens"] for batch in misses)
        required["reduction_tokens"] = 0 if global_reuse else required["reduction_tokens"]
        required["reduction_calls"] = 0 if global_reuse else required["reduction_calls"]
        required["tokens"] = required["batch_tokens"] + required["reduction_tokens"]
        required["requests"] = len(misses) + required["reduction_calls"]
        expected_inputs = sum(batch["input_tokens"] for batch in misses) + required["reduction_calls"] * max(
            (batch["input_tokens"] for batch in batches),default=0)
        reserved_outputs = required["requests"] * int(reducer.config.max_tokens)
        reserved_reasoning = required["requests"] * int(getattr(self._provider,"reasoning_headroom",0) or 0)
        from ..intelligence.inference.token_cost import estimated_cost
        cost = estimated_cost(getattr(self._provider,"price_schedule",None),model_id=getattr(self._provider,"model_id",None),
                              input_tokens=expected_inputs,output_tokens=reserved_outputs+reserved_reasoning,now=now)
        sizes = [len(batch["instrument_ids"]) for batch in batches]
        run.plan = {
            "order": self._order_label(run), "batches_planned": len(batches), "reduction_rounds_planned": rounds,
            "rows_planned": sum(sizes), "batch_rows_max": max(sizes, default=0),
            "batch_rows_average": round(sum(sizes) / len(sizes), 2) if sizes else 0,
            "packet_bytes_max": max((batch["packet_bytes"] for batch in batches), default=0),
            "batch_tokens_max": max(tokens, default=0), "largest_batch_tokens": max(tokens, default=0),
            "context_window": window, "reserved_output_tokens": output, "reference_evidence_thinned": thinned,
            "drift_margin": PLAN_DRIFT_MARGIN,
            "optimizer_version":OPTIMIZER_VERSION, "cached_batches":len(batches)-len(misses),
            "batch_optimizer":"MAXIMAL_CONTEXT_PREFIX" if self.adaptive_batches else "BASELINE_BISECTION",
            "new_inference_batches":len(misses), "global_reuse_only":global_reuse,
            "expected_input_tokens":expected_inputs, "total_eligible_candidates":len(eligible),
            "expected_requests":required["requests"], "reserved_output_tokens_total":reserved_outputs,
            "reserved_reasoning_tokens_total":reserved_reasoning, "estimated_total_tokens":required["tokens"],
            "available_request_budget":None, "available_token_budget":None, "feasible_under_current_limits":None,
            "reserved_batch_output_tokens":len(misses)*int(reducer.config.max_tokens),
            "reserved_reasoning_tokens":len(misses)*int(getattr(self._provider,"reasoning_headroom",0) or 0),
            "estimated_provider_cost":cost, "cost_basis":cost["basis"] if cost else "UNAVAILABLE_PRICE_CONFIGURATION",
            "required": required, "budget_basis": "PROVIDER_WORST_CASE" if self._budget is not None else "UNCAPPED_ENGINE",
            "provider_count": measured, "preflight_rejected": rejected,
        }
        report_stage("REUSE_ASSESSMENT", reused_batches=0,
                     new_inference_requests=0, required_tokens=required["tokens"])
        return batches

    def _plan_local(self, run: _Run, eligible: list[str]) -> list[dict[str, Any]]:
        """One row per request for the local engine, counted exactly once: by the send-time gate.

        Planning-time counts were never authoritative for a local request. Evidence is re-acquired for each
        request, so the packet that is sent differs from the one planned: run 97fae8e2 counted about 3,800
        tokens at planning and about 6,000 at send. Counting every row up front, by bisection from 50-row
        groups, cost 400-1,700 s before the first call. A single row is the only grouping that reliably fits
        the 8,192-token window, and the reducer's own cache still answers unchanged packets at send time.
        A local engine carries no token budget, so nothing is reserved from these figures."""
        reducer = self._reducer
        ordered = list(eligible) if run.shortlist is not None else fair_order(str(run.scope["result_set"]), eligible)
        if self._slice:
            turns = self._slice.get("last_turn")
            last = (self._slice.get("last_evaluated") or {}) if turns is None else turns
            # Stable over the fair order: no recent turn first, then the least recent turn.
            ordered.sort(key=lambda key: (key in last, float(last.get(key) or 0)))
        batches = [{"instrument_ids": [key], "packet_bytes": None, "input_tokens": None, "tokens": None,
                    "cached": False, "cached_selected": []} for key in ordered]
        rounds = reduction_rounds(len(batches))
        calls = len(batches) + sum(rounds)
        window = self._context_window()
        run.reduction_budget = {
            "context_window": window, "configured_output": int(reducer.config.max_tokens),
            "max_seconds": REDUCTION_DEADLINE_SECONDS,
            "max_requests_per_finalist": REDUCTION_REQUESTS_PER_FINALIST,
            "max_requests_floor": REDUCTION_REQUESTS_FLOOR,
        }
        run.plan = {
            "order": self._order_label(run), "batches_planned": len(batches), "reduction_rounds_planned": rounds,
            "rows_planned": len(batches), "batch_rows_max": 1 if batches else 0, "batch_rows_average": 1 if batches else 0,
            "packet_bytes_max": None, "batch_tokens_max": None, "largest_batch_tokens": None,
            "context_window": window, "reserved_output_tokens": int(reducer.config.max_tokens),
            "reduction_context": dict(run.reduction_budget),
            "reference_evidence_thinned": 0, "drift_margin": None, "optimizer_version": OPTIMIZER_VERSION,
            "cached_batches": 0, "batch_optimizer": "LOCAL_ONE_ROW_EXACT_AT_SEND",
            "token_basis": "EXACT_AT_SEND_ONLY", "new_inference_batches": len(batches), "global_reuse_only": False,
            "expected_input_tokens": None, "total_eligible_candidates": len(eligible), "expected_requests": calls,
            "reserved_output_tokens_total": None, "reserved_reasoning_tokens_total": 0, "estimated_total_tokens": None,
            "available_request_budget": None, "available_token_budget": None, "feasible_under_current_limits": None,
            "reserved_batch_output_tokens": None, "reserved_reasoning_tokens": 0,
            "estimated_provider_cost": None, "cost_basis": "LOCAL_ENGINE_NO_CHARGE",
            "required": {"tokens": None, "requests": calls, "batch_tokens": None, "reduction_tokens": None,
                         "reduction_calls": sum(rounds)},
            "budget_basis": "UNCAPPED_ENGINE", "provider_count": None, "preflight_rejected": None,
            "slice": None if not self._slice else {
                "deadline": _iso(float(self._slice["deadline_epoch"])) if self._slice.get("deadline_epoch") else None,
                "order": "NO_RECENT_TURN_FIRST_THEN_OLDEST_TURN_THEN_" + (
                    "OPPORTUNITY_SCORE" if run.shortlist is not None else "FAIR_ORDER"),
                "epoch": self._slice.get("epoch"),
                "evaluated_in_epoch": sum(1 for key in eligible if key in (self._slice.get("last_evaluated") or {}))},
        }
        report_stage("REUSE_ASSESSMENT", reused_batches=0, new_inference_requests=len(batches), required_tokens=None)
        return batches

    # ------------------------------------------------------------ model call

    def _call(self, run: _Run, instrument_ids: list[str], *, stage: str, index: int, total: int, planned_tokens: int,
              first_pass: bool, round_number: int | None = None, reuse_only: bool = False,
              should_stop: Callable[[], bool] = lambda: False) -> dict[str, Any]:
        """One bounded request on evidence acquired for it. Never retried."""
        from ..intelligence.inference.anthropic_synthesis import drawing_from_hold
        from .screener_news_evidence import attach_news, fit_news

        if stage == "GLOBAL_REDUCTION":
            run.reduction_requests += 1

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
            fitted: list[dict[str, Any]] = []
            compacted = False
            base_call_id = call_id
            while keep:
                if self._reducer.compact_input:
                    report_stage("COMPACTION", intake_count=len(keep))
                from ..intelligence.inference.candidate_reduction import packet_candidates
                manifest = {"scope":run.scope, "decision_cutoff":now, "candidates":packet_candidates(keep)}
                attempt_id = base_call_id + (f":fit{len(fitted)}" if fitted else "")
                self.ledger().append(run.run_id,"manifest",{"call_id":attempt_id, "semantic_hash":semantic_hash(manifest),
                    "optimizer_version":OPTIMIZER_VERSION, "canonical":manifest})
                self.ledger().append(run.run_id, "batch_started", {
                    "call_id": attempt_id, "stage": stage, "round": round_number, "index": index, "of": total,
                    "instrument_ids": submitted, "evidence_cutoff": now, "planned_tokens": planned_tokens,
                    "request_started_at": _iso(service._clock())})
                position = {"batch": index + 1, "batches_planned": total} if first_pass else {"group": index + 1, "groups": total}
                estimate = check = None
                if stage == "GLOBAL_REDUCTION" and getattr(self._provider, "runtime", None) == "LOCAL_MODEL":
                    # The exact count is free and authoritative. Measure the packet that would be sent; an
                    # over-budget group is split (or, for one/two finalists, thinned) without generation.
                    # A packet whose own estimate is already below the window keeps the cheaper send-time gate.
                    estimate = self._reducer.estimate(run.scope, keep, now)
                    window = self._context_window()
                    floor = self._output_floor(keep)
                    estimated = estimate.get("input_tokens")
                    near_budget = (window is None or not isinstance(estimated, int)
                                   or estimated + floor > window)
                    if not estimate.get("cached") and near_budget:
                        check = self._reducer.preflight(run.scope, keep, now, should_stop=should_stop)
                if check is not None and check.get("context_fit") is False:
                    result = self._context_refusal(run, keep, now, check, estimate)
                    run.reduction_not_sent += 1
                else:
                    with relabelled(stage, round=round_number, **position):
                        if run.hold:
                            with drawing_from_hold(run.run_id, planned_tokens):
                                result = self._reducer.reduce(run.scope, keep, now, allow_inference=not reuse_only, should_stop=should_stop)
                        else:
                            result = self._reducer.reduce(run.scope, keep, now, allow_inference=not reuse_only, should_stop=should_stop)
                call_id = attempt_id
                # A comparison of several finalists is split, never thinned: thinning could remove a finalist's only
                # second strong item and exclude it. One row (any first-pass request, or a group of one) is thinned.
                # A pair is the smallest comparison: halving it compares nothing, so a pair is thinned like one row.
                target = self._context_fit_target(result, fitted) if first_pass or len(keep) <= 2 else None
                if target is None:
                    if (stage == "GLOBAL_REDUCTION" and len(keep) <= 2 and not compacted
                            and self._context_refused(result) and self._compact_comparison(keep)):
                        # News thinning is exhausted and the pair/single still does not fit. Keep every
                        # current-market item (the quote and risk facts) and one non-news reference item;
                        # the first-pass receipts retain the full evidence. A candidate that loses its
                        # second strong item is dropped with the existing reason, never silently kept.
                        compacted = True
                        run.comparison_compacted += 1
                        for candidate in [item for item in keep if not item["sufficient"]]:
                            keep.remove(candidate)
                            dropped[candidate["instrument"]["instrument_id"]] = [
                                UNPROCESSED, ["EVIDENCE_THINNED_BY_PACKET_CAP"]]
                        submitted = [candidate["instrument"]["instrument_id"] for candidate in keep]
                        if not keep:
                            result, failure = None, "LOCAL_CONTEXT_EXCEEDED"
                            break
                        continue
                    break
                # The exact send-time count refused this packet before any generation. The existing deterministic
                # reference-evidence thinning, given the byte budget the count implies, removes stories from the row
                # with the most; current-market evidence is never thinned and every remaining reference keeps its
                # own clocks. A packet thinning cannot change is never resent; a refused attempt keeps one receipt.
                attempted = semantic_hash(packet_candidates(keep))
                fit_news(run.scope, keep, news, now=now, max_bytes=target)
                if semantic_hash(packet_candidates(keep)) == attempted:
                    if (stage == "GLOBAL_REDUCTION" and len(keep) <= 2 and not compacted
                            and self._context_refused(result) and self._compact_comparison(keep)):
                        # News thinning cannot change this pair/single; remove only the comparison metadata
                        # and all but one non-news reference item, then let the exact count decide again.
                        compacted = True
                        run.comparison_compacted += 1
                        for candidate in [item for item in keep if not item["sufficient"]]:
                            keep.remove(candidate)
                            dropped[candidate["instrument"]["instrument_id"]] = [
                                UNPROCESSED, ["EVIDENCE_THINNED_BY_PACKET_CAP"]]
                        submitted = [candidate["instrument"]["instrument_id"] for candidate in keep]
                        if not keep:
                            result, failure = None, "LOCAL_CONTEXT_EXCEEDED"
                            break
                        continue
                    break
                run.counted_not_sent += int(result.get("tokens_input") or 0)
                fitted.append({"call_id": attempt_id, "input_tokens": result.get("tokens_input"),
                               "packet_bytes": result.get("packet_bytes"), "target_bytes": target})
                self.ledger().append(run.run_id, "batch", {
                    "call_id": attempt_id, "stage": stage, "round": round_number, "index": index, "of": total,
                    "outcome": "NOT_SENT", "state": result["state"], "reason": result.get("reason"),
                    "tokens_input": result.get("tokens_input"), "packet_bytes": result.get("packet_bytes"),
                    "superseded_by": "CONTEXT_FIT_THINNING", "target_bytes": target, "evidence_cutoff": now,
                    "instrument_ids": submitted, "dropped": dict(dropped), "selected": [],
                    "context": self._context_receipt(result, keep)})
                for candidate in [item for item in keep if not item["sufficient"]]:
                    keep.remove(candidate)
                    dropped[candidate["instrument"]["instrument_id"]] = [UNPROCESSED, ["EVIDENCE_THINNED_BY_PACKET_CAP"]]
                submitted = [candidate["instrument"]["instrument_id"] for candidate in keep]
                if not keep:
                    # Every row lost its second strong item to thinning: nothing is sent and each row keeps its reason.
                    # The refused attempt's receipt above is the closing record; the run continues like any oversize.
                    result, failure = None, "LOCAL_CONTEXT_EXCEEDED"
                    break
            if keep:
                # A request answered from the reducer's cache was not sent again and is not counted as a model call.
                if result.get("cache") == "HIT":
                    run.cache_hits += 1
                elif result.get("inference_dispatched",True):
                    run.calls += 1
                if result["state"] not in _ANSWERED:
                    failure = str(result.get("reason") or result["state"])
                if self._budget is not None and self._budget.status().get("usage_overrun"):
                    failure = "PROVIDER_USAGE_EXCEEDED_RESERVATION"
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
            if result.get("cache") == "MISS" and result.get("inference_dispatched", True):
                run.tokens_input += int(result.get("tokens_input") or 0)
                run.tokens_output += int(result.get("tokens_output") or 0)
            elif result.get("cache") == "MISS":
                # Counted by the exact send-time gate and refused before generation: never model input.
                run.counted_not_sent += int(result.get("tokens_input") or 0)
            report_stage(stage,reused_batches=run.cache_hits,new_inference_requests=run.calls,
                         actual_tokens=run.tokens_input+run.tokens_output)
            unknown = failure is not None and failure.endswith("TIMEOUT")
            refused = bool(result.get("preflight_refused"))
            self.ledger().append(run.run_id, "batch", {
                "call_id": call_id, "stage": stage, "round": round_number, "index": index, "of": total,
                "outcome": "COMPLETED" if failure is None else "UNKNOWN_PROVIDER_OUTCOME" if unknown
                else "NOT_SENT" if refused else "FAILED",
                "state": result["state"], "reason": result.get("reason"), "validation": result.get("validation"),
                "reduction_run_id": result["run_id"], "input_hash": result["input_hash"], "packet_bytes": result["packet_bytes"],
                "output_schema_hash": result["output_schema_hash"], "cache": result["cache"],
                "reuse":result.get("reuse"), "manifest_hash":semantic_hash(manifest),
                "tokens_input": result.get("tokens_input"), "tokens_output": result.get("tokens_output"),
                "latency_ms": result.get("latency_ms"), "provider_request_id": result.get("provider_request_id"),
                "provider_diagnostics": result.get("provider_diagnostics"),
                "context": self._context_receipt(result, keep),
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
        # The model answered and the unchanged validator refused the answer, or the answer reached its output
        # allowance: a row-level outcome of a first-pass request. Provider and evidence failures are not.
        invalid = (failure is not None and result is not None and bool(result.get("inference_dispatched", True))
                   and (result.get("state") == "INVALID_OUTPUT" or result.get("reason") == "LOCAL_OUTPUT_LIMIT_REACHED"))
        return {"result": result if failure is None else None, "failure": failure, "submitted": submitted, "dropped": dropped,
                "rejected": first_pass and invalid, "invalid": invalid}

    def _context_refused(self, result: dict[str, Any] | None) -> bool:
        """True only for the local engine's exact count refusing before generation."""
        return (getattr(self._provider, "runtime", None) == "LOCAL_MODEL" and result is not None
                and result.get("reason") == "LOCAL_CONTEXT_EXCEEDED"
                and not result.get("inference_dispatched"))

    @staticmethod
    def _compact_comparison(candidates: list[dict[str, Any]]) -> bool:
        """Keep comparison-essential evidence when an exact count refuses even a thinned pair/single.

        Current-market evidence is never removed: it carries the quote, spread and the risk facts the
        downstream decision needs. One admitted non-news reference item stays for the second-strong-evidence
        gate. News stories were already thinned by ``fit_news``; the empty story status and the alignment
        projections are omitted, and the candidate is marked insufficient if its second item disappeared.
        """
        changed = False
        for candidate in candidates:
            reference = list(candidate.get("reference_evidence") or [])
            kept = [item for item in reference if item.get("capability") != "NEWS"][:1]
            if len(kept) != len(reference):
                candidate["reference_evidence"] = kept
                changed = True
            if candidate.get("alignments"):
                candidate["alignments"] = []
                changed = True
            news = candidate.get("news")
            if isinstance(news, dict) and (news.get("story_count") or news.get("providers")):
                candidate["news"] = {
                    **{key: news.get(key) for key in ("state", "model_id", "limitations") if key in news},
                    "story_count": 0, "providers": [],
                    "limitations": list(dict.fromkeys([*(news.get("limitations") or []), "COMPARISON_PACKET_COMPACTED"])),
                }
                changed = True
            current = candidate.get("current_market_evidence") or []
            items = [*current, *candidate.get("reference_evidence", [])]
            quote = any(item.get("capability") == "QUOTE" and (item.get("facts") or {}).get("price") is not None
                        and not item.get("weak_reasons") for item in current)
            second = any(item.get("capability") != "QUOTE" and not item.get("weak_reasons") for item in items)
            if candidate.get("sufficient") and not (quote and second):
                candidate["sufficient"] = False
                changed = True
        return changed

    def _output_floor(self, candidates: list[dict[str, Any]]) -> int:
        from ..intelligence.inference.local_provider import LOCAL_OUTPUT_FLOOR_BASE, LOCAL_OUTPUT_FLOOR_PER_CANDIDATE

        return min(int(self._reducer.config.max_tokens),
                   LOCAL_OUTPUT_FLOOR_BASE + LOCAL_OUTPUT_FLOOR_PER_CANDIDATE * max(1, len(candidates)))

    def _context_refusal(self, run: _Run, candidates: list[dict[str, Any]], now: str,
                         check: dict[str, Any], estimate: dict[str, Any] | None) -> dict[str, Any]:
        """A measured over-budget packet, recorded exactly like a provider refusal but never sent.

        The exact count is the local runtime's own; the canonical bytes and input hash come from the same
        ``estimate`` the reducer would have used. ``_context_fit_target`` can therefore thin a one/two-row
        packet with the same evidence rules as a send-time refusal, while a larger group is split by the caller.
        """
        window = check.get("context_window") or self._context_window()
        configured = int(self._reducer.config.max_tokens)
        floor = self._output_floor(candidates)
        tokens = check.get("input_tokens")
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION, "run_id": "CTX-" + uuid.uuid4().hex[:32],
            "decision_cutoff": now, "generated_at": now, "valid_until": now, "scope": run.scope,
            "provider_id": getattr(self._provider, "provider_id", None), "model_id": getattr(self._provider, "model_id", None),
            "runtime": getattr(self._provider, "runtime", None), "candidates": [], "evidence": candidates,
            "state": "UNAVAILABLE", "reason": "LOCAL_CONTEXT_EXCEEDED", "cache": "MISS", "preflight_refused": True,
            "inference_dispatched": False, "tokens_input": tokens, "tokens_output": 0,
            "input_hash": (estimate or {}).get("input_hash"), "packet_bytes": (estimate or {}).get("packet_bytes"),
            "output_schema_hash": input_hash_from_dict(output_schema(candidates)),
            "provider_diagnostics": {"preflight": dict(check), "context": {
                "configured_max_tokens": configured, "context_window": window, "input_tokens": tokens,
                "output_allowance": (window - tokens) if isinstance(window, int) and isinstance(tokens, int) else None,
                "output_floor": floor, "input_budget": (window - floor) if isinstance(window, int) else None,
                "context_fit": False, "source": "PREFLIGHT_EXACT_COUNT"}},
            "coverage": {"candidate_intake": len(candidates), "selected": 0},
            "limitations": ["The comparison packet exceeds the local model context; it was not sent."],
        }

    @staticmethod
    def _context_receipt(result: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        """The measured budget of one request, from the provider's own diagnostics."""
        context = ((result.get("provider_diagnostics") or {}).get("context") or {})
        if not context:
            return None
        window, floor = context.get("context_window"), context.get("output_floor")
        return {
            "source": context.get("source", "PROVIDER"),
            "context_window": window, "input_tokens": context.get("input_tokens"),
            "output_allowance": context.get("output_allowance"), "output_floor": floor,
            "input_budget": context.get("input_budget", (window - floor) if isinstance(window, int) and isinstance(floor, int) else None),
            "candidates": len(candidates),
        }

    def _context_fit_target(self, result: dict[str, Any] | None, fitted: list[dict[str, Any]]) -> int | None:
        """The canonical packet byte budget for a thinned resend, or None when this answer stands.

        Only for the local engine's exact send-time refusal (nothing generated), at most CONTEXT_FIT_ATTEMPTS times,
        and only while each attempt actually shrinks the packet."""
        if (getattr(self._provider, "runtime", None) != "LOCAL_MODEL" or result is None
                or result.get("reason") != "LOCAL_CONTEXT_EXCEEDED" or result.get("inference_dispatched")
                or len(fitted) >= CONTEXT_FIT_ATTEMPTS):
            return None
        counted, size, window = result.get("tokens_input"), result.get("packet_bytes"), self._context_window()
        if not isinstance(counted, int) or not isinstance(size, int) or counted <= 0 or size <= 0 or window is None:
            return None
        if fitted and size >= int(fitted[-1]["packet_bytes"] or 0):
            return None  # the last thinning removed nothing: no further budget can change the answer
        from ..intelligence.inference.local_provider import LOCAL_OUTPUT_FLOOR_BASE, LOCAL_OUTPUT_FLOOR_PER_CANDIDATE

        rows = len((result.get("evidence") or [None]))
        floor = min(int(self._reducer.config.max_tokens), LOCAL_OUTPUT_FLOOR_BASE + LOCAL_OUTPUT_FLOOR_PER_CANDIDATE * rows)
        excess = counted - (window - floor)
        if excess <= 0:
            return None
        # Remove the excess at a conservative CONTEXT_FIT_BYTES_PER_TOKEN; the next exact count decides again.
        return max(0, size - int(excess * CONTEXT_FIT_BYTES_PER_TOKEN))

    @staticmethod
    def _defer_finalists(run: _Run, dropped: dict[str, list[Any]]) -> None:
        """Slices: move finalists the comparison could not include from the exclusions to deferred rows."""
        run.excluded_finalists = [item for item in run.excluded_finalists if item["instrument_id"] not in dropped]
        for key, value in dropped.items():
            reasons = list(value[1]) if value[0] == UNPROCESSED else [f"{value[0]}_AT_COMPARISON_CUTOFF", *value[1]]
            run.classes[key] = (UNPROCESSED, ["DEFERRED_FROM_COMPARISON", *reasons])
        run.deferred_finalists += len(dropped)
        run.sliced = True

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
        coverage_complete = reconciled and not run.excluded_finalists and counts["unprocessed"] == 0 and run.batches_completed == planned \
            and status not in (FAILED, STOPPED, ENUMERATION_FAILED, BUDGET_INSUFFICIENT, PROVISIONAL_PARTIAL_COVERAGE, INTERRUPTED,
                               EVIDENCE_PROVIDER_UNAVAILABLE)
        eligible_now = counts["evaluated"] + counts["unprocessed"]
        # A rolling slice is complete when every row is classified and accounted for and the rows the slice reached
        # were answered and compared; rows it did not reach stay UNPROCESSED with their own reasons.
        slice_complete = reconciled and status in SLICE_STATUSES and not run.excluded_finalists
        deferred = sum(1 for name, codes in run.classes.values() if name == UNPROCESSED and "DEFERRED_TO_NEXT_SLICE" in codes)
        return {
            "method_version": self.identity["method_version"], "method_name": self.identity["method_name"],
            "coverage_run_id": run.run_id, "software_sha": self.identity["software_sha"], "status": status, "reason": reason,
            "shortlist": None if run.shortlist is None else {key: value for key, value in run.shortlist.items() if key != "ranked"},
            "universe_count": run.universe_count, "enumeration": run.enumeration, "assessed_count": len(run.classes),
            "eligible_count": run.eligible_count, "counts": counts, "reconciled": reconciled,
            "ai_evaluated_count": counts["evaluated"],
            "ai_coverage_pct": round(100 * counts["evaluated"] / eligible_now, 2) if eligible_now else None,
            "batches_planned": planned, "batches_completed": run.batches_completed, "model_calls": run.calls,
            "answers_from_cache": run.cache_hits,
            "optimizer_version":OPTIMIZER_VERSION,
            "efficiency":{"reused_batches":run.cache_hits, "new_inference_requests":run.calls,
                          "actual_input_tokens":run.tokens_input, "actual_output_tokens":run.tokens_output,
                          "counted_not_sent_tokens":run.counted_not_sent,
                          "required_tokens":(run.plan or {}).get("required",{}).get("tokens"),
                          "estimated_provider_cost":(run.plan or {}).get("estimated_provider_cost"),
                          "cost_basis":(run.plan or {}).get("cost_basis","UNAVAILABLE_PRICE_CONFIGURATION")},
            "plan": run.plan, "reduction": {"rounds_planned": len((run.plan or {}).get("reduction_rounds_planned", [])),
                                           "rounds_completed": run.rounds_completed,
                                           # Finalists whose evidence was no longer admissible when a comparison was due.
                                           "finalists_excluded": run.excluded_finalists[:MAX_EXCLUDED_LISTED],
                                           "finalists_excluded_count": len(run.excluded_finalists),
                                           "presplit_groups": run.presplit, "smallest_refused_group": run.refused_group,
                                           "requests": run.reduction_requests, "not_sent": run.reduction_not_sent,
                                           "compacted_comparisons": run.comparison_compacted,
                                           "budget": dict(run.reduction_budget), "rounds": run.reduction_rounds[-10:]},
            "finalist_count": len({item["instrument_id"] for item in run.finalists}),
            "budget": {**run.budget, "tokens_input": run.tokens_input, "tokens_output": run.tokens_output},
            "coverage_complete": coverage_complete, "selection_complete": coverage_complete and status in SELECTION_COMPLETE,
            "cutoffs": run.cutoffs, "timings_ms": {key: round(value, 1) for key, value in run.timings.items()},
            "ai_rejected_count": counts["by_class"].get(AI_REJECTED, 0), "slice_complete": slice_complete,
            "slice": None if not self._slice else {
                "epoch": self._slice.get("epoch"),
                "deadline": _iso(float(self._slice["deadline_epoch"])) if self._slice.get("deadline_epoch") is not None else None,
                "deferred_count": deferred, "rejected_requests": run.rejected,
                "deferred_finalists": run.deferred_finalists, "comparison_rejected": run.comparison_rejected,
                "evaluated_count": counts["by_class"].get(AI_EVALUATED, 0)},
        }

    def _terminal(self, run: _Run, status: str, reason: str | None = None, *, final: dict[str, Any] | None = None) -> dict[str, Any]:
        service = self.service
        self._release(run)
        block = self._block(run, status, reason)
        now = _iso(service._clock())
        common = {"scope": run.scope or None, "matched_count": run.universe_count or 0, "intake_count": run.submitted,
                  "max_intake": MAX_INTAKE, "result_set": (run.scope or {}).get("result_set")}
        repository = record = None
        stored = final is not None and ((status == GLOBAL_SELECTION_COMPLETE and block["selection_complete"])
                                        or (status == SLICE_SELECTION_COMPLETE and block["slice_complete"]))
        if stored:
            block["selected_count"] = len(final["candidates"])
            block["reduction_run_id"] = final["run_id"]
            # Stored under this run's own id: the reducer's request id stays on the receipt as reduction_run_id.
            record = {**final, "run_id": "CU-" + run.run_id[:40], "universe_coverage": block}
            repository = self._repository
            if repository is None:
                from ..local_state.action_decisions import action_repository

                repository = action_repository()
            result = {**record, "schema_version": RESULT_SCHEMA_VERSION, **common}
        if not stored:
            if status in (GLOBAL_SELECTION_COMPLETE, SLICE_SELECTION_COMPLETE):
                # Never label a run complete that the accounting says is not.
                status, block["status"], block["reason"] = PROVISIONAL_PARTIAL_COVERAGE, PROVISIONAL_PARTIAL_COVERAGE, "ACCOUNTING_INCOMPLETE"
            block["selected_count"] = 0
            settled = block["selection_complete"] or block["slice_complete"]
            provisional = [] if settled else [dict(item) for item in run.finalists]
            result = {
                "schema_version": RESULT_SCHEMA_VERSION, "run_id": run.run_id, "candidates": [], "evidence": [],
                "state": "NO_GROUNDED_CANDIDATES" if settled else "INCOMPLETE", "reason": status,
                "provisional": provisional, "universe_coverage": block, "decision_cutoff": run.cutoffs["last_batch"] or run.cutoffs["classification"] or now,
                "generated_at": now, "valid_until": now, "input_hash": input_hash_from_dict({"run_id": run.run_id, "status": status}),
                "packet_bytes": 0, "cache": "MISS", "simulated": False, "limitations": [_LIMITATIONS.get(status, status)],
                "coverage": {"candidate_intake": run.submitted, "selected": 0, "evidence_items": 0, "blocked_items": 0, "missing_items": 0},
                **{key: self.identity[key] for key in ("provider_id", "model_id", "runtime", "prompt_id", "prompt_version", "prompt_hash", "wire_schema_version")},
                **common}
        if run.classes:
            self._record_rows(run, "FINAL")
        terminal = {
            "account_id": run.account_id, "status": status, "reason": block["reason"], "finished_at": now,
            "candidate_run_id": result["run_id"] if stored else None,
            "selected": [{"instrument_id": pick["instrument_id"], "rank": pick["rank"]} for pick in result["candidates"]],
            # Identities only, bounded: rationales stay in the per-request receipts and the returned result.
            "provisional": [{key: item[key] for key in ("instrument_id", "batch", "rank_in_batch")}
                            for item in result.get("provisional", [])[:MAX_TERMINAL_FINALISTS]],
            "provisional_count": len(result.get("provisional", [])),
            "universe_coverage": {key: value for key, value in block.items() if key != "plan"}, "scope": run.scope or None}
        try:
            self.ledger().finalize(run.run_id, terminal, repository=repository, candidate=record)
        except ValueError as exc:
            if record is None:
                raise
            return self._terminal(run, FAILED, str(exc))
        if record is not None:
            report_stage("STORED")
        run.terminal = result
        return result


def interrupt_open_runs(ledger: Any, *, tracked: Any, release: Callable[[str], Any], clock: Callable[[], float] = time.time,
                        reason_for: Callable[[dict[str, Any]], str] | None = None) -> list[str]:
    """Close runs a previous process left open. Nothing is resumed: quote evidence older than a minute cannot
    be reused, so a new Run is a new run. A call left without an outcome stays charged; only the part of the
    run's hold that was never reserved is released. ``reason_for`` distinguishes a genuine restart from a
    run of this same process whose terminal receipt was lost; the default keeps the historical restart code."""
    closed = []
    for run_id in ledger.open_runs():
        # Asked per run, at the moment of closing it: a run that started while this loop ran is never closed.
        if run_id in tracked:
            continue
        head = ledger.records(run_id, "run")[0]
        reason = reason_for(head) if reason_for is not None else "SERVER_RESTARTED_DURING_RUN"
        unfinished = ledger.unfinished_batches(run_id)
        completed = ledger.records(run_id, "batch")
        try:
            released = release(run_id)
        except Exception:  # noqa: BLE001 - recovery never fails startup; an unreleased hold expires with the UTC day
            released = None
        ledger.append(run_id, "terminal", {
            "account_id": head.get("account_id"), "status": INTERRUPTED, "reason": reason,
            "finished_at": _iso(clock()), "candidate_run_id": None, "selected": [], "provisional": [],
            "unknown_provider_outcomes": [{"call_id": item["call_id"], "instrument_ids": item["instrument_ids"],
                                           "planned_tokens": item["planned_tokens"]} for item in unfinished],
            "calls_completed": len(completed), "hold_released": released,
            "universe_coverage": {"method_version": head.get("method_version") or METHOD_VERSION,
                                  "method_name": head.get("method_name") or METHOD_NAME, "coverage_run_id": run_id,
                                  "status": INTERRUPTED, "reason": reason,
                                  "coverage_complete": False, "selection_complete": False},
            "scope": None})
        closed.append(run_id)
    return closed


__all__ = ["BUDGET_INSUFFICIENT", "COMPLETE_NO_SELECTION", "EMPTY_UNIVERSE", "ENUMERATION_FAILED", "EVIDENCE_PROVIDER_UNAVAILABLE", "FAILED",
           "GLOBAL_SELECTION_COMPLETE", "INTERRUPTED", "NO_ELIGIBLE_ROWS", "PROVISIONAL_PARTIAL_COVERAGE",
           "SELECTION_COMPLETE", "STOPPED", "ScreenerAiCoverage", "interrupt_open_runs"]
