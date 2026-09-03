"""Map squeeze lifecycle demand onto scarce observational subscription slots."""

from __future__ import annotations

from .allocator import AllocationDecision, SubscriptionAllocator, SubscriptionRequest

STATE_PRIORITY = {
    "ACTIVE_SQUEEZE": 100,
    "LIVE_CONFIRMATION": 80,
    "IGNITION_WATCH": 50,
}


def squeeze_subscription_requests(
    candidates: list[dict[str, str]],
) -> list[SubscriptionRequest]:
    requests = []
    for row in candidates:
        state = str(row.get("state") or "IGNITION_WATCH")
        requests.append(
            SubscriptionRequest(
                instrument_id=str(row["instrument_id"]),
                capability="US_EQUITY_DEPTH",
                priority=STATE_PRIORITY.get(state, 10),
                lane="short_squeeze",
                thesis_id=str(row.get("thesis_id") or ""),
            )
        )
    return requests


def allocate_squeeze_hot_set(
    allocator: SubscriptionAllocator,
    candidates: list[dict[str, str]],
) -> AllocationDecision:
    return allocator.allocate(squeeze_subscription_requests(candidates))
