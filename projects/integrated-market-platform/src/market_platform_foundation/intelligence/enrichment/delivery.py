"""Operational delivery state for async enrichment (not opportunity lifecycle)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EnrichmentDeliveryState(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    DISPATCHED = "DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


TERMINAL_DELIVERY_STATES: frozenset[EnrichmentDeliveryState] = frozenset(
    {
        EnrichmentDeliveryState.ACKNOWLEDGED,
        EnrichmentDeliveryState.EXPIRED,
        EnrichmentDeliveryState.DEAD_LETTER,
    }
)

IN_FLIGHT_DELIVERY_STATES: frozenset[EnrichmentDeliveryState] = frozenset(
    {
        EnrichmentDeliveryState.PENDING,
        EnrichmentDeliveryState.CLAIMED,
        EnrichmentDeliveryState.DISPATCHED,
        EnrichmentDeliveryState.FAILED,
    }
)


@dataclass(frozen=True, slots=True)
class EnrichmentRetryPolicy:
    max_attempts: int = 5
    base_backoff_ns: int = 1_000_000_000
    max_backoff_ns: int = 300_000_000_000
    claim_lease_ns: int = 60_000_000_000
    dispatch_timeout_sec: float | None = None


DEFAULT_RETRY_POLICY = EnrichmentRetryPolicy()


def compute_next_retry_at_ns(*, retry_count: int, now_ns: int, policy: EnrichmentRetryPolicy) -> int:
    exponent = max(0, retry_count - 1)
    delay = min(policy.base_backoff_ns * (2**exponent), policy.max_backoff_ns)
    return now_ns + delay


__all__ = [
    "DEFAULT_RETRY_POLICY",
    "IN_FLIGHT_DELIVERY_STATES",
    "TERMINAL_DELIVERY_STATES",
    "EnrichmentDeliveryState",
    "EnrichmentRetryPolicy",
    "compute_next_retry_at_ns",
]
