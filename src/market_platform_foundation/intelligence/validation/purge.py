"""Purge verification against training datasets (BUILD 19)."""

from __future__ import annotations

from ..training.types import TrainingDatasetManifestV1, TrainingExampleRef
from .errors import ValidationError
from .types import ValidationFoldSpec


def label_available_time_ns_for_ref(ref: TrainingExampleRef, metadata: dict | None = None) -> int:
    if metadata and "label_available_time_ns" in metadata:
        return int(metadata["label_available_time_ns"])
    # Conservative fallback: decision + horizon from metadata or decision itself
    if metadata and "horizon_ns" in metadata:
        return ref.decision_time_ns + int(metadata["horizon_ns"])
    return ref.decision_time_ns


def is_training_example_purge_clean(
    *,
    label_available_time_ns: int,
    validation_start_ns: int,
    purge_ns: int,
) -> bool:
    """Require label information to be fully available before validation starts minus purge."""
    boundary = validation_start_ns - purge_ns
    return label_available_time_ns < boundary


def verify_training_purge_for_fold(
    dataset: TrainingDatasetManifestV1,
    fold: ValidationFoldSpec,
    *,
    purge_ns: int,
    label_times: dict[str, int] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    label_times = label_times or {}
    violations: list[str] = []
    metadata = dict(dataset.metadata)
    metadata.setdefault("horizon_ns", dataset.horizon_ns)

    for ref in dataset.example_refs:
        key = ref.snapshot_id
        label_time = label_times.get(key)
        if label_time is None:
            label_time = label_available_time_ns_for_ref(ref, metadata)
        if not is_training_example_purge_clean(
            label_available_time_ns=label_time,
            validation_start_ns=fold.validation_start_ns,
            purge_ns=purge_ns,
        ):
            violations.append(key)

    return len(violations) == 0, tuple(sorted(violations))


def assert_purge_clean_or_raise(
    dataset: TrainingDatasetManifestV1,
    fold: ValidationFoldSpec,
    *,
    purge_ns: int,
    label_times: dict[str, int] | None = None,
) -> None:
    clean, violations = verify_training_purge_for_fold(
        dataset, fold, purge_ns=purge_ns, label_times=label_times
    )
    if not clean:
        raise ValidationError(
            "INVALID_TRAINING_VALIDATION_OVERLAP",
            details={"fold_id": fold.fold_id, "violations": violations},
        )


__all__ = [
    "assert_purge_clean_or_raise",
    "is_training_example_purge_clean",
    "label_available_time_ns_for_ref",
    "verify_training_purge_for_fold",
]
