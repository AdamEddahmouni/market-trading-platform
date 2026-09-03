"""Concrete microstructure inference executor for BUILD 10 dispatch boundary."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import InferenceJobV1
from ..persistence.repository import IntelligenceRepository
from ..scheduling.executor import DispatchReceipt, InferenceDispatchBatch, InferenceExecutor
from .microstructure import MicrostructureSpecialist
from .models import SpecialistExecutionOutcome, SpecialistExecutionStatus, SpecialistResult
from .policy import MicrostructureSpecialistPolicyV1
from .resolver import resolve_specialist_context
from .runner import apply_execution_timing, execute_specialist_result


@dataclass
class MicrostructureInferenceExecutor:
    """Runs deterministic microstructure analysis for BUILD 10 dispatch batches."""

    repository: IntelligenceRepository
    policy: MicrostructureSpecialistPolicyV1 | None = None
    specialist: MicrostructureSpecialist | None = None
    accept: bool = True
    reject_job_ids: frozenset[str] = frozenset()
    dispatches: list[InferenceDispatchBatch] = field(default_factory=list)
    receipts: list[DispatchReceipt] = field(default_factory=list)
    outcomes: dict[str, SpecialistExecutionOutcome] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.specialist is None:
            self.specialist = MicrostructureSpecialist(self.policy)

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

        accepted: list[str] = []
        rejected: list[str] = []
        for job in batch.jobs:
            if job.job_id in self.reject_job_ids:
                rejected.append(job.job_id)
                continue
            accepted.append(job.job_id)
            outcome = self.execute_job(job, execution_start_time_ns=batch.dispatched_at_ns)
            self.outcomes[job.job_id] = outcome

        receipt = DispatchReceipt(
            dispatch_id=batch.dispatch_id,
            batch_id=batch.batch_id,
            accepted_job_ids=tuple(accepted),
            rejected_job_ids=tuple(rejected),
            dispatched_at_ns=batch.dispatched_at_ns,
        )
        self.receipts.append(receipt)
        return receipt

    def execute_job(
        self,
        job: InferenceJobV1,
        *,
        execution_start_time_ns: int,
        completion_time_ns: int | None = None,
        persist_evidence: bool = False,
    ) -> SpecialistExecutionOutcome:
        context, failure = resolve_specialist_context(
            job=job,
            repository=self.repository,
            policy=self.policy,
        )
        if failure is not None:
            return apply_execution_timing(
                job,
                failure,
                execution_start_time_ns=execution_start_time_ns,
                completion_time_ns=completion_time_ns or execution_start_time_ns,
            )

        assert context is not None
        assert self.specialist is not None
        result = self.specialist.analyze(context)
        return execute_specialist_result(
            job=job,
            route=context.route,
            result=result,
            repository=self.repository,
            execution_start_time_ns=execution_start_time_ns,
            completion_time_ns=completion_time_ns,
            persist_evidence=persist_evidence,
        )


__all__ = ["MicrostructureInferenceExecutor"]
