"""BUILD 11 microstructure executor and scheduler integration tests."""

from __future__ import annotations

import dataclasses
import unittest

from market_platform_foundation.intelligence.contracts import ContractKind, ContractReference
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult
from market_platform_foundation.intelligence.scheduling import (
    InferenceScheduler,
    ResidencyAction,
    ResourceClass,
    ResourceSnapshot,
    SchedulerJobState,
    StaticResourceProvider,
)
from market_platform_foundation.intelligence.specialists import (
    MICROSTRUCTURE_CPU_PROFILE,
    MicrostructureInferenceExecutor,
    SpecialistDiagnosticCode,
    SpecialistExecutionStatus,
    apply_execution_timing,
    resolve_specialist_context,
)
from tests.intelligence.routing_fixtures import T
from tests.intelligence.scheduling_fixtures import sample_route
from tests.intelligence.specialists_fixtures import order_flow_detection, routed_microstructure_job


def _cpu_resources(*, residency: str | None = "microstructure-cpu") -> ResourceSnapshot:
    return ResourceSnapshot(
        captured_at_ns=T,
        cpu_slots_total=8,
        cpu_slots_available=8,
        gpu_slots_total=0,
        gpu_slots_available=0,
        vram_bytes_total=0,
        vram_bytes_available=0,
        current_residency_key=residency,
        supported_resource_classes=frozenset({ResourceClass.CPU}),
    )


class MicrostructureExecutorTests(unittest.TestCase):
    def test_profile_is_cpu_without_gpu(self) -> None:
        self.assertEqual(MICROSTRUCTURE_CPU_PROFILE.resource_class, ResourceClass.CPU)
        self.assertEqual(MICROSTRUCTURE_CPU_PROFILE.min_vram_bytes, 0)
        self.assertIsNone(MICROSTRUCTURE_CPU_PROFILE.adapter_key)

    def test_executor_submission(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        repo, route, job = routed_microstructure_job(detection, snap2, signals=(sig_prev, sig_curr))
        executor = MicrostructureInferenceExecutor(repository=repo)
        scheduler = InferenceScheduler(
            executor=executor,
            resource_provider=StaticResourceProvider(_cpu_resources()),
        )
        scheduler.submit_route(
            route,
            scheduler_time_ns=T,
            source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snap2.snapshot_id),
        )
        scheduler.schedule_once(T)
        self.assertGreaterEqual(len(executor.dispatches), 1)
        outcome = executor.outcomes[job.job_id]
        self.assertEqual(outcome.status, SpecialistExecutionStatus.COMPLETED)
        self.assertEqual(len(outcome.evidence), 1)

    def test_scheduler_lifecycle_with_specialist(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        repo, route, job = routed_microstructure_job(detection, snap2, signals=(sig_prev, sig_curr))
        executor = MicrostructureInferenceExecutor(repository=repo)
        scheduler = InferenceScheduler(
            executor=executor,
            resource_provider=StaticResourceProvider(_cpu_resources()),
        )
        admitted = scheduler.submit_route(
            route,
            scheduler_time_ns=T,
            source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snap2.snapshot_id),
        )
        assert admitted.job is not None
        scheduler.schedule_once(T)
        scheduler.mark_running(admitted.job.job_id, scheduler_time_ns=T + 1)
        outcome = executor.execute_job(
            admitted.job,
            execution_start_time_ns=T + 1,
            completion_time_ns=T + 2,
            persist_evidence=True,
        )
        scheduler.complete_job(admitted.job.job_id, scheduler_time_ns=T + 2)
        self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.COMPLETED)
        self.assertEqual(repo.put_evidence(outcome.evidence[0]), RepositoryPutResult.ALREADY_PRESENT)

    def test_stale_before_start(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        repo, _, job = routed_microstructure_job(detection, snap2, signals=(sig_prev, sig_curr))
        executor = MicrostructureInferenceExecutor(repository=repo)
        outcome = executor.execute_job(job, execution_start_time_ns=job.expires_at_ns)
        self.assertEqual(outcome.status, SpecialistExecutionStatus.STALE)
        self.assertEqual(outcome.diagnostics[-1].code, SpecialistDiagnosticCode.STALE_INFERENCE)
        self.assertEqual(outcome.evidence, ())

    def test_stale_after_completion(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        repo, _, job = routed_microstructure_job(detection, snap2, signals=(sig_prev, sig_curr))
        executor = MicrostructureInferenceExecutor(repository=repo)
        outcome = executor.execute_job(
            job,
            execution_start_time_ns=job.expires_at_ns - 1,
            completion_time_ns=job.expires_at_ns,
        )
        self.assertEqual(outcome.status, SpecialistExecutionStatus.STALE)
        self.assertEqual(outcome.evidence, ())

    def test_deadline_missed_but_valid(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        repo, _, job = routed_microstructure_job(detection, snap2, signals=(sig_prev, sig_curr))
        executor = MicrostructureInferenceExecutor(repository=repo)
        context, _ = resolve_specialist_context(job=job, repository=repo)
        assert context is not None
        result = executor.specialist.analyze(context)
        outcome = apply_execution_timing(
            job,
            result,
            execution_start_time_ns=T,
            completion_time_ns=job.deadline_time_ns + 1,
        )
        self.assertEqual(outcome.status, SpecialistExecutionStatus.COMPLETED)
        self.assertTrue(outcome.deadline_missed)
        self.assertFalse(outcome.stale)
        codes = {item.code for item in outcome.diagnostics}
        self.assertIn(SpecialistDiagnosticCode.DEADLINE_MISSED, codes)

    def test_batch_blind_independence(self) -> None:
        _, snap_a, prev_a, curr_a, det_a = order_flow_detection(snap2_id="snap-a")
        _, snap_b, prev_b, curr_b, det_b = order_flow_detection(
            snap2_id="snap-b",
            current_nss=0.55,
        )
        repo_a, _, job_a = routed_microstructure_job(det_a, snap_a, signals=(prev_a, curr_a))
        _, _, job_b = routed_microstructure_job(det_b, snap_b, signals=(prev_b, curr_b), repo=repo_a)
        executor = MicrostructureInferenceExecutor(repository=repo_a)
        out_a = executor.execute_job(job_a, execution_start_time_ns=T)
        out_b = executor.execute_job(job_b, execution_start_time_ns=T)
        self.assertNotEqual(out_a.evidence[0].evidence_id, out_b.evidence[0].evidence_id)
        self.assertNotEqual(
            out_a.evidence[0].assessment["current_nss"],
            out_b.evidence[0].assessment["current_nss"],
        )

    def test_residency_no_special_action_when_aligned(self) -> None:
        from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository

        executor = MicrostructureInferenceExecutor(repository=InMemoryIntelligenceRepository())
        scheduler = InferenceScheduler(
            executor=executor,
            resource_provider=StaticResourceProvider(_cpu_resources(residency="microstructure-cpu")),
        )
        route = sample_route()
        scheduler.submit_route(route, scheduler_time_ns=T)
        scheduler.schedule_once(T)
        self.assertEqual(
            executor.dispatches[0].residency_plan.residency_action,
            ResidencyAction.KEEP_CURRENT,
        )


if __name__ == "__main__":
    unittest.main()
