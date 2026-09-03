"""Deterministic inference scheduler (BUILD 10)."""

from __future__ import annotations

import heapq
from dataclasses import replace
from typing import Any

from ..contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    InferenceJobV1,
    RouteAction,
    RoutingDecisionV1,
)
from .batching import plan_batches
from .errors import SchedulerAdmissionError, SchedulerStateTransitionError
from .executor import DispatchReceipt, InferenceDispatchBatch, InferenceExecutor
from .identity import derive_dispatch_batch_id, derive_inference_job_id
from .models import (
    CancellationReason,
    QueueOrderingKey,
    SchedulerJobRuntime,
    SchedulerJobState,
    SchedulerPassResult,
    SchedulerStateSummary,
    SubmitRouteResult,
    TERMINAL_STATES,
    queue_ordering_tuple,
    validate_transition,
)
from .observer import SchedulerEvent, SchedulerEventKind, SchedulerObserver
from .profiles import ExecutionProfileRegistry, InferenceExecutionProfile, ResourceClass
from .policy import SchedulerPolicyV1
from .residency import plan_residency, residency_affinity_rank
from .resources import ResourceProvider, ResourceSnapshot, default_resource_snapshot


class InferenceScheduler:
    """Converts routing intents into resource-aware dispatch plans without specialist inference."""

    SCHEDULER_ID = "inference-scheduler"
    SCHEDULER_VERSION = "1"

    def __init__(
        self,
        *,
        policy: SchedulerPolicyV1 | None = None,
        profile_registry: ExecutionProfileRegistry | None = None,
        resource_provider: ResourceProvider | None = None,
        executor: InferenceExecutor | None = None,
        observer: SchedulerObserver | None = None,
    ) -> None:
        self.policy = policy or SchedulerPolicyV1()
        self.profile_registry = profile_registry or ExecutionProfileRegistry()
        self._resource_provider = resource_provider
        self._executor = executor
        self._observer = observer or SchedulerObserver()
        self._jobs: dict[str, SchedulerJobRuntime] = {}
        self._submission_counter = 0
        self._dispatch_counter = 0
        self._reserved_cpu_slots = 0
        self._reserved_gpu_slots = 0
        self._reserved_vram_bytes = 0
        self._profile_by_id: dict[str, InferenceExecutionProfile] = {
            profile.profile_id: profile for profile in self.profile_registry.profiles.values()
        }

    @property
    def scheduler_lineage(self) -> ComponentLineage:
        return ComponentLineage(component_id=self.SCHEDULER_ID, component_version=self.SCHEDULER_VERSION)

    def submit_route(
        self,
        route: RoutingDecisionV1,
        *,
        scheduler_time_ns: int,
        source_snapshot_ref: ContractReference | None = None,
    ) -> SubmitRouteResult:
        if route.route_action != RouteAction.ROUTE:
            return SubmitRouteResult(None, SchedulerJobState.REJECTED, "ROUTE_NOT_EXECUTABLE", ("ROUTE_NOT_EXECUTABLE",))
        assert route.deadline_time_ns is not None and route.expires_at_ns is not None
        if scheduler_time_ns >= route.expires_at_ns:
            return SubmitRouteResult(None, SchedulerJobState.EXPIRED, "ROUTE_ALREADY_EXPIRED", ("ROUTE_ALREADY_EXPIRED",))

        profile = self.profile_registry.profile_for(route.expert_domain)
        if profile is None:
            return SubmitRouteResult(
                None,
                SchedulerJobState.REJECTED,
                "UNSUPPORTED_EXECUTION_PROFILE",
                ("UNSUPPORTED_EXECUTION_PROFILE",),
            )

        job_id = derive_inference_job_id(
            routing_decision_id=route.routing_decision_id,
            scheduler_policy_identity=self.policy.identity,
            execution_profile_id=profile.profile_id,
        )
        existing = self._jobs.get(job_id)
        if existing is not None and existing.state not in TERMINAL_STATES:
            self._observer.emit(
                SchedulerEvent(SchedulerEventKind.JOB_DEDUPLICATED, scheduler_time_ns, job_id=job_id)
            )
            return SubmitRouteResult(existing.job, existing.state, "ALREADY_PRESENT", ("ALREADY_QUEUED",))

        job = InferenceJobV1(
            job_id=job_id,
            schema_version="1",
            routing_decision_ref=ContractReference(
                kind=ContractKind.ROUTING_DECISION.value,
                id=route.routing_decision_id,
            ),
            detection_ref=route.detection_ref,
            source_snapshot_ref=source_snapshot_ref,
            expert_domain=route.expert_domain,
            priority=route.priority,
            decision_time_ns=route.decision_time_ns,
            submitted_at_ns=scheduler_time_ns,
            deadline_time_ns=route.deadline_time_ns,
            expires_at_ns=route.expires_at_ns,
            required_capabilities=route.required_capabilities,
            execution_profile_id=profile.profile_id,
            batch_key=profile.batch_key,
            residency_key=profile.residency_key,
            adapter_key=profile.adapter_key,
            scheduler_policy_identity=self.policy.identity,
            scheduler_lineage=self.scheduler_lineage,
            metadata=dict(route.metadata),
        )
        self._submission_counter += 1
        runtime = SchedulerJobRuntime(
            job=job,
            state=SchedulerJobState.QUEUED,
            submission_sequence=self._submission_counter,
        )
        self._jobs[job_id] = runtime
        self._observer.emit(SchedulerEvent(SchedulerEventKind.JOB_ADMITTED, scheduler_time_ns, job_id=job_id))

        if self.policy.enable_supersession:
            self._apply_supersession(runtime, scheduler_time_ns)

        return SubmitRouteResult(job, runtime.state, "ADMITTED", ())

    def cancel_job(self, job_id: str, *, reason: CancellationReason, scheduler_time_ns: int) -> bool:
        runtime = self._jobs.get(job_id)
        if runtime is None or runtime.state in TERMINAL_STATES:
            return False
        if runtime.state in (SchedulerJobState.DISPATCHED, SchedulerJobState.RUNNING):
            return False
        self._transition(runtime, SchedulerJobState.CANCELLED, scheduler_time_ns)
        runtime.cancellation_reason = reason
        self._release_reservations(runtime)
        self._observer.emit(
            SchedulerEvent(
                SchedulerEventKind.JOB_CANCELLED,
                scheduler_time_ns,
                job_id=job_id,
                details={"reason": reason.value},
            )
        )
        return True

    def update_resources(self, snapshot: ResourceSnapshot) -> None:
        self._resource_provider = _InlineResourceProvider(snapshot)

    def schedule_once(self, now_ns: int) -> SchedulerPassResult:
        resources = self._current_resources(now_ns)
        expired: list[str] = []
        superseded: list[str] = []
        blocked: list[str] = []
        rejected: list[str] = []
        deadline_missed: list[str] = []
        diagnostics: list[str] = []

        for runtime in list(self._jobs.values()):
            if runtime.state in TERMINAL_STATES:
                continue
            if now_ns >= runtime.job.expires_at_ns:
                self._transition(runtime, SchedulerJobState.EXPIRED, now_ns)
                self._release_reservations(runtime)
                expired.append(runtime.job.job_id)
                self._observer.emit(
                    SchedulerEvent(SchedulerEventKind.JOB_EXPIRED, now_ns, job_id=runtime.job.job_id)
                )
                continue
            if (
                self.policy.treat_deadline_missed_as_urgent
                and now_ns >= runtime.job.deadline_time_ns
                and not runtime.deadline_missed
            ):
                runtime.deadline_missed = True
                deadline_missed.append(runtime.job.job_id)
                diagnostics.append("DEADLINE_MISSED")

        ready_candidates: list[SchedulerJobRuntime] = []
        for runtime in self._jobs.values():
            if runtime.state in (SchedulerJobState.QUEUED, SchedulerJobState.BLOCKED_RESOURCE):
                if runtime.next_eligible_time_ns > now_ns:
                    continue
                profile = self._profile_by_id[runtime.job.execution_profile_id]
                if self._profile_permanently_unsupported(profile, resources):
                    self._transition(runtime, SchedulerJobState.REJECTED, now_ns)
                    rejected.append(runtime.job.job_id)
                    continue
                if self.policy.reject_if_cannot_complete_before_expiration:
                    if now_ns + profile.estimated_duration_ns > runtime.job.expires_at_ns:
                        self._transition(runtime, SchedulerJobState.REJECTED, now_ns)
                        rejected.append(runtime.job.job_id)
                        diagnostics.append("CANNOT_COMPLETE_BEFORE_EXPIRATION")
                        continue
                admission = self._resource_admission(runtime, profile, resources)
                if admission == SchedulerJobState.BLOCKED_RESOURCE:
                    if runtime.state != SchedulerJobState.BLOCKED_RESOURCE:
                        self._transition(runtime, SchedulerJobState.BLOCKED_RESOURCE, now_ns)
                        self._observer.emit(
                            SchedulerEvent(
                                SchedulerEventKind.JOB_BLOCKED_RESOURCE,
                                now_ns,
                                job_id=runtime.job.job_id,
                            )
                        )
                    blocked.append(runtime.job.job_id)
                    continue
                self._transition(runtime, SchedulerJobState.READY, now_ns)
                runtime.residency_plan = plan_residency(profile, resources)
                ready_candidates.append(runtime)
                self._observer.emit(
                    SchedulerEvent(SchedulerEventKind.JOB_READY, now_ns, job_id=runtime.job.job_id)
                )

        ordered_ready = self._order_ready_jobs(ready_candidates, resources)
        batches = plan_batches(
            ordered_ready,
            self._profile_by_id,
            scheduler_policy_identity=self.policy.identity,
        )

        dispatch_batches: list[InferenceDispatchBatch] = []
        if self._executor is not None:
            for batch_id, group in batches:
                if not group:
                    continue
                profile = self._profile_by_id[group[0].job.execution_profile_id]
                residency_plan = plan_residency(profile, resources)
                self._dispatch_counter += 1
                dispatch_id = f"DISP-{self._dispatch_counter:08d}"
                batch = InferenceDispatchBatch(
                    batch_id=batch_id,
                    dispatch_id=dispatch_id,
                    jobs=tuple(runtime.job for runtime in group),
                    residency_plan=residency_plan,
                    dispatched_at_ns=now_ns,
                )
                for runtime in group:
                    if not self._reserve_resources(runtime, profile):
                        self._transition(runtime, SchedulerJobState.BLOCKED_RESOURCE, now_ns)
                        blocked.append(runtime.job.job_id)
                        continue
                    self._transition(runtime, SchedulerJobState.DISPATCHED, now_ns)
                    runtime.dispatch_id = dispatch_id
                    runtime.batch_id = batch_id
                    runtime.residency_plan = residency_plan
                    self._observer.emit(
                        SchedulerEvent(
                            SchedulerEventKind.RESIDENCY_PLAN,
                            now_ns,
                            job_id=runtime.job.job_id,
                            details={
                                "residency_action": residency_plan.residency_action.value,
                                "adapter_action": residency_plan.adapter_action.value,
                            },
                        )
                    )
                receipt = self._executor.submit(batch)
                dispatch_batches.append(batch)
                self._handle_dispatch_receipt(receipt, group, now_ns)
                self._observer.emit(
                    SchedulerEvent(
                        SchedulerEventKind.BATCH_PLANNED,
                        now_ns,
                        details={"batch_id": batch_id, "job_ids": [runtime.job.job_id for runtime in group]},
                    )
                )

        for runtime in self._jobs.values():
            if runtime.state == SchedulerJobState.SUPERSEDED:
                superseded.append(runtime.job.job_id)

        return SchedulerPassResult(
            dispatch_batches=tuple(dispatch_batches),
            expired_job_ids=tuple(sorted(expired)),
            cancelled_job_ids=tuple(
                sorted(job_id for job_id, row in self._jobs.items() if row.state == SchedulerJobState.CANCELLED)
            ),
            superseded_job_ids=tuple(sorted(set(superseded))),
            blocked_job_ids=tuple(sorted(set(blocked))),
            rejected_job_ids=tuple(sorted(set(rejected))),
            deadline_missed_job_ids=tuple(sorted(set(deadline_missed))),
            state_summary=self.snapshot_state(),
            diagnostics=tuple(diagnostics),
        )

    def mark_running(self, job_id: str, *, scheduler_time_ns: int) -> None:
        runtime = self._require_runtime(job_id)
        self._transition(runtime, SchedulerJobState.RUNNING, scheduler_time_ns)
        self._observer.emit(SchedulerEvent(SchedulerEventKind.JOB_RUNNING, scheduler_time_ns, job_id=job_id))

    def complete_job(self, job_id: str, *, scheduler_time_ns: int) -> None:
        runtime = self._require_runtime(job_id)
        self._transition(runtime, SchedulerJobState.COMPLETED, scheduler_time_ns)
        self._release_reservations(runtime)
        self._observer.emit(SchedulerEvent(SchedulerEventKind.JOB_COMPLETED, scheduler_time_ns, job_id=job_id))

    def fail_job(self, job_id: str, *, scheduler_time_ns: int, retry: bool = False) -> None:
        runtime = self._require_runtime(job_id)
        self._release_reservations(runtime)
        runtime.attempt_count += 1
        if retry and runtime.attempt_count < self.policy.max_attempts:
            runtime.next_eligible_time_ns = scheduler_time_ns + self.policy.retry_delay_ns
            if scheduler_time_ns + self.policy.retry_delay_ns < runtime.job.expires_at_ns:
                self._transition(runtime, SchedulerJobState.QUEUED, scheduler_time_ns)
                return
        self._transition(runtime, SchedulerJobState.FAILED, scheduler_time_ns)
        self._observer.emit(SchedulerEvent(SchedulerEventKind.JOB_FAILED, scheduler_time_ns, job_id=job_id))

    def get_job(self, job_id: str) -> SchedulerJobRuntime | None:
        return self._jobs.get(job_id)

    def get_job_state(self, job_id: str) -> SchedulerJobState | None:
        runtime = self._jobs.get(job_id)
        return runtime.state if runtime is not None else None

    def snapshot_state(self) -> SchedulerStateSummary:
        counts = {state: 0 for state in SchedulerJobState}
        for runtime in self._jobs.values():
            counts[runtime.state] += 1
        return SchedulerStateSummary(
            queued=counts[SchedulerJobState.QUEUED],
            blocked=counts[SchedulerJobState.BLOCKED_RESOURCE],
            ready=counts[SchedulerJobState.READY],
            dispatched=counts[SchedulerJobState.DISPATCHED],
            running=counts[SchedulerJobState.RUNNING],
            completed=counts[SchedulerJobState.COMPLETED],
            failed=counts[SchedulerJobState.FAILED],
            cancelled=counts[SchedulerJobState.CANCELLED],
            expired=counts[SchedulerJobState.EXPIRED],
            superseded=counts[SchedulerJobState.SUPERSEDED],
            rejected=counts[SchedulerJobState.REJECTED],
        )

    def _current_resources(self, now_ns: int) -> ResourceSnapshot:
        if self._resource_provider is None:
            base = default_resource_snapshot(now_ns=now_ns)
        else:
            base = self._resource_provider.snapshot(now_ns=now_ns)
        return ResourceSnapshot(
            captured_at_ns=base.captured_at_ns,
            cpu_slots_total=base.cpu_slots_total,
            cpu_slots_available=max(0, base.cpu_slots_available - self._reserved_cpu_slots),
            gpu_slots_total=base.gpu_slots_total,
            gpu_slots_available=max(0, base.gpu_slots_available - self._reserved_gpu_slots),
            vram_bytes_total=base.vram_bytes_total,
            vram_bytes_available=max(0, base.vram_bytes_available - self._reserved_vram_bytes),
            current_residency_key=base.current_residency_key,
            current_adapter_key=base.current_adapter_key,
            active_job_count=base.active_job_count,
            supported_resource_classes=base.supported_resource_classes,
        )

    def _order_ready_jobs(
        self,
        ready_jobs: list[SchedulerJobRuntime],
        resources: ResourceSnapshot,
    ) -> list[SchedulerJobRuntime]:
        keyed: list[tuple[tuple[int, ...], SchedulerJobRuntime]] = []
        for runtime in ready_jobs:
            profile = self._profile_by_id[runtime.job.execution_profile_id]
            affinity = (
                residency_affinity_rank(profile, resources)
                if self.policy.enable_residency_affinity
                else 1
            )
            key = QueueOrderingKey.from_runtime(runtime, residency_affinity_rank=affinity)
            keyed.append((queue_ordering_tuple(key), runtime))
        keyed.sort(key=lambda row: row[0])
        return [runtime for _, runtime in keyed]

    def _resource_admission(
        self,
        runtime: SchedulerJobRuntime,
        profile: InferenceExecutionProfile,
        resources: ResourceSnapshot,
    ) -> SchedulerJobState:
        if profile.resource_class not in resources.supported_resource_classes:
            return SchedulerJobState.REJECTED
        if profile.resource_class == ResourceClass.CPU:
            if resources.cpu_slots_available < profile.cpu_slots:
                return SchedulerJobState.BLOCKED_RESOURCE
            return SchedulerJobState.READY
        if resources.gpu_slots_available < 1:
            return SchedulerJobState.BLOCKED_RESOURCE
        if resources.vram_bytes_available < profile.min_vram_bytes:
            return SchedulerJobState.BLOCKED_RESOURCE
        return SchedulerJobState.READY

    def _profile_permanently_unsupported(
        self,
        profile: InferenceExecutionProfile,
        resources: ResourceSnapshot,
    ) -> bool:
        if profile.resource_class not in resources.supported_resource_classes:
            return True
        if profile.resource_class == ResourceClass.GPU and resources.gpu_slots_total < 1:
            return True
        if profile.resource_class == ResourceClass.GPU and resources.vram_bytes_total < profile.min_vram_bytes:
            return True
        return False

    def _reserve_resources(self, runtime: SchedulerJobRuntime, profile: InferenceExecutionProfile) -> bool:
        resources = self._current_resources(runtime.job.submitted_at_ns)
        if profile.resource_class == ResourceClass.CPU:
            if resources.cpu_slots_available < profile.cpu_slots:
                return False
            runtime.reserved_cpu_slots = profile.cpu_slots
            self._reserved_cpu_slots += profile.cpu_slots
            return True
        if resources.gpu_slots_available < 1 or resources.vram_bytes_available < profile.min_vram_bytes:
            return False
        runtime.reserved_gpu_slots = 1
        runtime.reserved_vram_bytes = profile.min_vram_bytes
        self._reserved_gpu_slots += 1
        self._reserved_vram_bytes += profile.min_vram_bytes
        return True

    def _release_reservations(self, runtime: SchedulerJobRuntime) -> None:
        self._reserved_cpu_slots = max(0, self._reserved_cpu_slots - runtime.reserved_cpu_slots)
        self._reserved_gpu_slots = max(0, self._reserved_gpu_slots - runtime.reserved_gpu_slots)
        self._reserved_vram_bytes = max(0, self._reserved_vram_bytes - runtime.reserved_vram_bytes)
        runtime.reserved_cpu_slots = 0
        runtime.reserved_gpu_slots = 0
        runtime.reserved_vram_bytes = 0

    def _apply_supersession(self, runtime: SchedulerJobRuntime, now_ns: int) -> None:
        key = self._supersession_key(runtime.job)
        for other in self._jobs.values():
            if other.job.job_id == runtime.job.job_id:
                continue
            if other.state not in (
                SchedulerJobState.QUEUED,
                SchedulerJobState.BLOCKED_RESOURCE,
                SchedulerJobState.READY,
            ):
                continue
            if self._supersession_key(other.job) == key and other.job.submitted_at_ns < runtime.job.submitted_at_ns:
                self._transition(other, SchedulerJobState.SUPERSEDED, now_ns)
                other.cancellation_reason = CancellationReason.SUPERSEDED
                self._release_reservations(other)
                self._observer.emit(
                    SchedulerEvent(SchedulerEventKind.JOB_SUPERSEDED, now_ns, job_id=other.job.job_id)
                )

    @staticmethod
    def _supersession_key(job: InferenceJobV1) -> tuple[str, ...]:
        return (
            job.expert_domain.value,
            str(job.metadata.get("instrument_id", "")),
            str(job.metadata.get("semantic_event_type", "")),
            job.execution_profile_id,
        )

    def _handle_dispatch_receipt(
        self,
        receipt: DispatchReceipt,
        group: tuple[SchedulerJobRuntime, ...],
        now_ns: int,
    ) -> None:
        accepted = set(receipt.accepted_job_ids)
        for runtime in group:
            if runtime.job.job_id in accepted:
                self._observer.emit(
                    SchedulerEvent(SchedulerEventKind.JOB_DISPATCHED, now_ns, job_id=runtime.job.job_id)
                )
            else:
                self.fail_job(runtime.job.job_id, scheduler_time_ns=now_ns, retry=True)

    def _transition(self, runtime: SchedulerJobRuntime, target: SchedulerJobState, now_ns: int) -> None:
        _ = now_ns
        try:
            validate_transition(runtime.state, target)
        except ValueError as exc:
            raise SchedulerStateTransitionError(str(exc), str(exc)) from exc
        runtime.state = target

    def _require_runtime(self, job_id: str) -> SchedulerJobRuntime:
        runtime = self._jobs.get(job_id)
        if runtime is None:
            raise SchedulerAdmissionError("JOB_NOT_FOUND", f"job not found: {job_id}")
        return runtime


class _InlineResourceProvider:
    def __init__(self, snapshot: ResourceSnapshot) -> None:
        self._snapshot = snapshot

    def snapshot(self, *, now_ns: int) -> ResourceSnapshot:
        _ = now_ns
        return self._snapshot


__all__ = ["InferenceScheduler"]
