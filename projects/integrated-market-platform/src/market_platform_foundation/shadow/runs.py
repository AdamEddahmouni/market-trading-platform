"""Shadow-run lifecycle over fixture/replay data (Platformization P6).

``open_shadow_run`` binds a content-hashed manifest into the store;
``record_prediction`` appends immutable predictions (insert-once);
``finalize_report`` joins stored predictions with labels and produces a
deterministic metrics report whose id is derived from its own content. All
timestamps are injected parameters — identical inputs reproduce identical
bytes end-to-end (no wall clock in any computed value).
"""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .labeling import attach_label
from .metrics import (
    CALIBRATION_BUCKETS,
    METRICS_VERSION,
    REPORT_ID_PREFIX,
    assumption_overlay,
    join_pairs,
    observed_metrics,
    segment_by_regime,
    walk_forward_evaluation,
)
from .records import (
    SHADOW_SCHEMA,
    ShadowOutcomeLabel,
    ShadowPredictionRecord,
    ShadowRunManifest,
    build_prediction,
    build_run_manifest,
)
from .store import ShadowStore


def prediction_payload_from_decision_example(example: dict[str, Any]) -> dict[str, Any]:
    """Trivial passthrough of a DECISION-RESEARCH-001 example into the payload.

    Minimal composition contract (design spec §7): the example dict is
    embedded verbatim under an opaque key; nothing is interpreted, validated,
    or coupled here.
    """
    return {"decision_research": example}


def open_shadow_run(
    store: ShadowStore,
    *,
    strategy_version: str,
    prediction_version: str,
    universe: tuple[str, ...],
    data_window_refs: tuple[dict[str, str], ...],
    train_window_end_ns: int,
    eval_window_start_ns: int,
    eval_window_end_ns: int,
    created_at_ns: int,
    config: dict[str, Any] | None = None,
) -> tuple[ShadowRunManifest, bool]:
    """Create (or idempotently reopen) a shadow run; returns (manifest, inserted)."""
    manifest = build_run_manifest(
        strategy_version=strategy_version,
        prediction_version=prediction_version,
        universe=universe,
        data_window_refs=data_window_refs,
        train_window_end_ns=train_window_end_ns,
        eval_window_start_ns=eval_window_start_ns,
        eval_window_end_ns=eval_window_end_ns,
        created_at_ns=created_at_ns,
        config=config,
    )
    return store.append_manifest(manifest)


def record_prediction(
    store: ShadowStore,
    manifest: ShadowRunManifest,
    *,
    instrument_id: str,
    decision_time_ns: int,
    horizon_ns: int,
    predicted_probability: float | None = None,
    abstained: bool = False,
    abstain_reason: str | None = None,
    regime_tag: str | None = None,
    payload: dict[str, Any] | None = None,
    pit_snapshot_ref: str = "",
    created_at_ns: int,
) -> tuple[ShadowPredictionRecord, bool]:
    """Append one immutable prediction bound to the run (insert-once)."""
    record = build_prediction(
        run_id=manifest.run_id,
        instrument_id=instrument_id,
        decision_time_ns=decision_time_ns,
        horizon_ns=horizon_ns,
        predicted_probability=predicted_probability,
        abstained=abstained,
        abstain_reason=abstain_reason,
        regime_tag=regime_tag,
        payload=payload,
        pit_snapshot_ref=pit_snapshot_ref,
        created_at_ns=created_at_ns,
    )
    return store.append_prediction(record)


def record_label(
    store: ShadowStore,
    prediction: ShadowPredictionRecord,
    **kwargs: Any,
) -> tuple[ShadowOutcomeLabel, bool]:
    """Delayed outcome labeling via ``labeling.attach_label`` (fail-closed)."""
    return attach_label(store, prediction, **kwargs)


def finalize_report(
    store: ShadowStore,
    manifest: ShadowRunManifest,
    *,
    bucket_count: int | None = None,
    overlays: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Post-hoc join report: observed metrics + strictly separate overlays."""
    pairs = join_pairs(
        store.iter_predictions(manifest.run_id),
        list(store.iter_labels(manifest.run_id)),
    )
    body: dict[str, Any] = {
        "schema": SHADOW_SCHEMA,
        "version": METRICS_VERSION,
        "run_id": manifest.run_id,
        "manifest_hash": manifest.manifest_hash,
        "observed": observed_metrics(
            pairs,
            bucket_count=CALIBRATION_BUCKETS if bucket_count is None else bucket_count,
        ),
        "by_regime": segment_by_regime(pairs),
        "walk_forward": walk_forward_evaluation(pairs, manifest),
    }
    overlay_body = [
        assumption_overlay(
            pairs,
            slippage_bps=overlay["slippage_bps"],
            cost_model_version=overlay["cost_model_version"],
        )
        for overlay in sorted(overlays or [], key=lambda item: item["cost_model_version"])
    ]
    # Disjoint namespace: hypothetical assumptions never touch "observed".
    body["overlay"] = overlay_body
    body["report_id"] = REPORT_ID_PREFIX + sha256_bytes(canonical_bytes(body))
    return body


__all__ = [
    "finalize_report",
    "open_shadow_run",
    "prediction_payload_from_decision_example",
    "record_label",
    "record_prediction",
]
