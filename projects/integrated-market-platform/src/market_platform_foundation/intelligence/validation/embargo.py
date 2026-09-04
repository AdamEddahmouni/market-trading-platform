"""Embargo verification for fold sequences (BUILD 19)."""

from __future__ import annotations

from ..training.types import TrainingDatasetManifestV1
from .errors import ValidationError
from .types import ValidationFoldSpec


def is_example_in_embargo_interval(
    decision_time_ns: int,
    *,
    embargo_start_ns: int,
    embargo_end_ns: int,
) -> bool:
    return embargo_start_ns <= decision_time_ns < embargo_end_ns


def verify_embargo_for_fold_sequence(
    datasets_by_fold: dict[str, TrainingDatasetManifestV1],
    folds: tuple[ValidationFoldSpec, ...],
    *,
    embargo_ns: int,
) -> tuple[bool, dict[str, tuple[str, ...]]]:
    if embargo_ns == 0:
        return True, {}

    violations: dict[str, list[str]] = {}
    for idx in range(1, len(folds)):
        prior_fold = folds[idx - 1]
        current_fold = folds[idx]
        embargo_start = prior_fold.validation_start_ns
        embargo_end = prior_fold.validation_end_ns + embargo_ns
        dataset = datasets_by_fold.get(current_fold.fold_id)
        if dataset is None:
            continue
        fold_violations: list[str] = []
        for ref in dataset.example_refs:
            if is_example_in_embargo_interval(
                ref.decision_time_ns,
                embargo_start_ns=embargo_start,
                embargo_end_ns=embargo_end,
            ):
                fold_violations.append(ref.snapshot_id)
        if fold_violations:
            violations[current_fold.fold_id] = fold_violations

    return len(violations) == 0, {k: tuple(sorted(v)) for k, v in violations.items()}


def assert_embargo_clean_or_raise(
    datasets_by_fold: dict[str, TrainingDatasetManifestV1],
    folds: tuple[ValidationFoldSpec, ...],
    *,
    embargo_ns: int,
) -> None:
    clean, violations = verify_embargo_for_fold_sequence(
        datasets_by_fold, folds, embargo_ns=embargo_ns
    )
    if not clean:
        raise ValidationError("EMBARGO_VIOLATION", details={"violations": violations})


__all__ = [
    "assert_embargo_clean_or_raise",
    "is_example_in_embargo_interval",
    "verify_embargo_for_fold_sequence",
]
