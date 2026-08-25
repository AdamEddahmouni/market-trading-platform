"""Deterministic batch planning for BUILD 10."""

from __future__ import annotations

from .identity import derive_dispatch_batch_id
from .models import SchedulerJobRuntime
from .profiles import InferenceExecutionProfile


def jobs_batch_compatible(left: SchedulerJobRuntime, right: SchedulerJobRuntime, profile: InferenceExecutionProfile) -> bool:
    left_job = left.job
    right_job = right.job
    return (
        left_job.execution_profile_id == right_job.execution_profile_id
        and left_job.batch_key == right_job.batch_key
        and left_job.residency_key == right_job.residency_key
        and left_job.adapter_key == right_job.adapter_key
        and left_job.expert_domain == right_job.expert_domain
        and profile.max_batch_size > 1
    )


def plan_batches(
    ready_jobs: list[SchedulerJobRuntime],
    profiles: dict[str, InferenceExecutionProfile],
    *,
    scheduler_policy_identity: str,
) -> list[tuple[str, tuple[SchedulerJobRuntime, ...]]]:
    """Group compatible ready jobs into deterministic batches without delaying urgent work."""
    batches: list[tuple[str, tuple[SchedulerJobRuntime, ...]]] = []
    used: set[str] = set()

    for anchor in ready_jobs:
        if anchor.job.job_id in used:
            continue
        profile = profiles[anchor.job.execution_profile_id]
        group = [anchor]
        used.add(anchor.job.job_id)
        for candidate in ready_jobs:
            if candidate.job.job_id in used:
                continue
            if len(group) >= profile.max_batch_size:
                break
            if jobs_batch_compatible(anchor, candidate, profile):
                group.append(candidate)
                used.add(candidate.job.job_id)
        job_ids = tuple(runtime.job.job_id for runtime in group)
        batch_id = derive_dispatch_batch_id(job_ids=job_ids, scheduler_policy_identity=scheduler_policy_identity)
        batches.append((batch_id, tuple(group)))
    return batches


__all__ = ["jobs_batch_compatible", "plan_batches"]
