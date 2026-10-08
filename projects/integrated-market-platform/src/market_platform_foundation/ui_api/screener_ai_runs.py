"""AI Screener runs the operator can watch.

Starting a run returns at once; the run continues on a server thread and reports the stage it is
really in, with elapsed time and the counts it has actually produced: rows enumerated, rows assessed,
rows eligible, batches finished. No percentage is derived from assumed model latency. One run per
account: a second start joins the run in progress.

A run is ``ScreenerAiService.run_universe`` for the scope: the full-universe method. Its receipts are
written to the coverage ledger as it goes, so a restart finds the run it killed and closes it as
INTERRUPTED; nothing is resumed. Stop prevents the next model call; a call already sent is not cancelled,
because the provider offers no confirmed cancellation, and its tokens stay charged.

A service without ``run_universe`` (an acceptance harness carrying a prebuilt result) runs its ``run``.
"""
from __future__ import annotations

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
# The order the work happens in. A stage that did not happen (no budget, nothing eligible) is absent from a run.
# BATCH_INFERENCE and GLOBAL_REDUCTION each cover many bounded calls; their detail names the call in progress.
STAGES = ("ENUMERATION", "ELIGIBILITY", "PLANNING", "BUDGET_HELD", "BATCH_INFERENCE", "GLOBAL_REDUCTION", "STORED")
MAX_TRACKED_RUNS = 20
_LATENCY_SAMPLES = 20
# Counts a run has actually produced so far; the latest value of each is the run's progress.
_PROGRESS_KEYS = ("universe_count", "assessed_count", "eligible_count", "batches_planned", "batches_completed",
                  "rows_evaluated", "required_tokens", "held_tokens", "held_requests", "finalists", "round")
_DETAIL_KEYS = (*_PROGRESS_KEYS, "batch", "step", "packet_bytes", "reserved_tokens", "shared", "intake_count", "sufficient_count")
_STABLE_CODE = re.compile(r"[A-Z][A-Z0-9_]*")
# Runs alive in this process, across every tracker: restart recovery must never close one of these.
_LIVE: set[str] = set()
_RECOVERY = threading.Lock()


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


