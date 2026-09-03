"""Session-level continuity gap classification for EVIDENCE-01B."""

from __future__ import annotations

from dataclasses import dataclass

from ..evidence01.continuity import qualifying_gap_ns
from .types import ContinuityGapCategory


@dataclass(frozen=True)
class ContinuityGapRecordV1:
    gap_ns: int
    qualifying_gap_ns: int
    category: ContinuityGapCategory
    start_ns: int
    end_ns: int
    description: str


def classify_gap(
    prev_ns: int,
    next_ns: int,
    *,
    provider_disconnected: bool = False,
    runtime_down: bool = False,
) -> ContinuityGapRecordV1:
    raw_gap = next_ns - prev_ns
    qualifying = qualifying_gap_ns(prev_ns, next_ns)
    if qualifying == 0 and raw_gap > 0:
        category = ContinuityGapCategory.EXPECTED_MARKET_CLOSURE
        description = "gap falls entirely outside expected observation windows"
    elif raw_gap > qualifying and qualifying == 0:
        category = ContinuityGapCategory.EXPECTED_MARKET_CLOSURE
        description = "gap spans expected market closure"
    elif raw_gap > 24 * 60 * 60 * 1_000_000_000 and qualifying < 24 * 60 * 60 * 1_000_000_000:
        category = ContinuityGapCategory.EXPECTED_MARKET_CLOSURE
        description = "raw gap spans closure but qualifying gap within policy"
    elif provider_disconnected and qualifying > 0:
        category = ContinuityGapCategory.PROVIDER_DISCONNECT
        description = "provider disconnected during expected observation window"
    elif runtime_down and qualifying > 0:
        category = ContinuityGapCategory.RUNTIME_DOWN
        description = "runtime unavailable during expected observation window"
    elif qualifying > 0:
        category = ContinuityGapCategory.UNKNOWN
        description = "unexplained gap during expected observation window"
    else:
        category = ContinuityGapCategory.PLANNED_SESSION_BOUNDARY
        description = "within expected session boundary"
    return ContinuityGapRecordV1(
        gap_ns=raw_gap,
        qualifying_gap_ns=qualifying,
        category=category,
        start_ns=prev_ns,
        end_ns=next_ns,
        description=description,
    )


def maximum_qualifying_session_gap(
    decision_times_ns: list[int],
    *,
    provider_disconnected: bool = False,
) -> int:
    if len(decision_times_ns) < 2:
        return 0
    sorted_times = sorted(decision_times_ns)
    max_gap = 0
    for prev, nxt in zip(sorted_times, sorted_times[1:]):
        record = classify_gap(prev, nxt, provider_disconnected=provider_disconnected)
        max_gap = max(max_gap, record.qualifying_gap_ns)
    return max_gap
