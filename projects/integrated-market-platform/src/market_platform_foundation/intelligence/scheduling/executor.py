"""Abstract executor boundary and recording fake for BUILD 10."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..contracts import InferenceJobV1
from .models import ResidencyPlan


@dataclass(frozen=True, slots=True)
class InferenceDispatchBatch:
    batch_id: str
    dispatch_id: str
    jobs: tuple[InferenceJobV1, ...]
    residency_plan: ResidencyPlan
    dispatched_at_ns: int


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    dispatch_id: str
    batch_id: str
    accepted_job_ids: tuple[str, ...]
    rejected_job_ids: tuple[str, ...]
    dispatched_at_ns: int


@runtime_checkable
class InferenceExecutor(Protocol):
    """Future BUILD 11 specialist execution boundary."""

    def submit(self, batch: InferenceDispatchBatch) -> DispatchReceipt: ...


@dataclass
class RecordingInferenceExecutor:
    """Test-only executor that records dispatches without running models."""

    accept: bool = True
    reject_job_ids: frozenset[str] = frozenset()
    dispatches: list[InferenceDispatchBatch] = field(default_factory=list)
    receipts: list[DispatchReceipt] = field(default_factory=list)

    def submit(self, batch: InferenceDispatchBatch) -> DispatchReceipt:
        self.dispatches.append(batch)
        if not self.accept:
            receipt = DispatchReceipt(
                dispatch_id=batch.dispatch_id,
                batch_id=batch.batch_id,
                accepted_job_ids=(),
                rejected_job_ids=tuple(job.job_id for job in batch.jobs),
                dispatched_at_ns=batch.dispatched_at_ns,
            )
            self.receipts.append(receipt)
            return receipt
        accepted = tuple(job.job_id for job in batch.jobs if job.job_id not in self.reject_job_ids)
        rejected = tuple(job.job_id for job in batch.jobs if job.job_id in self.reject_job_ids)
        receipt = DispatchReceipt(
            dispatch_id=batch.dispatch_id,
            batch_id=batch.batch_id,
            accepted_job_ids=accepted,
            rejected_job_ids=rejected,
            dispatched_at_ns=batch.dispatched_at_ns,
        )
        self.receipts.append(receipt)
        return receipt


__all__ = [
    "DispatchReceipt",
    "InferenceDispatchBatch",
    "InferenceExecutor",
    "RecordingInferenceExecutor",
]
