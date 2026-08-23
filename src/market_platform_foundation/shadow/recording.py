"""Opportunity resolver binding admitted trades into the Run 1 ledgers.

One opportunity per ``(run_id, instrument, 60-second bucket)``: the first
qualifying admitted trade of a bucket decides it and every resolution is
durable (predicted, model-abstained, or system-skipped). Later observations
in a decided bucket are silent no-op counters. This module never raises
into the admission path (spec sections 4, 9, 10).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .predictor import FrozenPredictorConfig, eligible_trades, evaluate_prediction, reference_price
from .runs import record_prediction
from .session import ET, decision_bucket, outside_session_window, session_bounds_ns
from .store import ShadowStore

_NS = 1_000_000_000
HORIZON_SECONDS = 1800
TOLERANCE_SECONDS = 300


@dataclass
class RecorderStats:
    predictions_written: int = 0
    model_abstentions: int = 0
    quality_skips: int = 0
    system_skips: int = 0
    duplicate_bucket_observations: int = 0
    errors_total: int = 0
    consecutive_errors: int = 0
    last_success_ns: int | None = None
    last_error_code: str | None = None


class ShadowPredictionRecorder:
    """Resolves decision opportunities from observational state. Never raises."""

    def __init__(
        self,
        *,
        shadow_store: ShadowStore,
        experiment_store: Any,
        manifest: Any,
        config: FrozenPredictorConfig,
        session_dates: list[str],
        capture_id: str,
        clock: Any | None = None,
    ) -> None:
        self._shadow = shadow_store
        self._exp = experiment_store
        self._manifest = manifest
        self._config = config
        self._dates = set(session_dates)
        self._capture_id = capture_id
        self._clock = clock or time.time_ns
        self._bounds = {d: session_bounds_ns(d) for d in sorted(self._dates)}
        self._decided: set[tuple[str, int]] = set()
        self.enabled = self._exp.run_state(manifest.run_id) == "OPEN"
        self._stats = RecorderStats()

    def on_admitted(self, state: Any, envelope: dict[str, Any], result: dict[str, Any]) -> None:
        try:
            self._resolve(state, envelope)
        except Exception as exc:  # boundary must never raise into admission
            self._note_error("RECORDER_EXCEPTION", {"error": repr(exc)})

    def stats(self) -> RecorderStats:
        return self._stats

    def health(self) -> dict[str, Any]:
        return {
            "shadow_recording_enabled": self.enabled,
            "shadow_run_id": self._manifest.run_id,
            "shadow_run_state": self._exp.run_state(self._manifest.run_id),
            "shadow_last_success_ns": self._stats.last_success_ns,
            "shadow_last_error_code": self._stats.last_error_code,
            "shadow_error_count": self._stats.errors_total,
            "shadow_consecutive_errors": self._stats.consecutive_errors,
            "shadow_predictions_written": self._stats.predictions_written,
            "shadow_abstentions_written": self._stats.model_abstentions,
            "shadow_duplicate_bucket_observations": self._stats.duplicate_bucket_observations,
        }

    # -- internals -----------------------------------------------------------

    def _resolve(self, state: Any, envelope: dict[str, Any]) -> None:
        if not self.enabled:
            return  # defensive: runtime does not construct us unless enabled
        instrument = str(envelope.get("instrument_id") or "").upper()
        if instrument == "" or instrument not in {str(s).upper() for s in self._manifest.universe}:
            return
        if "TICK" not in str(envelope.get("capability") or ""):
            return
        event_time_ns = int(envelope.get("event_time") or 0)
        if event_time_ns <= 0:
            return
        bucket = decision_bucket(event_time_ns)
        key = (instrument, bucket)
        if key in self._decided:
            self._stats.duplicate_bucket_observations += 1
            return
        session_date = self._session_date(event_time_ns)
        if session_date is None:
            self._skip(key, "OUTSIDE_RUN_WINDOW", {"decision_time_ns": event_time_ns})
            return
        _, close_ns = self._bounds[session_date]
        target_ns = event_time_ns + HORIZON_SECONDS * _NS
        if outside_session_window(target_ns, TOLERANCE_SECONDS * _NS, close_ns):
            self._skip(key, "OUTSIDE_SESSION_WINDOW", {"target_ns": target_ns})
            return
        eligible = eligible_trades(state.trades_for(instrument), decision_time_ns=event_time_ns)
        evaluation = evaluate_prediction(eligible, decision_time_ns=event_time_ns, config=self._config)
        ref = reference_price(eligible, decision_time_ns=event_time_ns)
        detail = dict(evaluation)
        detail["reference_price"] = ref
        detail["capture_id"] = self._capture_id
        detail["quality_state"] = sorted({
            str(t.get("admission") or "") for t in eligible
        }) or ["NONE"]
        provenance: dict[str, int] = {}
        for t in eligible:
            prov = str(t.get("aggressor_provenance") or "UNKNOWN")
            provenance[prov] = provenance.get(prov, 0) + 1
        detail["classification_provenance"] = provenance
        if evaluation["outcome"] != "PREDICTED":
            self._write(key, "ABSTAINED_MODEL", None, detail)
            self._stats.model_abstentions += 1
            self._note_success()
            return
        prediction, _inserted = record_prediction(
            self._shadow,
            self._manifest,
            instrument_id=instrument,
            decision_time_ns=event_time_ns,
            horizon_ns=HORIZON_SECONDS * _NS,
            predicted_probability=evaluation["p_up"],
            regime_tag=session_date,
            pit_snapshot_ref=f"capture:{self._capture_id}",
            payload={
                "decision_research": {},
                "shadow_run1": {**evaluation, "reference_price": ref},
            },
            created_at_ns=int(self._clock()),
        )
        detail["prediction_ledger_binding"] = sha256_bytes(
            canonical_bytes({"pid": prediction.prediction_id})
        )[:16]
        self._write(key, "PREDICTED", prediction.prediction_id, detail)
        self._stats.predictions_written += 1
        self._note_success()

    def _write(self, key, outcome, prediction_id, detail) -> None:
        row_id, inserted = self._exp.record_decision_once(
            self._manifest.run_id,
            key[0],
            key[1],
            outcome,
            prediction_id=prediction_id,
            detail=detail,
            created_at_ns=int(self._clock()),
        )
        if inserted:
            self._decided.add(key)
        else:
            self._stats.duplicate_bucket_observations += 1

    def _skip(self, key, code: str, detail: dict[str, Any]) -> None:
        self._write(key, code, None, detail)
        self._stats.system_skips += 1
        self._note_success()

    def _session_date(self, event_time_ns: int) -> str | None:
        from datetime import datetime

        iso = datetime.fromtimestamp(event_time_ns / 1e9, tz=ET).date().isoformat()
        return iso if iso in self._dates else None

    def _note_success(self) -> None:
        self._stats.consecutive_errors = 0
        self._stats.last_success_ns = int(self._clock())

    def _note_error(self, code: str, detail: dict[str, Any]) -> None:
        self._stats.errors_total += 1
        self._stats.consecutive_errors += 1
        self._stats.last_error_code = code
        try:
            self._exp.log_error(self._manifest.run_id, int(self._clock()), code, detail)
        except Exception:  # even failure logging must never raise upward
            pass
