"""Immutable shadow prediction/outcome records with content-addressed identity.

Platformization P6 — shadow observation is NOT execution. Every record is
immutable: its id and integrity hash are SHA-256 over the canonical JSON body
(repo-wide ``canonical_bytes``/``sha256_bytes`` convention), so any
retrospective mutation of a stored record is detectable
(``verify_prediction``). All timestamps are injected parameters; no wall clock
participates in computed values (determinism contract, see the P6 design spec
§2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

SHADOW_SCHEMA = "1.0.0"
SHADOW_RECORDS_VERSION = "platform/shadow/records/1.0.0"

PREDICTION_ID_PREFIX = "SHPRD-"
LABEL_ID_PREFIX = "SHLBL-"
RUN_ID_PREFIX = "SHRUN-"

ABSTAIN_REASONS: tuple[str, ...] = (
    "NO_SIGNAL",
    "INSUFFICIENT_DATA",
    "QUALITY_GATE_FAILED",
)


class ShadowIntegrityError(ValueError):
    """Raised when a stored record's content no longer matches its hash."""


def _content_id(prefix: str, body: dict[str, Any]) -> str:
    return prefix + sha256_bytes(canonical_bytes(body))


# ---------------------------------------------------------------------------
# Run manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShadowRunManifest:
    """Identity + configuration of one shadow run (observation only)."""

    run_id: str
    strategy_version: str
    prediction_version: str
    universe: tuple[str, ...]
    data_window_refs: tuple[dict[str, str], ...]
    train_window_end_ns: int
    eval_window_start_ns: int
    eval_window_end_ns: int
    created_at_ns: int
    config: dict[str, Any] = field(default_factory=dict)
    manifest_hash: str = ""


def manifest_body(
    *,
    strategy_version: str,
    prediction_version: str,
    universe: tuple[str, ...],
    data_window_refs: tuple[dict[str, str], ...],
    train_window_end_ns: int,
    eval_window_start_ns: int,
    eval_window_end_ns: int,
    created_at_ns: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": SHADOW_SCHEMA,
        "version": SHADOW_RECORDS_VERSION,
        "strategy_version": strategy_version,
        "prediction_version": prediction_version,
        "universe": list(universe),
        "data_window_refs": list(data_window_refs),
        "train_window_end_ns": train_window_end_ns,
        "eval_window_start_ns": eval_window_start_ns,
        "eval_window_end_ns": eval_window_end_ns,
        "created_at_ns": created_at_ns,
        "config": config,
    }


def build_run_manifest(
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
) -> ShadowRunManifest:
    if not strategy_version or not prediction_version:
        raise ValueError("MANIFEST_VERSIONS_REQUIRED")
    if not universe:
        raise ValueError("MANIFEST_UNIVERSE_REQUIRED")
    if not (train_window_end_ns <= eval_window_start_ns <= eval_window_end_ns):
        # Non-peeking window contract: eval start must not precede train end.
        raise ValueError("WALK_FORWARD_WINDOW_ORDER_INVALID")
    body = manifest_body(
        strategy_version=strategy_version,
        prediction_version=prediction_version,
        universe=universe,
        data_window_refs=data_window_refs,
        train_window_end_ns=train_window_end_ns,
        eval_window_start_ns=eval_window_start_ns,
        eval_window_end_ns=eval_window_end_ns,
        created_at_ns=created_at_ns,
        config=dict(config or {}),
    )
    return ShadowRunManifest(
        run_id=_content_id(RUN_ID_PREFIX, body),
        manifest_hash=sha256_bytes(canonical_bytes(body)),
        **{
            key: value
            for key, value in body.items()
            if key not in ("schema", "version")
        },
    )


