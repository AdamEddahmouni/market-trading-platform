"""AI Screener runs the operator can watch.

Starting a run returns at once; the run continues on a server thread and reports the stage it is
really in, with elapsed time. The model call is one blocking request with no streaming, so there is
no percentage to report and none is invented. One run per account: a second start joins the run in
progress. Runs are tracked in this process only; the stored candidate run is the durable record.

This module adds no inference path: a run is exactly ``ScreenerAiService.run`` for the same scope.
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

RUN_SCHEMA = "screener-ai-screener-run/1.0.0"
RUNS_SCHEMA = "screener-ai-screener-runs/1.2.0"
HISTORY_SCHEMA = "screener-ai-screener-history/1.0.0"
MAX_HISTORY = 50
_REASON_SYMBOLS = 3
_MAX_REASONS = 8
# The order the work happens in. A stage that did not happen (no budget, cached answer) is absent from a run.
STAGES = ("SCOPE", "NEWS", "EVIDENCE", "PACKET", "BUDGET_RESERVED", "MODEL_CALL", "VALIDATION", "STORED")
MAX_TRACKED_RUNS = 20
_LATENCY_SAMPLES = 20
_DETAIL_KEYS = ("intake_count", "sufficient_count", "packet_bytes", "reserved_tokens", "shared")
_STABLE_CODE = re.compile(r"[A-Z][A-Z0-9_]*")


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


def evidence_reasons(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Why a run had little to select from, read from its evidence packet and never from model prose.

    Each reason counts the candidates it applies to and names a few of them: blocked evidence by capability and
    reason code, candidates the model saw with no news story, and candidates without sufficient evidence."""
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


