"""Walk-forward fold generation (BUILD 19)."""

from __future__ import annotations

from .errors import ValidationError
from .types import ValidationExample, ValidationFoldSpec, WalkForwardMode, WalkForwardSpec


def generate_walk_forward_folds(
    spec: WalkForwardSpec,
    *,
    purge_ns: int = 0,
) -> tuple[ValidationFoldSpec, ...]:
    boundaries = spec.fold_boundaries_ns
    if len(boundaries) < 2:
        raise ValidationError("FOLD_BOUNDARIES_INSUFFICIENT")

    for idx in range(len(boundaries) - 1):
        if boundaries[idx] >= boundaries[idx + 1]:
            raise ValidationError(
                "FOLD_BOUNDARIES_NOT_CHRONOLOGICAL",
                details={"index": idx, "start": boundaries[idx], "end": boundaries[idx + 1]},
            )

    folds: list[ValidationFoldSpec] = []
    fold_candidates = spec.fold_candidate_ids or (None,) * (len(boundaries) - 1)
    for idx in range(len(boundaries) - 1):
        validation_start = boundaries[idx]
        validation_end = boundaries[idx + 1]
        if idx > 0 and validation_start < boundaries[idx - 1]:
            raise ValidationError("OVERLAPPING_VALIDATION_WINDOWS", details={"fold_index": idx})

        if spec.mode == WalkForwardMode.EXPANDING:
            training_cutoff = validation_start - purge_ns
            training_start: int | None = None
        elif spec.mode == WalkForwardMode.ROLLING:
            if spec.rolling_window_ns is None:
                raise ValidationError("WALK_FORWARD_ROLLING_WINDOW_REQUIRED")
            if spec.rolling_window_ns <= 0:
                raise ValidationError(
                    "WALK_FORWARD_ROLLING_WINDOW_INVALID",
                    details={"rolling_window_ns": spec.rolling_window_ns},
                )
            training_cutoff = validation_start - purge_ns
            training_start = training_cutoff - spec.rolling_window_ns
        else:
            raise ValidationError("WALK_FORWARD_MODE_UNSUPPORTED", details={"mode": spec.mode})

        candidate_id = fold_candidates[idx] if idx < len(fold_candidates) else None
        folds.append(
            ValidationFoldSpec(
                fold_id=f"fold-{idx + 1}",
                validation_start_ns=validation_start,
                validation_end_ns=validation_end,
                training_cutoff_ns=training_cutoff,
                candidate_id=candidate_id,
                training_start_ns=training_start,
            )
        )
    return tuple(folds)


def fold_example_temporal_violation(
    example: ValidationExample,
    fold: ValidationFoldSpec,
) -> str | None:
    """Return a leak code when a scored fold example violates the temporal contract.

    Scoring uses labels that realize after the decision. A label available at or
    before decision time is fail-closed as ``FUTURE_LABEL_ACCESS``. Fold examples
    must also sit in the half-open validation window and must not be training-period
    rows scored as out-of-sample.
    """
    if example.label_available_time_ns <= example.decision_time_ns:
        return "FUTURE_LABEL_ACCESS"
    if not (fold.validation_start_ns <= example.decision_time_ns < fold.validation_end_ns):
        return "VALIDATION_WINDOW_MISMATCH"
    if example.decision_time_ns < fold.training_cutoff_ns:
        return "TRAINING_PERIOD_SCORED_AS_VALIDATION"
    if (
        fold.training_start_ns is not None
        and fold.training_start_ns <= example.decision_time_ns < fold.training_cutoff_ns
    ):
        return "TRAINING_PERIOD_SCORED_AS_VALIDATION"
    return None


__all__ = ["fold_example_temporal_violation", "generate_walk_forward_folds"]
