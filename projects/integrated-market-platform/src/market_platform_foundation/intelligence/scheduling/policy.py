"""Versioned deterministic BUILD 10 scheduler policy."""

from __future__ import annotations

from dataclasses import dataclass

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts import RoutingPriority

PRIORITY_RANK: dict[RoutingPriority, int] = {
    RoutingPriority.CRITICAL: 0,
    RoutingPriority.HIGH: 1,
    RoutingPriority.NORMAL: 2,
    RoutingPriority.LOW: 3,
}


def priority_rank(priority: RoutingPriority) -> int:
    return PRIORITY_RANK[priority]


@dataclass(frozen=True, slots=True)
class SchedulerPolicyV1:
    """Immutable scheduler semantics — identity excludes wall-clock timestamps."""

    policy_id: str = "inference-scheduler-policy"
    policy_version: str = "1"
    max_attempts: int = 1
    retry_delay_ns: int = 0
    enable_supersession: bool = True
    enable_residency_affinity: bool = True
    reject_if_cannot_complete_before_expiration: bool = True
    treat_deadline_missed_as_urgent: bool = True

    def __post_init__(self) -> None:
        if not self.policy_id or not self.policy_version:
            raise ValueError("SCHEDULER_POLICY_IDENTITY_INVALID")
        if self.max_attempts < 1:
            raise ValueError("SCHEDULER_MAX_ATTEMPTS_INVALID")
        if self.retry_delay_ns < 0:
            raise ValueError("SCHEDULER_RETRY_DELAY_INVALID")

    @property
    def identity(self) -> str:
        payload = {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "max_attempts": self.max_attempts,
            "retry_delay_ns": self.retry_delay_ns,
            "enable_supersession": self.enable_supersession,
            "enable_residency_affinity": self.enable_residency_affinity,
            "reject_if_cannot_complete_before_expiration": self.reject_if_cannot_complete_before_expiration,
            "treat_deadline_missed_as_urgent": self.treat_deadline_missed_as_urgent,
        }
        return f"SCHPOL-{sha256_bytes(canonical_bytes(payload))}"


__all__ = ["PRIORITY_RANK", "SchedulerPolicyV1", "priority_rank"]
