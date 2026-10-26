"""AI Screener runs the operator can watch.

Starting a run returns at once; the run continues on a server thread and reports the stage it is
really in, with elapsed time and the counts it has actually produced: rows enumerated, rows assessed,
rows eligible, batches finished. No percentage is derived from assumed model latency. One run per
account: a second start joins the run in progress.

A run is ``ScreenerAiService.run_universe`` for the scope: the full-universe method. Its receipts are
written to the coverage ledger as it goes, so a restart finds the run it killed and closes it as
INTERRUPTED; nothing is resumed. Stop reaches owned local generation and its resource monitor reaps the
owned process. Hosted calls have no confirmed cancellation and their tokens stay charged.

A service without ``run_universe`` (an acceptance harness carrying a prebuilt result) runs its ``run``.
"""
from __future__ import annotations

import json
import re
import statistics
import threading
import time
import uuid
from collections import OrderedDict, deque
from datetime import UTC, date, datetime, time as day_time, timedelta
from typing import Any, Callable

from ..intelligence.inference.run_progress import observing

RUN_SCHEMA = "screener-ai-screener-run/2.0.0"
RUNS_SCHEMA = "screener-ai-screener-runs/2.0.0"
HISTORY_SCHEMA = "screener-ai-screener-history/1.0.0"
MAX_HISTORY = 50
_REASON_SYMBOLS = 3
_MAX_REASONS = 8
# The order the work happens in. A stage that did not happen (no budget, nothing eligible) is absent from a run.
# BATCH_INFERENCE and GLOBAL_REDUCTION each cover many bounded calls; their detail names the call in progress.
STAGES = ("ENUMERATION", "ELIGIBILITY", "PLANNING", "TOKEN_PLANNING", "REUSE_ASSESSMENT", "BUDGET_HELD",
          "COMPACTION", "BATCH_INFERENCE", "GLOBAL_REDUCTION", "STORED")
STAGED_STAGES = STAGES[:2] + ("LOCAL_ASSESSMENT",) + STAGES[2:]


def _stage_order(scope):
    return STAGED_STAGES if scope.get("method") == "STAGED_LOCAL_FIRST_EXPERIMENTAL" else STAGES
MAX_TRACKED_RUNS = 20
_LATENCY_SAMPLES = 20
# Counts a run has actually produced so far; the latest value of each is the run's progress.
_PROGRESS_KEYS = ("universe_count", "assessed_count", "eligible_count", "batches_planned", "batches_completed",
                  "rows_evaluated", "required_tokens", "held_tokens", "held_requests", "finalists", "round",
                  "reused_batches", "new_inference_requests", "actual_tokens", "local_assessed", "premium_evaluated")
_DETAIL_KEYS = (*_PROGRESS_KEYS, "batch", "step", "packet_bytes", "reserved_tokens", "shared", "intake_count", "sufficient_count")
_STABLE_CODE = re.compile(r"[A-Z][A-Z0-9_]*")
# Runs alive in this process, across every tracker: restart recovery must never close one of these.
_LIVE: set[str] = set()
_RECOVERY = threading.Lock()


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


