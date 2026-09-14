"""Distribution summaries with observability-standard p50 alias."""

from __future__ import annotations

from typing import Any, Sequence

from market_platform_foundation.rt01.stats import distribution_stats


def latency_summary(samples_ns: Sequence[int], *, missing_pair_count: int = 0) -> dict[str, Any]:
    stats = distribution_stats(samples_ns)
    base = stats.to_dict()
    base["p50_ns"] = base.get("median_ns")
    base["missing_pair_count"] = missing_pair_count
    return base


def empty_presence() -> dict[str, int]:
    return {"present_count": 0, "missing_count": 0}


def merge_presence(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {
        "present_count": left.get("present_count", 0) + right.get("present_count", 0),
        "missing_count": left.get("missing_count", 0) + right.get("missing_count", 0),
    }


__all__ = ["empty_presence", "latency_summary", "merge_presence"]