def verify_manifest(manifest: ShadowRunManifest) -> None:
    body = manifest_body(
        strategy_version=manifest.strategy_version,
        prediction_version=manifest.prediction_version,
        universe=manifest.universe,
        data_window_refs=manifest.data_window_refs,
        train_window_end_ns=manifest.train_window_end_ns,
        eval_window_start_ns=manifest.eval_window_start_ns,
        eval_window_end_ns=manifest.eval_window_end_ns,
        created_at_ns=manifest.created_at_ns,
        config=manifest.config,
    )
    expected_id = _content_id(RUN_ID_PREFIX, body)
    expected_hash = sha256_bytes(canonical_bytes(body))
    if manifest.run_id != expected_id or manifest.manifest_hash != expected_hash:
        raise ShadowIntegrityError("MANIFEST_HASH_MISMATCH")


# ---------------------------------------------------------------------------
# Prediction records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShadowPredictionRecord:
    """Immutable point-in-time assertion written before outcome observation."""

    prediction_id: str
    run_id: str
    instrument_id: str
    decision_time_ns: int
    horizon_ns: int
    predicted_probability: float | None
    predicted_positive: bool | None
    abstained: bool
    abstain_reason: str | None
    regime_tag: str | None
    payload: dict[str, Any]
    pit_snapshot_ref: str
    created_at_ns: int
    record_hash: str


def prediction_body(record_like: dict[str, Any]) -> dict[str, Any]:
    """Canonical identity body of a prediction (everything but id/hash)."""
    return {
        "run_id": record_like["run_id"],
        "instrument_id": record_like["instrument_id"],
        "decision_time_ns": int(record_like["decision_time_ns"]),
        "horizon_ns": int(record_like["horizon_ns"]),
        "predicted_probability": record_like["predicted_probability"],
        "predicted_positive": record_like["predicted_positive"],
        "abstained": bool(record_like["abstained"]),
        "abstain_reason": record_like["abstain_reason"],
        "regime_tag": record_like["regime_tag"],
        "payload": record_like["payload"],
        "pit_snapshot_ref": record_like["pit_snapshot_ref"],
        "created_at_ns": int(record_like["created_at_ns"]),
    }


def compute_prediction_hash(record_like: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(prediction_body(record_like)))


def build_prediction(
    *,
    run_id: str,
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
) -> ShadowPredictionRecord:
    if horizon_ns <= 0:
        raise ValueError("HORIZON_MUST_BE_POSITIVE")
    if abstained:
        if predicted_probability is not None:
            raise ValueError("ABSTAINED_RECORD_CARRIES_PROBABILITY")
        if not abstain_reason:
            raise ValueError("ABSTENTION_REASON_REQUIRED")
        predicted_positive = None
    else:
        if predicted_probability is None or not 0.0 <= predicted_probability <= 1.0:
            raise ValueError("PREDICTED_PROBABILITY_OUT_OF_RANGE")
        if abstain_reason:
            raise ValueError("NON_ABSTAINED_RECORD_HAS_ABSTAIN_REASON")
        predicted_positive = predicted_probability >= 0.5
    like = {
        "run_id": run_id,
        "instrument_id": instrument_id,
        "decision_time_ns": decision_time_ns,
        "horizon_ns": horizon_ns,
        "predicted_probability": predicted_probability,
        "predicted_positive": predicted_positive,
        "abstained": abstained,
        "abstain_reason": abstain_reason,
        "regime_tag": regime_tag,
        "payload": dict(payload or {}),
        "pit_snapshot_ref": pit_snapshot_ref,
        "created_at_ns": created_at_ns,
    }
    body = prediction_body(like)
    return ShadowPredictionRecord(
        prediction_id=_content_id(PREDICTION_ID_PREFIX, body),
        record_hash=compute_prediction_hash(like),
        **body,
    )