def evidence_reasons(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Why a run had little to select from, read from its evidence packet and never from model prose.

    Each reason counts the candidates it applies to and names a few of them: blocked evidence by capability and
    reason code, candidates the model saw with no news story, and candidates without sufficient evidence. For a
    full-universe run the packet is the final selection's: the finalists, not every row the batches assessed."""
    candidates = result.get("evidence") or []
    total = len(candidates)
    found: dict[tuple[str, str | None, str | None], list[str]] = {}

    def note(kind: str, capability: str | None, reason: str | None, candidate: dict[str, Any]) -> None:
        instrument = candidate.get("instrument") or {}
        symbol = str(instrument.get("symbol") or instrument.get("instrument_id") or "")
        symbols = found.setdefault((kind, capability, reason), [])
        if symbol not in symbols:
            symbols.append(symbol)

    for candidate in candidates:
        for item in candidate.get("blocked") or []:
            for code in item.get("reason_codes") or [None]:
                note("BLOCKED", str(item.get("capability")), code, candidate)
        items = [*(candidate.get("current_market_evidence") or []), *(candidate.get("reference_evidence") or [])]
        if not any(item.get("capability") == "NEWS" for item in items):
            note("NO_NEWS", "NEWS", None, candidate)
        if not candidate.get("sufficient"):
            note("INSUFFICIENT", None, None, candidate)
    order = {"BLOCKED": 0, "NO_NEWS": 1, "INSUFFICIENT": 2}
    ranked = sorted(found.items(), key=lambda entry: (-len(entry[1]), order[entry[0][0]], str(entry[0][1]), str(entry[0][2])))
    return [{"kind": kind, "capability": capability, "reason": reason, "count": len(symbols), "of": total, "symbols": symbols[:_REASON_SYMBOLS]}
            for (kind, capability, reason), symbols in ranked[:_MAX_REASONS]]


def _coverage(result: dict[str, Any]) -> dict[str, Any] | None:
    """The run's accounting without its plan detail. None for a result that carries none."""
    block = result.get("universe_coverage")
    if not isinstance(block, dict):
        return None
    keys = ("method_version", "status", "reason", "universe_count", "assessed_count", "eligible_count", "ai_evaluated_count",
            "ai_coverage_pct", "batches_planned", "batches_completed", "model_calls", "finalist_count", "selected_count",
            "coverage_complete", "selection_complete", "reconciled", "counts", "budget", "reduction", "efficiency",
            "slice_complete", "slice", "ai_rejected_count")
    return {key: block.get(key) for key in keys}


def run_summary(result: dict[str, Any]) -> dict[str, Any]:
    """What the Screener needs from a finished run without the evidence packet: the outcome, which rows the model
    was shown in the selection it made and which it selected, and the evidence-derived reasons."""
    coverage = _coverage(result)
    # Only a completed global selection (or a single-request result) names a stored candidate run.
    stored = result.get("method") != "STAGED_LOCAL_FIRST_EXPERIMENTAL" and (
        coverage is None or coverage["status"] in ("GLOBAL_SELECTION_COMPLETE", "SLICE_SELECTION_COMPLETE"))
    return {
        "method": result.get("method", "EXHAUSTIVE_EXISTING"), "staged": result.get("staged"),
        "coverage": coverage, "provisional_count": len(result.get("provisional") or []),
        "candidate_run_id": result.get("run_id") if stored else None,
        "state": result.get("state"), "reason": result.get("reason"),
        "selected": [{"instrument_id": pick["instrument_id"], "rank": pick["rank"]} for pick in result.get("candidates", [])],
        "intake": [str((candidate.get("instrument") or {}).get("instrument_id")) for candidate in result.get("evidence") or []],
        "reasons": evidence_reasons(result),
        "intake_count": result.get("intake_count"), "cache": result.get("cache"), "simulated": result.get("simulated"),
        "provider_id": result.get("provider_id"), "model_id": result.get("model_id"), "runtime": result.get("runtime"),
        "tokens_input": result.get("tokens_input"), "tokens_output": result.get("tokens_output"),
        "latency_ms": result.get("latency_ms"), "packet_bytes": result.get("packet_bytes"),
        "decision_cutoff": result.get("decision_cutoff"), "valid_until": result.get("valid_until"),
        "limitations": list(result.get("limitations") or []),
    }


class AiScreenerRuns:
    def __init__(self, service: Any | None = None, *, clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self._fixed_service = service
        self._clock = clock
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._runs: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._active: dict[str, dict[str, Any]] = {}
        self._start_locks: dict[str, threading.Lock] = {}
        self._latencies: dict[str, deque[int]] = {}
        self._reservations: dict[str, int] = {}
        self._recovered: list[dict[str, Any]] = []

    def _start_lock(self, account_id: str) -> threading.Lock:
        """One start/recover section per account, so two scopes cannot both find the slot free."""
        with self._lock:
            lock = self._start_locks.get(account_id)
            if lock is None:
                lock = self._start_locks[account_id] = threading.Lock()
            return lock

    def _tracked(self) -> set[str]:
        """Run ids alive in this process, including an active run whose ``_LIVE`` mark was lost."""
        with self._lock:
            return set(_LIVE) | {run["run_id"] for run in self._active.values()}

    @staticmethod
    def _same_question(active: dict[str, Any], scope: dict[str, Any]) -> bool:
        return _question(active.get("scope") or {}) == _question(scope)

    @staticmethod
    def _recovery_reason(head: dict[str, Any]) -> str:
        from .screener_ai_coverage import BOOT_ID

        return "RUN_TERMINAL_NOT_RECORDED" if head.get("boot_id") == BOOT_ID else "SERVER_RESTARTED_DURING_RUN"

    def recover_at_boot(self) -> list[dict[str, Any]]:
        """Once, when the serving process starts: close the runs a dead process left open, so none of them holds
        the shared AI slot until somebody presses Run or Stop. Returns the runs closed."""
        before = len(self._recovered)
        self._recover(self._service())
        return list(self._recovered[before:])

    def _recover(self, service: Any) -> None:
        """Close full-universe runs a previous process left open and release their unused holds. Called from an
        operator write (Run, Stop) and once at boot (``recover_at_boot``), never from a status read."""
        if not callable(getattr(service, "run_universe", None)):
            return
        try:
            from ..local_state.ai_screener_coverage import coverage_ledger
            from .screener_ai_coverage import interrupt_open_runs

            ledger = coverage_ledger()
            with _RECOVERY:
                # ``_LIVE`` itself, not a copy: a run is registered there before it writes its first receipt.
                from ..local_state.staged_screener import staged_stores
                staged, _ = staged_stores()
                tracked = self._tracked()
                staged_live = tracked | {value + "-premium" for value in tracked}
                for staged_id in interrupt_open_runs(staged, tracked=staged_live, release=service.release_hold, clock=self._clock):
                    terminal=staged.terminal(staged_id) or {}
                    self._recovered.append({'run_id':staged_id,'account_id':terminal.get('account_id'), 'method':'STAGED_LOCAL_FIRST_EXPERIMENTAL', 'status':terminal.get('status'), 'reason':terminal.get('reason'), 'finished_at':terminal.get('finished_at'), 'calls_completed':terminal.get('calls_completed'), 'unknown_provider_outcomes':len(terminal.get('unknown_provider_outcomes') or [])})
                for run_id in interrupt_open_runs(ledger, tracked=tracked, release=service.release_hold, clock=self._clock,
                                                  reason_for=self._recovery_reason):
                    terminal = ledger.terminal(run_id) or {}
                    self._recovered.append({"run_id": run_id, "account_id": terminal.get("account_id"), "status": terminal.get("status"),
                                            "reason": terminal.get("reason"), "finished_at": terminal.get("finished_at"),
                                            "calls_completed": terminal.get("calls_completed"),
                                            "unknown_provider_outcomes": len(terminal.get("unknown_provider_outcomes") or [])})
        except Exception:  # noqa: BLE001 - recovery is bookkeeping; it never blocks a new run, and is tried again on the next
            pass

    def _interrupted(self, service: Any, account_id: str) -> list[dict[str, Any]]:
        """Runs of this account a restart ended: those already closed, and those found open and not alive in this
        process, which the next Run or Stop will close. Reads the ledger only; writes nothing."""
        found = [item for item in self._recovered if item["account_id"] == account_id]
        if not callable(getattr(service, "run_universe", None)):
            return found
        try:
            from ..local_state.ai_screener_coverage import coverage_ledger

            ledger = coverage_ledger()
            from ..local_state.staged_screener import staged_stores
            staged,_=staged_stores()
            tracked = self._tracked()
            for staged_id in staged.open_runs():
                head=staged.records(staged_id,"run")
                if staged_id in tracked or staged_id.removesuffix("-premium") in tracked or not head or head[0].get("account_id")!=account_id: continue
                found.append({"run_id":staged_id,"account_id":account_id,"method":"STAGED_LOCAL_FIRST_EXPERIMENTAL","status":"INTERRUPTED","reason":"SERVER_RESTARTED_DURING_RUN","finished_at":None,"calls_completed":len(staged.records(staged_id,"batch")),"unknown_provider_outcomes":len(staged.unfinished_batches(staged_id))})
            for run_id in ledger.open_runs():
                head = ledger.records(run_id, "run")
                if run_id in tracked or not head or head[0].get("account_id") != account_id:
                    continue
                found.append({"run_id": run_id, "account_id": account_id, "status": "INTERRUPTED",
                              "reason": self._recovery_reason(head[0]),
                              "finished_at": None, "calls_completed": len(ledger.records(run_id, "batch")),
                              "unknown_provider_outcomes": len(ledger.unfinished_batches(run_id))})
        except Exception:  # noqa: BLE001 - a status read never fails on bookkeeping
            pass
        return found

    def _service(self) -> Any:
        if self._fixed_service is not None:
            return self._fixed_service
        from .screener_ai import screener_ai_service

        return screener_ai_service()

    def start(self, account_id: str, body: dict[str, Any], *, spend_limit: dict[str, int] | None = None,
              origin: str = "OPERATOR", slice_plan: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a run for this account, or join the one already in progress. ValueError for an invalid scope.

        ``spend_limit`` (AUTO-01) caps what a run started without an operator may hold; a joined run keeps the
        terms it was started under. ``slice_plan`` makes an automation run a rolling slice (local engine only)."""
        service = self._service()
        scope = service.validate_scope(body)
        # The whole find/recover/create section is serialized per account. Recovery is inside it so it cannot
        # close a run this section is about to create, and a second scope cannot pass the free-slot check
        # between the first scope's check and its insertion.
        with self._start_lock(account_id):
            self._recover(service)
            engine = service.engine()
            with self._lock:
                active = self._active.get(account_id)
                if active is not None:
                    same = self._same_question(active, scope)
                    return self._snapshot(active, joined=True, joined_scope=same)
                run = {"run_id": uuid.uuid4().hex, "account_id": account_id, "scope": scope, "state": "RUNNING",
                       "started_at": self._clock(), "started": self._monotonic(), "finished_at": None, "finished": None,
                       "engine": {key: engine[key] for key in ("provider_id", "model_id", "runtime")},
                       "timeout_seconds": engine["timeout_seconds"], "stages": [], "intake_count": None,
                       "sufficient_count": None, "packet_bytes": None, "result": None, "error": None,
                       "progress": {}, "stop": threading.Event(), "stop_requested_at": None,
                       "spend_limit": dict(spend_limit) if spend_limit is not None else None, "origin": origin,
                       "slice_plan": dict(slice_plan) if slice_plan else None}
                self._active[account_id] = run
                self._runs[run["run_id"]] = run
                _LIVE.add(run["run_id"])
                for run_id in [key for key, value in self._runs.items() if value["state"] != "RUNNING"][:max(0, len(self._runs) - MAX_TRACKED_RUNS)]:
                    del self._runs[run_id]
                snapshot = self._snapshot(run, joined_scope=True)
            threading.Thread(target=self._work, args=(service, run, scope), name="imp-ai-screener-run", daemon=True).start()
            return snapshot

    def row_records(self, run_id: str) -> dict[str, tuple[str, list[str]]]:
        """Each row's final class and reasons in a finished run, from its immutable ledger rows."""
        from ..local_state.ai_screener_coverage import coverage_ledger

        records: dict[str, tuple[str, list[str]]] = {}
        for record in coverage_ledger().records(run_id, "rows"):
            if record.get("phase") == "FINAL":
                records.update((row[0], (row[1], list(row[2] if len(row) > 2 else []))) for row in record.get("rows") or [])
        return records

    def row_outcomes(self, run_id: str) -> dict[str, str]:
        """Each row's final class in a finished run, from its immutable ledger rows. Empty when there are none."""
        from ..local_state.ai_screener_coverage import coverage_ledger

        outcomes: dict[str, str] = {}
        for record in coverage_ledger().records(run_id, "rows"):
            if record.get("phase") == "FINAL":
                outcomes.update((row[0], row[1]) for row in record.get("rows") or [])
        return outcomes

    def read(self, account_id: str, run_id: str) -> dict[str, Any] | None:
        """One of this account's tracked runs, with its full result once finished."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is not None:
                return self._snapshot(run) if run["account_id"] == account_id else None
        staged = self._restored_staged(account_id, run_id)
        return staged or self._restored(account_id, run_id=run_id)

    def _restored_staged(self, account_id, run_id=None, *, result=True):
        from ..local_state.staged_screener import staged_stores
        ledger, repo = staged_stores()
        terminal = ledger.terminal(run_id) if run_id else ledger.latest_terminal(account_id)
        if terminal and not run_id: run_id=terminal["run_id"]
        if not terminal or terminal.get("account_id") != account_id or not terminal.get("experimental_result_id"):
            return None
        record = repo.get(terminal["experimental_result_id"])
        if record is None:
            return None
        head = ledger.records(run_id, "run")[0]
        return {"schema_version": RUN_SCHEMA, "run_id": run_id, "account_id": account_id,
                "state": "COMPLETED", "joined": False, "scope": head["query"], "stage": None,
                "stage_order": list(STAGED_STAGES), "stages": [], "started_at": head["started_at"],
                "finished_at": terminal["finished_at"], "elapsed_ms": round((datetime.fromisoformat(terminal["finished_at"].replace("Z","+00:00"))-datetime.fromisoformat(head["started_at"].replace("Z","+00:00"))).total_seconds()*1000),
                "engine": {key: record.get(key) for key in ("provider_id", "model_id", "runtime")},
                "timeout_seconds": 120, "typical_latency_ms": None, "typical_latency_samples": 0,
                "intake_count": record["intake_count"], "sufficient_count": record["staged"]["counters"]["deterministically_eligible"],
                "packet_bytes": record["packet_bytes"], "progress": {}, "stop_requested": False,
                "stop_requested_at": None, "summary": run_summary(record), "result": record if result else None, "error": None}

    def _restored(self, account_id: str, *, run_id: str | None = None, result: bool = True) -> dict[str, Any] | None:
        """Read a completed selection after restart from its immutable parent and candidate receipts.

        No inference, budget changes or recovery writes occur. Incomplete runs remain available
        through coverage receipts; they cannot be reconstructed as stored candidate selections.
        """
        if not callable(getattr(self._service(), "run_universe", None)):
            return None
        from ..local_state.ai_screener_coverage import coverage_ledger
        from ..local_state.action_decisions import action_repository
        from .screener_ai import SCHEMA_VERSION

        ledger = coverage_ledger()
        terminal = ledger.terminal(run_id) if run_id is not None else ledger.latest_terminal(account_id)
        if not terminal or terminal.get("account_id") != account_id or terminal.get("status") != "GLOBAL_SELECTION_COMPLETE":
            return None
        run_id = run_id or terminal["run_id"]
        head = ledger.records(run_id, "run")[0]
        record = action_repository().get("candidate_run", terminal["candidate_run_id"])
        if record is None:
            return None
        block = record["universe_coverage"]
        restored = {**record, "schema_version": SCHEMA_VERSION, "scope": terminal["scope"],
                    "matched_count": block["universe_count"], "intake_count": block["ai_evaluated_count"],
                    "max_intake": head["limits"]["max_batch_rows"], "result_set": terminal["scope"]["result_set"]}
        elapsed = (datetime.fromisoformat(terminal["finished_at"].replace("Z", "+00:00"))
                   - datetime.fromisoformat(head["started_at"].replace("Z", "+00:00"))).total_seconds()
        return {"schema_version": RUN_SCHEMA, "run_id": run_id, "account_id": account_id, "state": "COMPLETED", "joined": False,
                "scope": head["query"], "stage": None, "stage_order": list(STAGES), "stages": [],
                "started_at": head["started_at"], "finished_at": terminal["finished_at"], "elapsed_ms": round(elapsed * 1000),
                "engine": {key: head.get(key) for key in ("provider_id", "model_id", "runtime")},
                "timeout_seconds": self._service().engine()["timeout_seconds"], "typical_latency_ms": None, "typical_latency_samples": 0,
                "intake_count": block["ai_evaluated_count"], "sufficient_count": block["eligible_count"], "packet_bytes": record["packet_bytes"],
                "progress": {}, "stop_requested": False, "stop_requested_at": None, "summary": run_summary(restored),
                "result": restored if result else None, "error": None}

    def stop(self, account_id: str, run_id: str) -> dict[str, Any] | None:
        """Stop further calls and signal owned local generation. Hosted calls remain charged;
        completed receipts are kept. Stopping a finished run changes nothing."""
        self._recover(self._service())
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run["account_id"] != account_id:
                return None
            if run["state"] == "RUNNING" and not run["stop"].is_set():
                run["stop"].set()
                run["stop_requested_at"] = self._clock()
            return self._snapshot(run, result=False)

    def coverage(self, account_id: str, run_id: str, *, row_class: str | None = None, offset: int = 0,
                 limit: int = 200) -> dict[str, Any] | None:
        """One run's receipts: its plan, every model call, and a page of per-row accounting. Reads the ledger only.
        ``row_class`` is one class, or ``NOT_EVALUATED`` for every row the model did not evaluate."""
        from ..local_state.ai_screener_coverage import coverage_ledger

        ledger = coverage_ledger()
        head = ledger.records(run_id, "run")
        if not head:
            from ..local_state.staged_screener import staged_stores
            ledger, _ = staged_stores()
            head = ledger.records(run_id, "run")
        if not head or head[0].get("account_id") != account_id:
            return None
        parts = ledger.records(run_id, "rows")
        phase = "FINAL" if any(part["phase"] == "FINAL" for part in parts) else "CLASSIFIED"
        wanted = (lambda name: name != "AI_EVALUATED") if row_class == "NOT_EVALUATED" else (lambda name: row_class is None or name == row_class)
        rows = [row for part in parts if part["phase"] == phase for row in part["rows"] if wanted(row[1])]
        offset, limit = max(0, int(offset)), max(1, min(500, int(limit)))
        plan = ledger.records(run_id, "plan")
        terminal = ledger.terminal(run_id)
        return {"schema_version": "screener-ai-screener-coverage/1.0.0", "run_id": run_id, "run": head[0],
                "plan": plan[0] if plan else None, "calls": ledger.records(run_id, "batch"),
                "unfinished_calls": ledger.unfinished_batches(run_id),
                "rounds": ledger.records(run_id, "round"), "terminal": terminal,
                "rows": {"phase": phase, "class": row_class, "total": len(rows), "offset": offset, "limit": limit,
                         "items": [{"instrument_id": row[0], "class": row[1], "reasons": row[2]} for row in rows[offset:offset + limit]]}}

    def current(self, account_id: str) -> dict[str, Any]:
        """What a page shows and attaches to: the engine's state and budget, the run in progress and the latest
        finished run (without result bodies). Reads only; calls no model and starts nothing."""
        service = self._service()
        ai = service.ai_status()
        interrupted = self._interrupted(service, account_id)
        with self._lock:
            active = self._active.get(account_id)
            latest = next((run for run in reversed(self._runs.values())
                           if run["account_id"] == account_id and run["state"] != "RUNNING" and run["scope"].get("method") != "STAGED_LOCAL_FIRST_EXPERIMENTAL"), None)
            experimental = next((run for run in reversed(self._runs.values()) if run["account_id"] == account_id
                                  and run["state"] != "RUNNING" and run["scope"].get("method") == "STAGED_LOCAL_FIRST_EXPERIMENTAL"), None)
            budget = self._budget(ai)
            # What the next run needs depends on its query, so only a spent budget blocks here; a run that cannot
            # be paid for is refused by its own plan, before any model call, with the exact shortfall.
            exhausted = ai.get("reason") == "SYNTHESIS_DAILY_BUDGET_EXHAUSTED" or (
                budget is not None and (budget["headroom"] == 0 or budget["requests_left"] == 0))
            state = ("RUNNING" if active is not None else "NOT_CONFIGURED" if ai.get("state") == "NOT_CONFIGURED"
                     else "WAITING_FOR_BUDGET" if exhausted else "BLOCKED" if ai.get("state") != "AVAILABLE" else "IDLE")
            return {"schema_version": RUNS_SCHEMA, "state": state,
                    "ai": {key: ai.get(key) for key in ("state", "reason", "provider_id", "model_id", "runtime")}, "budget": budget,
                    "active": self._snapshot(active, result=False) if active is not None else None,
                    "latest": self._snapshot(latest, result=False) if latest is not None else self._restored(account_id, result=False),
                    "experimental_latest": self._snapshot(experimental, result=False) if experimental is not None else self._restored_staged(account_id,result=False),
                    "interrupted": interrupted}

    def _budget(self, ai: dict[str, Any]) -> dict[str, Any] | None:
        """The shared daily budget. ``run_size`` is what the last run on this engine's model held for its whole
        plan; a different query needs a different amount, so ``runs_left`` is that run repeated, not a promise."""
        raw = ai.get("budget")
        if not raw:
            return None
        headroom = max(0, int(raw["max_tokens"]) - int(raw["tokens"]))
        requests_left = max(0, int(raw["max_requests"]) - int(raw["requests"]))
        per_run = self._reservations.get(ai.get("model_id") or "")
        resets = datetime.combine(date.fromisoformat(raw["day"]) + timedelta(days=1), day_time(), UTC)
        return {"day": raw["day"], "tokens": int(raw["tokens"]), "max_tokens": int(raw["max_tokens"]), "requests": int(raw["requests"]),
                "max_requests": int(raw["max_requests"]), "headroom": headroom, "requests_left": requests_left,
                "held_tokens": int(raw.get("held_tokens") or 0), "held_requests": int(raw.get("held_requests") or 0),
                "run_size": per_run, "run_size_basis": "LAST_RUN_HOLD" if per_run else None,
                "runs_left": min(requests_left, headroom // per_run) if per_run else None,
                "resets_at": resets.isoformat().replace("+00:00", "Z")}

    def _enter(self, run: dict[str, Any], stage: str, detail: dict[str, Any]) -> None:
        if stage not in _stage_order(run["scope"]):
            return
        kept = {key: detail[key] for key in _DETAIL_KEYS if key in detail}
        with self._lock:
            now = self._monotonic()
            stages = run["stages"]
            if stages and stages[-1]["stage"] == stage:
                stages[-1]["detail"].update(kept)
            else:
                if stages:
                    stages[-1]["ended"] = now
                stages.append({"stage": stage, "started_at": self._clock(), "started": now, "ended": None, "detail": kept})
            for key in ("intake_count", "sufficient_count", "packet_bytes"):
                if key in kept:
                    run[key] = kept[key]
            run["progress"].update({key: kept[key] for key in _PROGRESS_KEYS if kept.get(key) is not None})
            if stage == "BUDGET_HELD" and isinstance(kept.get("held_tokens"), int) and run["engine"]["model_id"]:
                self._reservations[run["engine"]["model_id"]] = kept["held_tokens"]

    def _work(self, service: Any, run: dict[str, Any], scope: dict[str, Any]) -> None:
        result = error = None
        try:
            with observing(lambda stage, detail: self._enter(run, stage, detail)):
                full = getattr(service, "run_universe", None)
                # Passed only when set, so a harness service with the original signature keeps working.
                extra = {"spend_limit": run["spend_limit"]} if run.get("spend_limit") is not None else {}
                if run.get("slice_plan"):
                    extra["slice_plan"] = run["slice_plan"]
                result = (full(scope, run_id=run["run_id"], account_id=run["account_id"], should_stop=run["stop"].is_set, **extra)
                          if callable(full) else service.run(scope))
        except Exception as exc:  # noqa: BLE001 - a run must always end; only a stable code leaves this process
            message = str(exc)
            error = {"code": message if _STABLE_CODE.fullmatch(message) else "AI_SCREENER_RUN_FAILED",
                     "stage": run["stages"][-1]["stage"] if run["stages"] else None}
        with self._lock:
            now = self._monotonic()
            if run["stages"]:
                run["stages"][-1]["ended"] = now
            run.update(state="FAILED" if error else "COMPLETED", result=result, error=error, finished=now, finished_at=self._clock())
            if result is not None:
                run["engine"] = {key: result.get(key) for key in ("provider_id", "model_id", "runtime")}
                latency, model = result.get("latency_ms"), result.get("model_id")
                # A measured call only: a cached answer or a refusal says nothing about how long this model takes.
                if result.get("cache") == "MISS" and isinstance(latency, int) and latency > 0 and model:
                    self._latencies.setdefault(model, deque(maxlen=_LATENCY_SAMPLES)).append(latency)
            if self._active.get(run["account_id"]) is run:
                del self._active[run["account_id"]]
            _LIVE.discard(run["run_id"])

    def _snapshot(self, run: dict[str, Any], *, joined: bool = False, result: bool = True,
                  joined_scope: bool | None = None) -> dict[str, Any]:
        now = self._monotonic()
        running = run["state"] == "RUNNING"
        samples = self._latencies.get(run["engine"]["model_id"] or "", ())
        return {
            "schema_version": RUN_SCHEMA, "run_id": run["run_id"], "account_id": run["account_id"], "state": run["state"],
            "joined": joined, "joined_scope": joined_scope, "deferred": bool(joined and joined_scope is False),
            "scope": run["scope"], "origin": run.get("origin", "OPERATOR"),
            "stage": run["stages"][-1]["stage"] if running and run["stages"] else None, "stage_order": list(_stage_order(run["scope"])),
            "stages": [{"stage": item["stage"], "started_at": _iso(item["started_at"]),
                        "elapsed_ms": int(round(((item["ended"] if item["ended"] is not None else now) - item["started"]) * 1000)),
                        "detail": dict(item["detail"])} for item in run["stages"]],
            "started_at": _iso(run["started_at"]), "finished_at": _iso(run["finished_at"]) if run["finished_at"] is not None else None,
            "elapsed_ms": int(round(((run["finished"] if run["finished"] is not None else now) - run["started"]) * 1000)),
            "engine": dict(run["engine"]), "timeout_seconds": run["timeout_seconds"],
            "typical_latency_ms": int(statistics.median(samples)) if samples else None, "typical_latency_samples": len(samples),
            "intake_count": run["intake_count"], "sufficient_count": run["sufficient_count"], "packet_bytes": run["packet_bytes"],
            "progress": dict(run.get("progress") or {}),
            "stop_requested": bool(run.get("stop") and run["stop"].is_set()),
            "stop_requested_at": _iso(run["stop_requested_at"]) if run.get("stop_requested_at") is not None else None,
            "summary": run_summary(run["result"]) if run["result"] is not None else None,
            "result": run["result"] if result else None, "error": dict(run["error"]) if run["error"] else None,
        }


def _question(scope: dict[str, Any]) -> str:
    """Identity of the Screener query a run answered. The list snapshot is not part of it."""
    return json.dumps({key: scope.get(key) for key in ("universe", "search", "sort", "descending", "filters", "view", "screen")},
                      sort_keys=True, default=str)


def run_history(repository: Any, *, limit: int = 20,
                scope_for: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None) -> dict[str, Any]:
    """Stored candidate runs, newest first, each with what it added or removed against the previous run of the
    same Screener query. Reads the durable record, so runs made by the scheduled loop are listed too.

    A full-universe record stores its final reduction's result, whose scope is not the operator's query; that
    query lives on the coverage ledger's terminal record, which ``scope_for`` reads. Without it the record's own
    scope is used."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_HISTORY:
        raise ValueError("INVALID_HISTORY_LIMIT")
    # Read past the page so the oldest listed run can still be compared with its real predecessor.
    records = repository.recent("candidate_run", min(200, limit * 4))
    scopes = [(scope_for(record) if scope_for is not None else None) or record.get("scope") or {} for record in records]
    rows = []
    for index, record in enumerate(records[:limit]):
        scope = scopes[index]
        selected = [pick["instrument_id"] for pick in record.get("candidates") or []]
        previous_index = next((later for later in range(index + 1, len(records)) if _question(scopes[later]) == _question(scope)), None)
        previous = records[previous_index] if previous_index is not None else None
        before = [pick["instrument_id"] for pick in previous.get("candidates") or []] if previous is not None else None
        coverage = record.get("coverage") or {}
        universe = record.get("universe_coverage") or {}
        rows.append({
            "candidate_run_id": record.get("run_id"), "generated_at": record.get("generated_at"), "decision_cutoff": record.get("decision_cutoff"),
            "state": record.get("state"), "reason": record.get("reason"), "provider_id": record.get("provider_id"),
            "model_id": record.get("model_id"), "runtime": record.get("runtime"), "cache": record.get("cache"), "simulated": record.get("simulated"),
            "tokens_input": record.get("tokens_input"), "tokens_output": record.get("tokens_output"), "latency_ms": record.get("latency_ms"),
            "selected": [{"instrument_id": pick["instrument_id"], "rank": pick["rank"]} for pick in record.get("candidates") or []],
            # A full-universe run's intake is every row the batches evaluated, not the finalists of its last call.
            "selected_count": len(selected), "intake_count": universe.get("ai_evaluated_count", coverage.get("candidate_intake")),
            "scope": {key: scope.get(key) for key in ("universe", "search", "sort", "descending", "filters", "view", "screen")},
            "previous_run_id": previous.get("run_id") if previous is not None else None,
            "added": [item for item in selected if item not in before] if before is not None else None,
            "removed": [item for item in before if item not in selected] if before is not None else None,
        })
    return {"schema_version": HISTORY_SCHEMA, "runs": rows, "limit": limit}


_RUNS: AiScreenerRuns | None = None


def ai_screener_runs() -> AiScreenerRuns:
    global _RUNS
    if _RUNS is None:
        _RUNS = AiScreenerRuns()
    return _RUNS


__all__ = ["AiScreenerRuns", "HISTORY_SCHEMA", "MAX_HISTORY", "MAX_TRACKED_RUNS", "RUNS_SCHEMA", "RUN_SCHEMA", "STAGES", "ai_screener_runs",
           "evidence_reasons", "run_history", "run_summary"]