def _coverage(result: dict[str, Any]) -> dict[str, Any] | None:
    """The run's accounting without its plan detail. None for a result that carries none."""
    block = result.get("universe_coverage")
    if not isinstance(block, dict):
        return None
    keys = ("method_version", "status", "reason", "universe_count", "assessed_count", "eligible_count", "ai_evaluated_count",
            "ai_coverage_pct", "batches_planned", "batches_completed", "model_calls", "finalist_count", "selected_count",
            "coverage_complete", "selection_complete", "reconciled", "counts", "budget", "reduction")
    return {key: block.get(key) for key in keys}


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    """What a status strip needs from a finished run, without the evidence packet."""
    coverage = _coverage(result)
    # Only a completed global selection (or a single-request result) names a stored candidate run.
    stored = coverage is None or coverage["status"] == "GLOBAL_SELECTION_COMPLETE"
    return {
        "coverage": coverage, "provisional_count": len(result.get("provisional") or []),
        "candidate_run_id": result.get("run_id") if stored else None,
        "state": result.get("state"), "reason": result.get("reason"),
        "selected": [{"instrument_id": pick["instrument_id"], "rank": pick["rank"]} for pick in result.get("candidates", [])],
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
        self._latencies: dict[str, deque[int]] = {}
        self._reservations: dict[str, int] = {}
        self._recovered: list[dict[str, Any]] = []

    def _recover(self, service: Any) -> None:
        """Close full-universe runs a previous process left open and release their unused holds. Called only from
        an operator write (Run, Stop), never from a status read."""
        if not callable(getattr(service, "run_universe", None)):
            return
        try:
            from ..local_state.ai_screener_coverage import coverage_ledger
            from .screener_ai_coverage import interrupt_open_runs

            ledger = coverage_ledger()
            with _RECOVERY:
                # ``_LIVE`` itself, not a copy: a run is registered there before it writes its first receipt.
                for run_id in interrupt_open_runs(ledger, tracked=_LIVE, release=service.release_hold, clock=self._clock):
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
            for run_id in ledger.open_runs():
                head = ledger.records(run_id, "run")
                if run_id in _LIVE or not head or head[0].get("account_id") != account_id:
                    continue
                found.append({"run_id": run_id, "account_id": account_id, "status": "INTERRUPTED", "reason": "SERVER_RESTARTED_DURING_RUN",
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

    def start(self, account_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Start a run for this account, or join the one already in progress. ValueError for an invalid scope."""
        service = self._service()
        scope = service.validate_scope(body)
        self._recover(service)
        with self._lock:
            active = self._active.get(account_id)
            if active is not None:
                return self._snapshot(active, joined=True)
        engine = service.engine()
        with self._lock:
            active = self._active.get(account_id)
            if active is not None:
                return self._snapshot(active, joined=True)
            run = {"run_id": uuid.uuid4().hex, "account_id": account_id, "scope": scope, "state": "RUNNING",
                   "started_at": self._clock(), "started": self._monotonic(), "finished_at": None, "finished": None,
                   "engine": {key: engine[key] for key in ("provider_id", "model_id", "runtime")},
                   "timeout_seconds": engine["timeout_seconds"], "stages": [], "intake_count": None,
                   "sufficient_count": None, "packet_bytes": None, "result": None, "error": None,
                   "progress": {}, "stop": threading.Event(), "stop_requested_at": None}
            self._active[account_id] = run
            self._runs[run["run_id"]] = run
            _LIVE.add(run["run_id"])
            for run_id in [key for key, value in self._runs.items() if value["state"] != "RUNNING"][:max(0, len(self._runs) - MAX_TRACKED_RUNS)]:
                del self._runs[run_id]
            snapshot = self._snapshot(run)
        threading.Thread(target=self._work, args=(service, run, scope), name="imp-ai-screener-run", daemon=True).start()
        return snapshot

    def read(self, account_id: str, run_id: str) -> dict[str, Any] | None:
        """One of this account's tracked runs, with its full result once finished."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is not None:
                return self._snapshot(run) if run["account_id"] == account_id else None
        return self._restored(account_id, run_id=run_id)

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
                "progress": {}, "stop_requested": False, "stop_requested_at": None, "summary": _summary(restored),
                "result": restored if result else None, "error": None}

    def stop(self, account_id: str, run_id: str) -> dict[str, Any] | None:
        """Ask this account's run to start no further model call. A call already sent finishes and stays charged;
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
                           if run["account_id"] == account_id and run["state"] != "RUNNING"), None)
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
        if stage not in STAGES:
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
                result = (full(scope, run_id=run["run_id"], account_id=run["account_id"], should_stop=run["stop"].is_set)
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

    def _snapshot(self, run: dict[str, Any], *, joined: bool = False, result: bool = True) -> dict[str, Any]:
        now = self._monotonic()
        running = run["state"] == "RUNNING"
        samples = self._latencies.get(run["engine"]["model_id"] or "", ())
        return {
            "schema_version": RUN_SCHEMA, "run_id": run["run_id"], "account_id": run["account_id"], "state": run["state"],
            "joined": joined, "scope": run["scope"],
            "stage": run["stages"][-1]["stage"] if running and run["stages"] else None, "stage_order": list(STAGES),
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
            "summary": _summary(run["result"]) if run["result"] is not None else None,
            "result": run["result"] if result else None, "error": dict(run["error"]) if run["error"] else None,
        }


_RUNS: AiScreenerRuns | None = None


def ai_screener_runs() -> AiScreenerRuns:
    global _RUNS
    if _RUNS is None:
        _RUNS = AiScreenerRuns()
    return _RUNS


__all__ = ["AiScreenerRuns", "MAX_TRACKED_RUNS", "RUNS_SCHEMA", "RUN_SCHEMA", "STAGES", "ai_screener_runs"]
