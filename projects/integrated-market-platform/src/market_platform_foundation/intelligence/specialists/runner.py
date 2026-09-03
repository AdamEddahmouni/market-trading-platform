"""Specialist dispatch runner — orchestrates execution, persistence, and outcomes."""

from __future__ import annotations

from ..contracts import InferenceJobV1, RoutingDecisionV1
from ..persistence.errors import RepositoryConflictError
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .models import (
    SpecialistDiagnostic,
    SpecialistDiagnosticCode,
    SpecialistExecutionOutcome,
    SpecialistExecutionStatus,
    SpecialistResult,
)


def apply_execution_timing(
    job: InferenceJobV1,
    result: SpecialistResult,
    *,
    execution_start_time_ns: int,
    completion_time_ns: int,
) -> SpecialistExecutionOutcome:
    stale = execution_start_time_ns >= job.expires_at_ns or completion_time_ns >= job.expires_at_ns
    deadline_missed = completion_time_ns > job.deadline_time_ns
    status = result.status
    diagnostics = list(result.diagnostics)
    evidence = result.evidence

    if stale:
        status = SpecialistExecutionStatus.STALE
        diagnostics.append(
            SpecialistDiagnostic(
                SpecialistDiagnosticCode.STALE_INFERENCE,
                "specialist execution crossed hard expiration boundary",
                {
                    "execution_start_time_ns": execution_start_time_ns,
                    "completion_time_ns": completion_time_ns,
                    "expires_at_ns": job.expires_at_ns,
                },
            )
        )
        evidence = ()
    elif deadline_missed and status == SpecialistExecutionStatus.COMPLETED:
        diagnostics.append(
            SpecialistDiagnostic(
                SpecialistDiagnosticCode.DEADLINE_MISSED,
                "specialist completed after deadline but before expiration",
                {
                    "completion_time_ns": completion_time_ns,
                    "deadline_time_ns": job.deadline_time_ns,
                },
            )
        )

    return SpecialistExecutionOutcome(
        job_id=job.job_id,
        status=status,
        evidence=evidence,
        diagnostics=tuple(diagnostics),
        started_at_ns=execution_start_time_ns,
        completed_at_ns=completion_time_ns,
        deadline_missed=deadline_missed,
        stale=stale,
    )


def execute_specialist_result(
    *,
    job: InferenceJobV1,
    route: RoutingDecisionV1,
    result: SpecialistResult,
    repository: IntelligenceRepository,
    execution_start_time_ns: int,
    completion_time_ns: int | None = None,
    persist_evidence: bool = True,
) -> SpecialistExecutionOutcome:
    completed_at = completion_time_ns if completion_time_ns is not None else execution_start_time_ns
    outcome = apply_execution_timing(
        job,
        result,
        execution_start_time_ns=execution_start_time_ns,
        completion_time_ns=completed_at,
    )
    if not persist_evidence or outcome.stale or not outcome.evidence:
        return outcome

    persisted: list[str] = []
    diagnostics = list(outcome.diagnostics)
    status = outcome.status
    for evidence in outcome.evidence:
        try:
            put_result = repository.put_evidence(evidence)
            persisted.append(put_result.value)
        except RepositoryConflictError as exc:
            status = SpecialistExecutionStatus.FAILED
            diagnostics.append(
                SpecialistDiagnostic(
                    SpecialistDiagnosticCode.EVIDENCE_CONFLICT,
                    "evidence persistence conflict",
                    {"evidence_id": evidence.evidence_id, "error": str(exc)},
                )
            )
            return SpecialistExecutionOutcome(
                job_id=job.job_id,
                status=status,
                evidence=(),
                diagnostics=tuple(diagnostics),
                started_at_ns=outcome.started_at_ns,
                completed_at_ns=outcome.completed_at_ns,
                deadline_missed=outcome.deadline_missed,
                stale=outcome.stale,
            )

    _ = route.routing_decision_id
    _ = persisted
    return outcome


def persist_outcome_evidence(
    outcome: SpecialistExecutionOutcome,
    *,
    repository: IntelligenceRepository,
) -> tuple[SpecialistExecutionOutcome, tuple[RepositoryPutResult, ...]]:
    if outcome.stale or not outcome.evidence:
        return outcome, ()
    results: list[RepositoryPutResult] = []
    for evidence in outcome.evidence:
        results.append(repository.put_evidence(evidence))
    return outcome, tuple(results)


__all__ = [
    "apply_execution_timing",
    "execute_specialist_result",
    "persist_outcome_evidence",
]
