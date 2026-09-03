"""Runtime models, state machine, and queue ordering for BUILD 10."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts import InferenceJobV1, RoutingPriority
from .policy import priority_rank


class SchedulerJobState(StrEnum):
    QUEUED = "QUEUED"
    BLOCKED_RESOURCE = "BLOCKED_RESOURCE"
    READY = "READY"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


TERMINAL_STATES = frozenset(
    {
        SchedulerJobState.COMPLETED,
        SchedulerJobState.FAILED,
        SchedulerJobState.CANCELLED,
        SchedulerJobState.EXPIRED,
        SchedulerJobState.SUPERSEDED,
        SchedulerJobState.REJECTED,
    }
)

ALLOWED_TRANSITIONS: dict[SchedulerJobState, frozenset[SchedulerJobState]] = {
    SchedulerJobState.QUEUED: frozenset(
        {
            SchedulerJobState.BLOCKED_RESOURCE,
            SchedulerJobState.READY,
            SchedulerJobState.EXPIRED,
            SchedulerJobState.SUPERSEDED,
            SchedulerJobState.CANCELLED,
            SchedulerJobState.REJECTED,
        }
    ),
    SchedulerJobState.BLOCKED_RESOURCE: frozenset(
        {
            SchedulerJobState.READY,
            SchedulerJobState.EXPIRED,
            SchedulerJobState.SUPERSEDED,
            SchedulerJobState.CANCELLED,
        }
    ),
    SchedulerJobState.READY: frozenset(
        {
            SchedulerJobState.DISPATCHED,
            SchedulerJobState.BLOCKED_RESOURCE,
            SchedulerJobState.EXPIRED,
            SchedulerJobState.SUPERSEDED,
            SchedulerJobState.CANCELLED,
        }
    ),
    SchedulerJobState.DISPATCHED: frozenset(
        {
            SchedulerJobState.RUNNING,
            SchedulerJobState.QUEUED,
            SchedulerJobState.FAILED,
            SchedulerJobState.CANCELLED,
        }
    ),
    SchedulerJobState.RUNNING: frozenset(
        {
            SchedulerJobState.COMPLETED,
            SchedulerJobState.FAILED,
        }
    ),
    SchedulerJobState.COMPLETED: frozenset(),
    SchedulerJobState.FAILED: frozenset(),
    SchedulerJobState.CANCELLED: frozenset(),
    SchedulerJobState.EXPIRED: frozenset(),
    SchedulerJobState.SUPERSEDED: frozenset(),
    SchedulerJobState.REJECTED: frozenset(),
}


class CancellationReason(StrEnum):
    MANUAL = "MANUAL"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    ROUTE_INVALIDATED = "ROUTE_INVALIDATED"
    RESOURCE_POLICY = "RESOURCE_POLICY"


class ResidencyAction(StrEnum):
    KEEP_CURRENT = "KEEP_CURRENT"
    LOAD_RESIDENCY = "LOAD_RESIDENCY"
    SWITCH_ADAPTER = "SWITCH_ADAPTER"
    NO_SPECIAL_ACTION = "NO_SPECIAL_ACTION"


class AdapterAction(StrEnum):
    KEEP_CURRENT = "KEEP_CURRENT"
    SWITCH_ADAPTER = "SWITCH_ADAPTER"
    NO_SPECIAL_ACTION = "NO_SPECIAL_ACTION"


@dataclass(frozen=True, slots=True)
class ResidencyPlan:
    residency_action: ResidencyAction
    target_residency_key: str | None
    adapter_action: AdapterAction
    target_adapter_key: str | None


@dataclass
class SchedulerJobRuntime:
    """Mutable lifecycle record separate from immutable InferenceJobV1."""

    job: InferenceJobV1
    state: SchedulerJobState
    submission_sequence: int
    attempt_count: int = 0
    next_eligible_time_ns: int = 0
    deadline_missed: bool = False
    diagnostics: tuple[str, ...] = ()
    cancellation_reason: CancellationReason | None = None
    dispatch_id: str | None = None
    batch_id: str | None = None
    residency_plan: ResidencyPlan | None = None
    reserved_cpu_slots: int = 0
    reserved_gpu_slots: int = 0
    reserved_vram_bytes: int = 0


@dataclass(frozen=True, slots=True)
class QueueOrderingKey:
    priority_rank: int
    deadline_time_ns: int
    expires_at_ns: int
    submission_sequence: int
    job_id: str
    residency_affinity_rank: int = 1

    @classmethod
    def from_runtime(
        cls,
        runtime: SchedulerJobRuntime,
        *,
        residency_affinity_rank: int = 1,
    ) -> QueueOrderingKey:
        return cls(
            priority_rank=priority_rank(runtime.job.priority),
            deadline_time_ns=runtime.job.deadline_time_ns,
            expires_at_ns=runtime.job.expires_at_ns,
            submission_sequence=runtime.submission_sequence,
            job_id=runtime.job.job_id,
            residency_affinity_rank=residency_affinity_rank,
        )


def queue_ordering_tuple(key: QueueOrderingKey) -> tuple[int, int, int, int, int, str]:
    return (
        key.priority_rank,
        key.deadline_time_ns,
        key.expires_at_ns,
        key.submission_sequence,
        key.residency_affinity_rank,
        key.job_id,
    )


def validate_transition(current: SchedulerJobState, target: SchedulerJobState) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ValueError(f"INVALID_STATE_TRANSITION:{current.value}->{target.value}")


@dataclass(frozen=True, slots=True)
class SchedulerStateSummary:
    queued: int = 0
    blocked: int = 0
    ready: int = 0
    dispatched: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    expired: int = 0
    superseded: int = 0
    rejected: int = 0


@dataclass(frozen=True, slots=True)
class SubmitRouteResult:
    job: InferenceJobV1 | None
    state: SchedulerJobState | None
    outcome: str
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SchedulerPassResult:
    dispatch_batches: tuple[Any, ...] = ()
    expired_job_ids: tuple[str, ...] = ()
    cancelled_job_ids: tuple[str, ...] = ()
    superseded_job_ids: tuple[str, ...] = ()
    blocked_job_ids: tuple[str, ...] = ()
    rejected_job_ids: tuple[str, ...] = ()
    deadline_missed_job_ids: tuple[str, ...] = ()
    state_summary: SchedulerStateSummary = field(default_factory=SchedulerStateSummary)
    diagnostics: tuple[str, ...] = ()


__all__ = [
    "ALLOWED_TRANSITIONS",
    "AdapterAction",
    "CancellationReason",
    "QueueOrderingKey",
    "ResidencyAction",
    "ResidencyPlan",
    "SchedulerJobRuntime",
    "SchedulerJobState",
    "SchedulerPassResult",
    "SchedulerStateSummary",
    "SubmitRouteResult",
    "TERMINAL_STATES",
    "queue_ordering_tuple",
    "validate_transition",
]