def run_summary(result: dict[str, Any]) -> dict[str, Any]:
    """What the Screener needs from a finished run without the evidence packet: the outcome, which rows the model
    was shown and which it selected, and the evidence-derived reasons."""
    return {
        "state": result.get("state"), "reason": result.get("reason"), "candidate_run_id": result.get("run_id"),
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
        self._latencies: dict[str, deque[int]] = {}
        self._reservations: dict[str, int] = {}

    def _service(self) -> Any:
        if self._fixed_service is not None:
            return self._fixed_service
        from .screener_ai import screener_ai_service

        return screener_ai_service()

    def start(self, account_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Start a run for this account, or join the one already in progress. ValueError for an invalid scope."""
        service = self._service()
        scope = service.validate_scope(body)
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
                   "sufficient_count": None, "packet_bytes": None, "result": None, "error": None}
            self._active[account_id] = run
            self._runs[run["run_id"]] = run
            for run_id in [key for key, value in self._runs.items() if value["state"] != "RUNNING"][:max(0, len(self._runs) - MAX_TRACKED_RUNS)]:
                del self._runs[run_id]
            snapshot = self._snapshot(run)
        threading.Thread(target=self._work, args=(service, run, scope), name="imp-ai-screener-run", daemon=True).start()
        return snapshot

    def read(self, account_id: str, run_id: str) -> dict[str, Any] | None:
        """One of this account's tracked runs, with its full result once finished."""
        with self._lock:
            run = self._runs.get(run_id)
            return self._snapshot(run) if run is not None and run["account_id"] == account_id else None

    def current(self, account_id: str) -> dict[str, Any]:
        """What a page shows and attaches to: the engine's state and budget, the run in progress and the latest
        finished run (without result bodies). Reads only; calls no model and starts nothing."""
        ai = self._service().ai_status()
        with self._lock:
            active = self._active.get(account_id)
            latest = next((run for run in reversed(self._runs.values())
                           if run["account_id"] == account_id and run["state"] != "RUNNING"), None)
            budget = self._budget(ai)
            exhausted = ai.get("reason") == "SYNTHESIS_DAILY_BUDGET_EXHAUSTED" or (budget is not None and budget["runs_left"] == 0)
            state = ("RUNNING" if active is not None else "NOT_CONFIGURED" if ai.get("state") == "NOT_CONFIGURED"
                     else "WAITING_FOR_BUDGET" if exhausted else "BLOCKED" if ai.get("state") != "AVAILABLE" else "IDLE")
            return {"schema_version": RUNS_SCHEMA, "state": state,
                    "ai": {key: ai.get(key) for key in ("state", "reason", "provider_id", "model_id", "runtime")}, "budget": budget,
                    "active": self._snapshot(active, result=False) if active is not None else None,
                    "latest": self._snapshot(latest, result=False) if latest is not None else None}

    def _budget(self, ai: dict[str, Any]) -> dict[str, Any] | None:
        """The shared daily budget in runs-left terms. The size of a run is the last reservation this engine's
        model actually held; until one has been held it is unknown and no count is given."""
        raw = ai.get("budget")
        if not raw:
            return None
        headroom = max(0, int(raw["max_tokens"]) - int(raw["tokens"]))
        requests_left = max(0, int(raw["max_requests"]) - int(raw["requests"]))
        per_run = self._reservations.get(ai.get("model_id") or "")
        resets = datetime.combine(date.fromisoformat(raw["day"]) + timedelta(days=1), day_time(), UTC)
        return {"day": raw["day"], "tokens": int(raw["tokens"]), "max_tokens": int(raw["max_tokens"]), "requests": int(raw["requests"]),
                "max_requests": int(raw["max_requests"]), "headroom": headroom, "requests_left": requests_left,
                "run_size": per_run, "run_size_basis": "LAST_RESERVATION" if per_run else None,
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
            if stage == "BUDGET_RESERVED" and isinstance(kept.get("reserved_tokens"), int) and run["engine"]["model_id"]:
                self._reservations[run["engine"]["model_id"]] = kept["reserved_tokens"]

    def _work(self, service: Any, run: dict[str, Any], scope: dict[str, Any]) -> None:
        result = error = None
        try:
            with observing(lambda stage, detail: self._enter(run, stage, detail)):
                result = service.run(scope)
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
            "summary": run_summary(run["result"]) if run["result"] is not None else None,
            "result": run["result"] if result else None, "error": dict(run["error"]) if run["error"] else None,
        }


def _question(scope: dict[str, Any]) -> str:
    """Identity of the Screener query a run answered. The list snapshot is not part of it."""
    return json.dumps({key: scope.get(key) for key in ("universe", "search", "sort", "descending", "filters", "view", "screen")},
                      sort_keys=True, default=str)


def run_history(repository: Any, *, limit: int = 20) -> dict[str, Any]:
    """Stored candidate runs, newest first, each with what it added or removed against the previous run of the
    same Screener query. Reads the durable record, so runs made by the scheduled loop are listed too."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_HISTORY:
        raise ValueError("INVALID_HISTORY_LIMIT")
    # Read past the page so the oldest listed run can still be compared with its real predecessor.
    records = repository.recent("candidate_run", min(200, limit * 4))
    rows = []
    for index, record in enumerate(records[:limit]):
        scope = record.get("scope") or {}
        selected = [pick["instrument_id"] for pick in record.get("candidates") or []]
        previous = next((older for older in records[index + 1:] if _question(older.get("scope") or {}) == _question(scope)), None)
        before = [pick["instrument_id"] for pick in previous.get("candidates") or []] if previous is not None else None
        coverage = record.get("coverage") or {}
        rows.append({
            "candidate_run_id": record.get("run_id"), "generated_at": record.get("generated_at"), "decision_cutoff": record.get("decision_cutoff"),
            "state": record.get("state"), "reason": record.get("reason"), "provider_id": record.get("provider_id"),
            "model_id": record.get("model_id"), "runtime": record.get("runtime"), "cache": record.get("cache"), "simulated": record.get("simulated"),
            "tokens_input": record.get("tokens_input"), "tokens_output": record.get("tokens_output"), "latency_ms": record.get("latency_ms"),
            "selected": [{"instrument_id": pick["instrument_id"], "rank": pick["rank"]} for pick in record.get("candidates") or []],
            "selected_count": len(selected), "intake_count": coverage.get("candidate_intake"),
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
