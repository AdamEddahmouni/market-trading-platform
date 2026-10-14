"""Server-owned live Paper forecast hook (default off).

Enabled only when ``IMP_PAPER_FORECAST_MODELS_DIR`` names a directory holding an ``ACTIVE.json`` written by the
forecast build tool, and only while the live feature-corpus window is running. When the Action service is
about to look up a governed Opportunity for a candidate, this hook first gives that exact candidate (its own
instrument record and evidence ids) one honest chance to mint one through ``mint_live_opportunity``. It
mints at most once per instrument per evidence set and never more often than ``MIN_MINT_INTERVAL_NS``.

Every attempt, minted or not, is journaled with its reasons. It calls no language model, has no order, Paper
submit or broker capability, and a failure here never fails the decision: the lookup simply finds nothing.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MODELS_ENV = "IMP_PAPER_FORECAST_MODELS_DIR"
ACTIVE_FILE = "ACTIVE.json"
PREREGISTRATION_FILE = "preregistration.json"
MIN_MINT_INTERVAL_NS = 60_000_000_000
ACTIVE_SCHEMA = "imp-live-forecast-active/1.0.0"

_HOOK: "LiveForecastHook | None" = None
_HOOK_LOCK = threading.Lock()


def _day(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, UTC).strftime("%Y-%m-%d")


class LiveForecastHook:
    def __init__(self, root: Path, *, window_getter=None, clock=time.time_ns) -> None:
        from ..intelligence.production.model_store import load_production_specialist_model
        from ..intelligence.production.live_training import scored_artifacts_match
        from ..strategy.path_a_forecast_producer import load_paper_demo_calibration
        from ..strategy.path_a_live_forecast import LiveForecastArtifacts, load_preregistration, preregistration_valid

        self.root = Path(root)
        self.clock = clock
        self.window_getter = window_getter
        self.lock = threading.Lock()
        self.last_attempt: dict[str, int] = {}
        self.counters = dict(attempts=0, minted=0, existing=0, refused=0, errors=0, throttled=0)
        active = json.loads((self.root / ACTIVE_FILE).read_text(encoding="utf-8"))
        if active.get("schema_version") != ACTIVE_SCHEMA:
            raise ValueError("FORECAST_ACTIVE_SCHEMA_MISMATCH")
        self.preregistration = load_preregistration(self.root / PREREGISTRATION_FILE)
        if not preregistration_valid(self.preregistration):
            raise ValueError("FORECAST_PREREGISTRATION_INVALID")
        self.build_id = str(active["build_id"])
        activated_ns = int(datetime.fromisoformat(str(active["activated_at"]).replace("Z", "+00:00")).timestamp() * 1_000_000_000)
        self.artifacts: dict[str, Any] = {}
        self.refused: dict[str, str] = {}
        for iid in active.get("instruments") or []:
            directory = self.root / self.build_id / iid
            try:
                evaluation = json.loads((directory / "evaluation.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.refused[iid] = "EVALUATION_UNREADABLE"
                continue
            model = load_production_specialist_model(directory / "model")
            calibration = load_paper_demo_calibration(directory / "calibration")
            if (not evaluation.get("eligible") or not scored_artifacts_match(
                    model, calibration, model_id=evaluation.get("model_id"),
                    calibration_model_id=evaluation.get("calibration_model_id"), artifact_hashes=evaluation.get("artifact_hashes"))):
                # Only a build that passed its preregistered holdout rule, with the very artifacts it scored, is used.
                self.refused[iid] = "NOT_ELIGIBLE_OR_ARTIFACT_MISMATCH"
                continue
            self.artifacts[iid] = LiveForecastArtifacts(instrument_id=iid, build_id=self.build_id, model=model,
                                                        calibration=calibration, activated_at_ns=activated_ns)

    def _window(self):
        if self.window_getter is not None:
            return self.window_getter()
        from .paper_forecast_corpus import corpus_service

        service = corpus_service()
        return service.window if service is not None and service.state == "RUNNING" else None

    def _journal(self, outcome: dict[str, Any]) -> None:
        path = self.root / "journal" / f"forecast-attempts-{_day(self.clock())}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(outcome, sort_keys=True, default=str, separators=(",", ":")) + "\n")

    @staticmethod
    def _existing(repository, candidate, cutoff_ns) -> bool:
        from ..strategy.path_a_live_forecast import qualified_instrument_id

        identities = {candidate["instrument"]["instrument_id"], qualified_instrument_id(candidate["instrument"])}
        evidence = {e["evidence_id"] for e in (*candidate.get("current_market_evidence", ()), *candidate.get("reference_evidence", ()))}
        return any(identities.intersection(o.scope.instrument_ids) and o.created_at_ns <= cutoff_ns
                   and (o.valid_until_ns is None or o.valid_until_ns > cutoff_ns)
                   and evidence.intersection(r.id for r in o.lineage_refs) for o in repository.list_opportunities())

    def ensure_opportunity(self, store, candidate, cutoff_ns: int) -> dict[str, Any] | None:
        from ..strategy.path_a_live_forecast import mint_live_opportunity

        iid = str(candidate["instrument"]["instrument_id"])
        artifacts = self.artifacts.get(iid)
        repository = getattr(store, "strategy_repository", None)
        if artifacts is None or repository is None or not hasattr(repository, "list_opportunities"):
            return None
        with self.lock:
            if self._existing(repository, candidate, cutoff_ns):
                self.counters["existing"] += 1
                return dict(instrument_id=iid, status="EXISTING")
            last = self.last_attempt.get(iid)
            if last is not None and cutoff_ns - last < MIN_MINT_INTERVAL_NS:
                self.counters["throttled"] += 1
                return dict(instrument_id=iid, status="THROTTLED")
            window = self._window()
            if window is None:
                outcome = dict(instrument_id=iid, status="FORECAST_UNAVAILABLE", reason_codes=["LIVE_WINDOW_UNAVAILABLE"])
            else:
                self.last_attempt[iid] = cutoff_ns
                self.counters["attempts"] += 1
                try:
                    outcome = mint_live_opportunity(
                        window=window, candidate=candidate, artifacts=artifacts, preregistration=self.preregistration,
                        account_id=store.paper_ledger.paper_account_id, decision_time_ns=cutoff_ns, repository=repository,
                        forecast_dir=self.root / "forecasts" / _day(cutoff_ns))
                except Exception as exc:  # noqa: BLE001 - recorded; the gate then finds no Opportunity
                    self.counters["errors"] += 1
                    outcome = dict(instrument_id=iid, status="ERROR", reason_codes=[f"{type(exc).__name__}:{str(exc)[:160]}"])
            if outcome.get("status") == "MINTED":
                self.counters["minted"] += 1
            elif outcome.get("status") != "ERROR":
                self.counters["refused"] += 1
            outcome.update(evidence_ids=[e.get("evidence_id") for e in candidate.get("current_market_evidence", ())][:8],
                           at=datetime.fromtimestamp(cutoff_ns / 1e9, UTC).isoformat())
            self._journal(outcome)
            return outcome

    def status(self) -> dict[str, Any]:
        return dict(schema_version="paper-live-forecast-status/1.0.0", build_id=self.build_id,
                    instruments=sorted(self.artifacts), refused=self.refused, counters=dict(self.counters),
                    calls_models=False, order_capability=False)


def live_forecast_hook(environ=os.environ) -> "LiveForecastHook | None":
    """The configured hook, loaded once; ``None`` when off or when its artifacts cannot be trusted."""
    global _HOOK
    with _HOOK_LOCK:
        if _HOOK is not None:
            return _HOOK
        root = str(environ.get(MODELS_ENV) or "").strip()
        if not root or not Path(root).is_absolute() or not (Path(root) / ACTIVE_FILE).is_file():
            return None
        try:
            _HOOK = LiveForecastHook(Path(root))
        except Exception:  # noqa: BLE001 - an untrusted build is not used; status reports it through start
            return None
        return _HOOK


def start_paper_live_forecast(environ=os.environ) -> dict[str, Any]:
    """Load the hook at startup so its state is reported once. Never raises into server startup."""
    root = str(environ.get(MODELS_ENV) or "").strip()
    if not root:
        return dict(enabled=False, reason="DISABLED")
    try:
        hook = LiveForecastHook(Path(root))
    except Exception as exc:  # noqa: BLE001
        return dict(enabled=False, reason=f"{type(exc).__name__}:{str(exc)[:160]}")
    global _HOOK
    with _HOOK_LOCK:
        _HOOK = hook
    return dict(enabled=True, **hook.status())


__all__ = ["LiveForecastHook", "MODELS_ENV", "live_forecast_hook", "start_paper_live_forecast"]
