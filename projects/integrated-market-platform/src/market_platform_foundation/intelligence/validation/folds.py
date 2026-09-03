"""Walk-forward fold generation (BUILD 19)."""

from __future__ import annotations

from .errors import ValidationError
from .types import ValidationFoldSpec, WalkForwardMode, WalkForwardSpec


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
        elif spec.mode == WalkForwardMode.ROLLING:
            training_cutoff = validation_start - purge_ns
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
            )
        )
    return tuple(folds)


__all__ = ["generate_walk_forward_folds"]
