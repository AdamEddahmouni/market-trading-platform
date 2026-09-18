"""Chronological research split utility (HISTORICAL_DEVELOPMENT only)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .types import (
    ChronologicalSplitPolicy,
    HistoricalResearchSplitAssignment,
    HistoricalResearchSplitName,
)


def chronological_split_boundaries(
    ordered_times_ns: Sequence[int],
    policy: ChronologicalSplitPolicy,
) -> dict[str, int | None]:
    """Return inclusive index boundaries for train / dev-validate / research-test."""

    unique = sorted(set(int(t) for t in ordered_times_ns))
    n = len(unique)
    if n == 0:
        return {
            "train_end_index": None,
            "development_validate_end_index": None,
            "research_test_start_index": None,
            "timeline_count": 0,
        }
    train_end = max(0, int(n * policy.train_fraction) - 1)
    dev_end = max(
        train_end,
        int(n * (policy.train_fraction + policy.development_validate_fraction)) - 1,
    )
    if n == 1:
        train_end = 0
        dev_end = 0
    return {
        "train_end_index": train_end,
        "development_validate_end_index": dev_end,
        "research_test_start_index": min(dev_end + 1, n - 1) if dev_end < n - 1 else n,
        "timeline_count": n,
        "ordered_times_ns": unique,
    }


def assign_chronological_splits(
    ordered_times_ns: Sequence[int],
    policy: ChronologicalSplitPolicy,
) -> tuple[HistoricalResearchSplitAssignment, ...]:
    bounds = chronological_split_boundaries(ordered_times_ns, policy)
    unique: list[int] = list(bounds.get("ordered_times_ns") or [])
    if not unique:
        return ()
    train_end = int(bounds["train_end_index"])
    dev_end = int(bounds["development_validate_end_index"])
    out: list[HistoricalResearchSplitAssignment] = []
    for index, decision_time_ns in enumerate(unique):
        if index <= train_end:
            split = HistoricalResearchSplitName.HISTORICAL_TRAIN
        elif index <= dev_end:
            split = HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE
        else:
            split = HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST
        out.append(HistoricalResearchSplitAssignment(decision_time_ns=decision_time_ns, split=split))
    return tuple(out)


def splits_overlap(assignments: Sequence[HistoricalResearchSplitAssignment]) -> bool:
    seen: dict[int, HistoricalResearchSplitName] = {}
    for row in assignments:
        prior = seen.get(row.decision_time_ns)
        if prior is not None and prior != row.split:
            return True
        seen[row.decision_time_ns] = row.split
    return False


def assert_chronological_order(assignments: Sequence[HistoricalResearchSplitAssignment]) -> None:
    times = [row.decision_time_ns for row in assignments]
    if times != sorted(times):
        raise ValueError("SPLIT_TIMELINE_NOT_CHRONOLOGICAL")


def decision_times_for_split(
    assignments: Sequence[HistoricalResearchSplitAssignment],
    split: HistoricalResearchSplitName,
) -> frozenset[int]:
    return frozenset(row.decision_time_ns for row in assignments if row.split == split)


def filter_events_to_decision_times(
    events: Sequence[Mapping[str, Any]],
    decision_times_ns: frozenset[int],
) -> list[dict[str, Any]]:
    """Keep only replay events whose available_time is in the allowed decision-time set."""

    if not decision_times_ns:
        return []
    filtered = [
        dict(row)
        for row in events
        if int(row.get("available_time", 0)) in decision_times_ns
    ]
    filtered.sort(key=lambda row: (int(row["available_time"]), str(row.get("normalized_event_id", ""))))
    return filtered


__all__ = [
    "assign_chronological_splits",
    "assert_chronological_order",
    "chronological_split_boundaries",
    "decision_times_for_split",
    "filter_events_to_decision_times",
    "splits_overlap",
]
