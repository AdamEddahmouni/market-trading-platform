"""Walk-forward fold definitions with PIT boundaries."""

from __future__ import annotations

from typing import Any


def build_walk_forward_folds(
    observation_times: list[int],
    *,
    min_train: int = 2,
    test_size: int = 1,
) -> list[dict[str, int]]:
    times = sorted(set(observation_times))
    folds: list[dict[str, int]] = []
    if len(times) < min_train + test_size:
        return folds
    start = min_train
    while start + test_size <= len(times):
        train_times = times[:start]
        test_times = times[start : start + test_size]
        folds.append(
            {
                "fold_id": len(folds),
                "test_end_cutoff": test_times[-1],
                "test_start_cutoff": test_times[0],
                "train_end_cutoff": train_times[-1],
                "train_start_cutoff": train_times[0],
            }
        )
        start += test_size
    return folds


def verify_fold_pit(
    folds: list[dict[str, int]],
    rows: list[dict[str, object]],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    for fold in folds:
        train_end = int(fold["train_end_cutoff"])
        test_start = int(fold["test_start_cutoff"])
        if train_end >= test_start:
            reasons.append("PIT_WF_TRAIN_TEST_OVERLAP")
        for row in rows:
            obs_time = int(row.get("observation_time", row.get("available_time", 0)))
            cutoff = int(row.get("prediction_cutoff", obs_time))
            if test_start <= obs_time <= int(fold["test_end_cutoff"]) and cutoff < train_end:
                reasons.append("PIT_WF_TEST_USES_TRAIN_CUTOFF")
    status = "PASS" if not reasons else "FAIL"
    return status, sorted(set(reasons))
