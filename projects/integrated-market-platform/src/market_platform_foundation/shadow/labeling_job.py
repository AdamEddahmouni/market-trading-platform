"""Delayed labeling from sealed admitted captures (Run 1, spec section 7).

P0 was persisted at prediction time (decision detail ``reference_price``);
this job never reconstructs it. P30 is the first eligible captured trade
with ``target <= event_time <= target + tolerance``. Zero returns and
unlabelable outcomes become immutable annotations, never labels. Causality
is enforced by the governed ``attach_label``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..market_data.capture import read_envelopes
from .labeling import LabelingViolation, attach_label

_NS = 1_000_000_000


@dataclass(frozen=True)
class LabelingConfig:
    horizon_seconds: int = 1800
    tolerance_seconds: int = 300


def _captured_ticks(capture_paths: list[Path], instrument_id: str) -> list[tuple[int, float, int]]:
    """(event_time_ns, last_price, received_ns) sorted by event time."""
    rows: list[tuple[int, float, int]] = []
    for path in capture_paths:
        for envelope in read_envelopes(path):
            if "TICK" not in str(envelope.get("capability") or ""):
                continue
            if str(envelope.get("instrument_id") or "").upper() != instrument_id.upper():
                continue
            payload = envelope.get("raw_payload") or {}
            price = payload.get("last_price")
            if price is None:
                continue
            clocks = envelope.get("clocks") or {}
            rows.append((
                int(payload.get("event_time") or clocks.get("received_time_ns") or 0),
                float(price),
                int(clocks.get("received_time_ns") or 0),
            ))
    rows.sort(key=lambda r: r[0])
    return rows


def label_due(
    *,
    shadow_store: Any,
    experiment_store: Any,
    manifest: Any,
    capture_paths: list[Path],
    now_ns: int,
    config: LabelingConfig,
) -> dict[str, Any]:
    run_id = manifest.run_id
    decisions = list(experiment_store.iter_decisions(run_id, outcome="PREDICTED"))
    summary: dict[str, Any] = {"labeled": 0, "zero_return": 0, "unlabelable": {}, "pending": 0}
    ticks_cache: dict[str, list[tuple[int, float, int]]] = {}

    def ticks(instrument: str) -> list[tuple[int, float, int]]:
        if instrument not in ticks_cache:
            ticks_cache[instrument] = _captured_ticks(capture_paths, instrument)
        return ticks_cache[instrument]

    for decision in decisions:
        detail = decision["detail"]
        ref = detail.get("reference_price") or {}
        if not ref.get("price"):
            experiment_store.add_annotation(
                decision["id"], "UNLABELABLE_NO_REFERENCE_PRICE", {}, now_ns
            )
            summary["unlabelable"]["NO_REFERENCE_PRICE"] = (
                summary["unlabelable"].get("NO_REFERENCE_PRICE", 0) + 1
            )
            continue
        prediction = shadow_store.get_prediction(decision["prediction_id"])
        if prediction is None:
            summary["pending"] += 1
            continue
        if shadow_store.get_label_for_run_prediction(run_id, prediction.prediction_id) is not None:
            continue
        target_ns = decision_time_of(prediction) + config.horizon_seconds * _NS
        if now_ns < target_ns + config.tolerance_seconds * _NS:
            summary["pending"] += 1
            continue
        candidates = [
            t
            for t in ticks(decision["instrument_id"])
            if target_ns <= t[0] <= target_ns + config.tolerance_seconds * _NS
        ]
        if not candidates:
            experiment_store.add_annotation(
                decision["id"], "UNLABELABLE_NO_HORIZON_TRADE", {"target_ns": target_ns}, now_ns
            )
            summary["unlabelable"]["NO_HORIZON_TRADE"] = (
                summary["unlabelable"].get("NO_HORIZON_TRADE", 0) + 1
            )
            continue
        p30_event_ns, p30_price, p30_received_ns = candidates[0]
        p0_price = float(ref["price"])
        r30 = p30_price / p0_price - 1.0
        if r30 == 0.0:
            experiment_store.add_annotation(
                decision["id"],
                "LABEL_ZERO_RETURN",
                {"p0_price": p0_price, "p30_price": p30_price, "target_ns": target_ns},
                now_ns,
            )
            summary["zero_return"] += 1
            continue
        try:
            attach_label(
                shadow_store,
                prediction,
                observed_positive=r30 > 0.0,
                label_time_ns=p30_event_ns,
                available_time_ns=max(p30_received_ns, p30_event_ns + 1),
                label_source="LIVE_ADMITTED_CAPTURE",
                observed_return_bps=round(r30 * 10_000.0, 6),
            )
        except LabelingViolation:
            summary["unlabelable"]["CAUSALITY"] = (
                summary["unlabelable"].get("CAUSALITY", 0) + 1
            )
            continue
        kind = "LABEL_LABELED_UP" if r30 > 0.0 else "LABEL_LABELED_DOWN"
        experiment_store.add_annotation(
            decision["id"],
            kind,
            {
                "r30_bps": round(r30 * 10_000.0, 6),
                "p0_price": p0_price,
                "p30_price": p30_price,
                "p30_event_ns": p30_event_ns,
                "capture_ids": [str(p) for p in capture_paths],
            },
            now_ns,
        )
        summary["labeled"] += 1
    return summary


def decision_time_of(prediction: Any) -> int:
    return int(prediction.decision_time_ns)
