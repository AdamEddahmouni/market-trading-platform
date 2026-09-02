"""RT-01 baseline statistics and aggregation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class DistributionStats:
    count: int
    min_ns: int | None
    median_ns: int | None
    mean_ns: float | None
    p90_ns: int | None
    p95_ns: int | None
    p99_ns: int | None
    max_ns: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "min_ns": self.min_ns,
            "median_ns": self.median_ns,
            "mean_ns": self.mean_ns,
            "p90_ns": self.p90_ns,
            "p95_ns": self.p95_ns,
            "p99_ns": self.p99_ns,
            "max_ns": self.max_ns,
        }


def percentile(sorted_values: Sequence[int], p: float) -> int | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * p
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return sorted_values[low]
    weight = rank - low
    return int(sorted_values[low] * (1 - weight) + sorted_values[high] * weight)


def distribution_stats(samples_ns: Sequence[int]) -> DistributionStats:
    if not samples_ns:
        return DistributionStats(0, None, None, None, None, None, None, None)
    ordered = sorted(samples_ns)
    count = len(ordered)
    mean = sum(ordered) / count
    return DistributionStats(
        count=count,
        min_ns=ordered[0],
        median_ns=percentile(ordered, 0.5),
        mean_ns=mean,
        p90_ns=percentile(ordered, 0.9) if count >= 2 else ordered[0],
        p95_ns=percentile(ordered, 0.95) if count >= 2 else ordered[0],
        p99_ns=percentile(ordered, 0.99) if count >= 2 else ordered[0],
        max_ns=ordered[-1],
    )


__all__ = ["DistributionStats", "distribution_stats", "percentile"]