def verify_prediction(record: ShadowPredictionRecord) -> None:
    like = {
        "run_id": record.run_id,
        "instrument_id": record.instrument_id,
        "decision_time_ns": record.decision_time_ns,
        "horizon_ns": record.horizon_ns,
        "predicted_probability": record.predicted_probability,
        "predicted_positive": record.predicted_positive,
        "abstained": record.abstained,
        "abstain_reason": record.abstain_reason,
        "regime_tag": record.regime_tag,
        "payload": record.payload,
        "pit_snapshot_ref": record.pit_snapshot_ref,
        "created_at_ns": record.created_at_ns,
    }
    expected_id = _content_id(PREDICTION_ID_PREFIX, prediction_body(like))
    expected_hash = compute_prediction_hash(like)
    if record.prediction_id != expected_id:
        raise ShadowIntegrityError("PREDICTION_ID_MISMATCH")
    if record.record_hash != expected_hash:
        raise ShadowIntegrityError("PREDICTION_HASH_MISMATCH")


# ---------------------------------------------------------------------------
# Outcome labels
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShadowOutcomeLabel:
    """Immutable delayed annotation joined by (run_id, prediction_id)."""

    label_id: str
    run_id: str
    prediction_id: str
    observed_positive: bool
    observed_return_bps: float | None
    label_time_ns: int
    available_time_ns: int
    label_source: str
    labeler_version: str
    label_hash: str


def label_body(record_like: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": record_like["run_id"],
        "prediction_id": record_like["prediction_id"],
        "observed_positive": bool(record_like["observed_positive"]),
        "observed_return_bps": record_like["observed_return_bps"],
        "label_time_ns": int(record_like["label_time_ns"]),
        "available_time_ns": int(record_like["available_time_ns"]),
        "label_source": record_like["label_source"],
        "labeler_version": record_like["labeler_version"],
    }


def compute_label_hash(record_like: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(label_body(record_like)))


def build_label_from_parts(
    *,
    run_id: str,
    prediction_id: str,
    observed_positive: bool,
    label_time_ns: int,
    available_time_ns: int,
    label_source: str = "fixture",
    labeler_version: str = "platform/shadow/labeling/1.0.0",
    observed_return_bps: float | None = None,
) -> ShadowOutcomeLabel:
    like = {
        "run_id": run_id,
        "prediction_id": prediction_id,
        "observed_positive": observed_positive,
        "observed_return_bps": observed_return_bps,
        "label_time_ns": label_time_ns,
        "available_time_ns": available_time_ns,
        "label_source": label_source,
        "labeler_version": labeler_version,
    }
    body = label_body(like)
    return ShadowOutcomeLabel(
        label_id=_content_id(LABEL_ID_PREFIX, body),
        label_hash=compute_label_hash(like),
        **body,
    )


def verify_label(label: ShadowOutcomeLabel) -> None:
    like = {
        "run_id": label.run_id,
        "prediction_id": label.prediction_id,
        "observed_positive": label.observed_positive,
        "observed_return_bps": label.observed_return_bps,
        "label_time_ns": label.label_time_ns,
        "available_time_ns": label.available_time_ns,
        "label_source": label.label_source,
        "labeler_version": label.labeler_version,
    }
    expected_id = _content_id(LABEL_ID_PREFIX, label_body(like))
    expected_hash = compute_label_hash(like)
    if label.label_id != expected_id or label.label_hash != expected_hash:
        raise ShadowIntegrityError("LABEL_HASH_MISMATCH")


__all__ = [
    "ABSTAIN_REASONS",
    "LABEL_ID_PREFIX",
    "PREDICTION_ID_PREFIX",
    "RUN_ID_PREFIX",
    "SHADOW_RECORDS_VERSION",
    "SHADOW_SCHEMA",
    "ShadowIntegrityError",
    "ShadowOutcomeLabel",
    "ShadowPredictionRecord",
    "ShadowRunManifest",
    "build_label_from_parts",
    "build_prediction",
    "build_run_manifest",
    "compute_label_hash",
    "compute_prediction_hash",
    "label_body",
    "manifest_body",
    "prediction_body",
    "verify_label",
    "verify_manifest",
    "verify_prediction",
]
