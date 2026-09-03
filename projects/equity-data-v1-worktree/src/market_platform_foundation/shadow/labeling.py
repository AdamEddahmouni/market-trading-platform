"""Delayed outcome labeling with explicit availability times (P6).

A label may only be attached to a prediction whose stored content still
matches its hash (tamper evidence), and only when the label's timing
respects causality:

- ``label_time_ns > decision_time_ns`` — the outcome resolved after the
  decision was made;
- ``available_time_ns > decision_time_ns + horizon_ns`` — the label becomes
  usable strictly after the full prediction horizon has elapsed, making it
  structurally impossible for a label to inform any decision inside its own
  window (leakage prevention);
- ``available_time_ns >= label_time_ns`` — nothing is available before it
  resolved.

All rules fail closed via ``LabelingViolation``.
"""

from __future__ import annotations

from .records import (
    ShadowIntegrityError,
    ShadowOutcomeLabel,
    ShadowPredictionRecord,
    build_label_from_parts,
    verify_prediction,
)
from .store import ShadowStore


class LabelingViolation(ValueError):
    """Raised when a proposed outcome label violates a causality rule."""


def check_label_causality(
    prediction: ShadowPredictionRecord,
    *,
    label_time_ns: int,
    available_time_ns: int,
) -> None:
    if label_time_ns <= prediction.decision_time_ns:
        raise LabelingViolation("LABEL_TIME_NOT_AFTER_DECISION")
    horizon_end = prediction.decision_time_ns + prediction.horizon_ns
    if available_time_ns <= horizon_end:
        raise LabelingViolation("LABEL_LEAKS_DECISION_WINDOW")
    if available_time_ns < label_time_ns:
        raise LabelingViolation("LABEL_AVAILABLE_BEFORE_RESOLVED")


def label_prediction(
    prediction: ShadowPredictionRecord,
    *,
    observed_positive: bool,
    label_time_ns: int,
    available_time_ns: int,
    label_source: str = "fixture",
    labeler_version: str = "platform/shadow/labeling/1.0.0",
    observed_return_bps: float | None = None,
) -> ShadowOutcomeLabel:
    """Build an outcome label after re-verifying the referenced prediction."""
    verify_prediction(prediction)
    check_label_causality(
        prediction,
        label_time_ns=label_time_ns,
        available_time_ns=available_time_ns,
    )
    return build_label_from_parts(
        run_id=prediction.run_id,
        prediction_id=prediction.prediction_id,
        observed_positive=observed_positive,
        label_time_ns=label_time_ns,
        available_time_ns=available_time_ns,
        label_source=label_source,
        labeler_version=labeler_version,
        observed_return_bps=observed_return_bps,
    )


def attach_label(
    store: ShadowStore,
    prediction: ShadowPredictionRecord,
    *,
    observed_positive: bool,
    label_time_ns: int,
    available_time_ns: int,
    label_source: str = "fixture",
    labeler_version: str = "platform/shadow/labeling/1.0.0",
    observed_return_bps: float | None = None,
) -> tuple[ShadowOutcomeLabel, bool]:
    """Label a prediction and insert it once into the store.

    The prediction is loaded from the store by id when present so that the
    hash verification below runs against **stored** bytes; a mutated record
    raises ``ShadowIntegrityError("PREDICTION_HASH_MISMATCH")`` before any
    label is written.
    """
    stored = store.get_prediction(prediction.prediction_id)
    referent = stored if stored is not None else prediction
    label = label_prediction(
        referent,
        observed_positive=observed_positive,
        label_time_ns=label_time_ns,
        available_time_ns=available_time_ns,
        label_source=label_source,
        labeler_version=labeler_version,
        observed_return_bps=observed_return_bps,
    )
    return store.append_label(label)


__all__ = [
    "LabelingViolation",
    "attach_label",
    "check_label_causality",
    "label_prediction",
]
