"""BUILD 10 inference scheduler behavioral tests."""

from __future__ import annotations

import dataclasses
import unittest

from market_platform_foundation.intelligence.contracts import (
    ExpertDomain,
    RouteAction,
    RoutingPriority,
)
from market_platform_foundation.intelligence.replay import ReplayClock
from market_platform_foundation.intelligence.scheduling import (
    CancellationReason,
    InferenceScheduler,
    RecordingInferenceExecutor,
    ResidencyAction,
    ResourceClass,
    ResourceSnapshot,
    SchedulerJobState,
    SchedulerPolicyV1,
    SchedulerStateTransitionError,
    StaticResourceProvider,
    derive_dispatch_batch_id,
    derive_inference_job_id,
)
from tests.intelligence.scheduling_fixtures import SCHEDULER_T, route_with_priority, sample_route
from tests.intelligence.test_routing_contracts import sample_route as routing_sample_route


def gpu_resources(
    *,
    now_ns: int = SCHEDULER_T,
    gpu_available: int = 1,
    vram_available: int = 16 * 1024**3,
    residency: str | None = None,
    adapter: str | None = None,
) -> ResourceSnapshot:
    return ResourceSnapshot(
        captured_at_ns=now_ns,
        cpu_slots_total=8,
        cpu_slots_available=8,
        gpu_slots_total=1,
        gpu_slots_available=gpu_available,
        vram_bytes_total=16 * 1024**3,
        vram_bytes_available=vram_available,
        current_residency_key=residency,
        current_adapter_key=adapter,
    )


def cpu_resources(*, now_ns: int = SCHEDULER_T, cpu_available: int = 2) -> ResourceSnapshot:
    return ResourceSnapshot(
        captured_at_ns=now_ns,
        cpu_slots_total=8,
        cpu_slots_available=cpu_available,
        gpu_slots_total=0,
        gpu_slots_available=0,
        vram_bytes_total=0,
        vram_bytes_available=0,
        supported_resource_classes=frozenset({ResourceClass.CPU}),
    )


class InferenceSchedulerTests(unittest.TestCase):
    def test_dedup_same_route(self) -> None:
        scheduler = InferenceScheduler()
        route = sample_route()
        first = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        second = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T + 1)
        self.assertEqual(first.outcome, "ADMITTED")
        self.assertEqual(second.outcome, "ALREADY_PRESENT")
        self.assertEqual(first.job.job_id, second.job.job_id)

    def test_priority_ordering(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(cpu_resources(cpu_available=8)))
        routes = [
            dataclasses.replace(
                sample_route("ROUTE-low", expert_domain=ExpertDomain.POSITIONING_BORROW),
                priority=RoutingPriority.LOW,
            ),
            dataclasses.replace(
                sample_route("ROUTE-critical", expert_domain=ExpertDomain.REGIME_CROSS_ASSET),
                priority=RoutingPriority.CRITICAL,
            ),
            dataclasses.replace(
                sample_route("ROUTE-normal", expert_domain=ExpertDomain.POSITIONING_BORROW),
                priority=RoutingPriority.NORMAL,
                metadata={"instrument_id": "US:ABC", "semantic_event_type": "BORROW_CHANGE"},
            ),
            dataclasses.replace(
                sample_route("ROUTE-high", expert_domain=ExpertDomain.REGIME_CROSS_ASSET),
                priority=RoutingPriority.HIGH,
                metadata={"instrument_id": "US:DEF", "semantic_event_type": "REGIME_SHIFT"},
            ),
        ]
        for route in routes:
            scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T)
        dispatched = [job.routing_decision_ref.id for batch in executor.dispatches for job in batch.jobs]
        self.assertEqual(
            dispatched,
            ["ROUTE-critical", "ROUTE-high", "ROUTE-normal", "ROUTE-low"],
        )

    def test_earliest_deadline_first(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(gpu_resources()))
        early = dataclasses.replace(sample_route("ROUTE-early"), deadline_time_ns=SCHEDULER_T + 1_000_000_000)
        late = dataclasses.replace(sample_route("ROUTE-late"), deadline_time_ns=SCHEDULER_T + 10_000_000_000)
        scheduler.submit_route(late, scheduler_time_ns=SCHEDULER_T)
        scheduler.submit_route(early, scheduler_time_ns=SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(executor.dispatches[0].jobs[0].routing_decision_ref.id, "ROUTE-early")

    def test_hard_expiration_at_boundary(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(gpu_resources()))
        route = sample_route()
        result = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert result.job is not None
        expire_at = route.expires_at_ns
        scheduler.schedule_once(expire_at)
        self.assertEqual(scheduler.get_job_state(result.job.job_id), SchedulerJobState.EXPIRED)
        self.assertEqual(len(executor.dispatches), 0)

    def test_deadline_missed_but_still_runnable(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(gpu_resources()))
        route = sample_route()
        result = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert result.job is not None
        pass_result = scheduler.schedule_once(route.deadline_time_ns)
        self.assertIn(result.job.job_id, pass_result.deadline_missed_job_ids)
        scheduler.schedule_once(route.deadline_time_ns)
        self.assertGreaterEqual(len(executor.dispatches), 1)

    def test_route_already_expired_at_submission(self) -> None:
        scheduler = InferenceScheduler()
        route = sample_route()
        result = scheduler.submit_route(route, scheduler_time_ns=route.expires_at_ns)
        self.assertEqual(result.outcome, "ROUTE_ALREADY_EXPIRED")

    def test_gpu_blocked_then_recovery(self) -> None:
        executor = RecordingInferenceExecutor()
        blocked = gpu_resources(gpu_available=0, vram_available=0)
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(blocked))
        route = dataclasses.replace(
            sample_route("ROUTE-deriv-block"),
            expert_domain=ExpertDomain.DERIVATIVES,
        )
        admitted = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert admitted.job is not None
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.BLOCKED_RESOURCE)
        scheduler.update_resources(gpu_resources())
        scheduler.schedule_once(SCHEDULER_T + 1)
        self.assertEqual(len(executor.dispatches), 1)

    def test_vram_blocked(self) -> None:
        scheduler = InferenceScheduler(resource_provider=StaticResourceProvider(gpu_resources(vram_available=1024)))
        route = dataclasses.replace(
            sample_route("ROUTE-deriv-vram"),
            expert_domain=ExpertDomain.DERIVATIVES,
        )
        admitted = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert admitted.job is not None
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.BLOCKED_RESOURCE)

    def test_cpu_job_dispatch(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(cpu_resources()))
        route = dataclasses.replace(
            sample_route(expert_domain=ExpertDomain.POSITIONING_BORROW),
            routing_decision_id="ROUTE-positioning",
        )
        admitted = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(len(executor.dispatches), 1)

    def test_unsupported_gpu_profile_rejected(self) -> None:
        scheduler = InferenceScheduler(
            resource_provider=StaticResourceProvider(cpu_resources()),
        )
        route = dataclasses.replace(
            sample_route("ROUTE-deriv-reject"),
            expert_domain=ExpertDomain.DERIVATIVES,
        )
        admitted = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert admitted.job is not None
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.REJECTED)

    def test_batching_compatible_jobs(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(cpu_resources(cpu_available=8)))
        for index in range(3):
            scheduler.submit_route(sample_route(f"ROUTE-batch-{index}"), scheduler_time_ns=SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(len(executor.dispatches), 1)
        self.assertEqual(len(executor.dispatches[0].jobs), 3)

    def test_batch_identity_deterministic(self) -> None:
        job_ids = ("IJOB-a", "IJOB-b")
        policy = SchedulerPolicyV1().identity
        first = derive_dispatch_batch_id(job_ids=job_ids, scheduler_policy_identity=policy)
        second = derive_dispatch_batch_id(job_ids=job_ids, scheduler_policy_identity=policy)
        self.assertEqual(first, second)

    def test_residency_keep_current(self) -> None:
        executor = RecordingInferenceExecutor()
        resources = cpu_resources()
        resources = dataclasses.replace(resources, current_residency_key="microstructure-cpu")
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(resources))
        route = sample_route()
        scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(executor.dispatches[0].residency_plan.residency_action, ResidencyAction.KEEP_CURRENT)

    def test_residency_load_required(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(gpu_resources()))
        route = sample_route()
        scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(executor.dispatches[0].residency_plan.residency_action, ResidencyAction.LOAD_RESIDENCY)

    def test_priority_beats_residency_affinity(self) -> None:
        executor = RecordingInferenceExecutor()
        resources = gpu_resources(residency="base-llm-micro", adapter="microstructure-adapter")
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(resources))
        low_same_residency = route_with_priority(RoutingPriority.LOW, "ROUTE-low-same")
        critical_different = dataclasses.replace(
            sample_route("ROUTE-critical-diff"),
            priority=RoutingPriority.CRITICAL,
            expert_domain=ExpertDomain.DERIVATIVES,
            routing_decision_id="ROUTE-critical-diff",
        )
        scheduler.submit_route(low_same_residency, scheduler_time_ns=SCHEDULER_T)
        scheduler.submit_route(critical_different, scheduler_time_ns=SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T)
        self.assertEqual(executor.dispatches[0].jobs[0].routing_decision_ref.id, "ROUTE-critical-diff")

    def test_supersession(self) -> None:
        scheduler = InferenceScheduler()
        old = sample_route("ROUTE-old")
        new = sample_route("ROUTE-new")
        old_result = scheduler.submit_route(old, scheduler_time_ns=SCHEDULER_T)
        new_result = scheduler.submit_route(new, scheduler_time_ns=SCHEDULER_T + 1)
        assert old_result.job is not None
        self.assertEqual(scheduler.get_job_state(old_result.job.job_id), SchedulerJobState.SUPERSEDED)
        assert new_result.job is not None
        self.assertEqual(scheduler.get_job_state(new_result.job.job_id), SchedulerJobState.QUEUED)

    def test_no_false_supersession(self) -> None:
        scheduler = InferenceScheduler()
        first = dataclasses.replace(sample_route("ROUTE-a"), metadata={"instrument_id": "US:AAA"})
        second = dataclasses.replace(sample_route("ROUTE-b"), metadata={"instrument_id": "US:BBB"})
        first_result = scheduler.submit_route(first, scheduler_time_ns=SCHEDULER_T)
        scheduler.submit_route(second, scheduler_time_ns=SCHEDULER_T + 1)
        assert first_result.job is not None
        self.assertEqual(scheduler.get_job_state(first_result.job.job_id), SchedulerJobState.QUEUED)

    def test_manual_cancellation(self) -> None:
        scheduler = InferenceScheduler()
        route = sample_route()
        admitted = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert admitted.job is not None
        self.assertTrue(
            scheduler.cancel_job(admitted.job.job_id, reason=CancellationReason.MANUAL, scheduler_time_ns=SCHEDULER_T)
        )
        self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.CANCELLED)

    def test_lifecycle_transitions(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(gpu_resources()))
        route = sample_route()
        admitted = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert admitted.job is not None
        scheduler.schedule_once(SCHEDULER_T)
        scheduler.mark_running(admitted.job.job_id, scheduler_time_ns=SCHEDULER_T + 1)
        scheduler.complete_job(admitted.job.job_id, scheduler_time_ns=SCHEDULER_T + 2)
        self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.COMPLETED)

    def test_invalid_transition_rejected(self) -> None:
        executor = RecordingInferenceExecutor()
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(gpu_resources()))
        route = sample_route()
        admitted = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert admitted.job is not None
        scheduler.schedule_once(SCHEDULER_T)
        scheduler.mark_running(admitted.job.job_id, scheduler_time_ns=SCHEDULER_T + 1)
        scheduler.complete_job(admitted.job.job_id, scheduler_time_ns=SCHEDULER_T + 2)
        with self.assertRaises(SchedulerStateTransitionError):
            scheduler.mark_running(admitted.job.job_id, scheduler_time_ns=SCHEDULER_T + 3)

    def test_dispatch_failure_retry_bounded(self) -> None:
        executor = RecordingInferenceExecutor(reject_job_ids=frozenset())
        executor.accept = False
        policy = SchedulerPolicyV1(max_attempts=1)
        scheduler = InferenceScheduler(
            executor=executor,
            policy=policy,
            resource_provider=StaticResourceProvider(gpu_resources()),
        )
        route = sample_route()
        admitted = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        assert admitted.job is not None
        scheduler.schedule_once(SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T + 1)
        self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.FAILED)

    def test_resource_release_on_complete(self) -> None:
        executor = RecordingInferenceExecutor()
        resources = cpu_resources(cpu_available=1)
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(resources))
        first = scheduler.submit_route(sample_route("ROUTE-1"), scheduler_time_ns=SCHEDULER_T)
        second = scheduler.submit_route(sample_route("ROUTE-2"), scheduler_time_ns=SCHEDULER_T)
        scheduler.schedule_once(SCHEDULER_T)
        assert first.job is not None
        scheduler.mark_running(first.job.job_id, scheduler_time_ns=SCHEDULER_T + 1)
        scheduler.complete_job(first.job.job_id, scheduler_time_ns=SCHEDULER_T + 2)
        scheduler.schedule_once(SCHEDULER_T + 3)
        self.assertEqual(len(executor.dispatches), 2)

    def test_non_executable_route_rejected(self) -> None:
        scheduler = InferenceScheduler()
        route = dataclasses.replace(
            routing_sample_route(),
            route_action=RouteAction.SUPPRESS,
            deadline_time_ns=None,
            expires_at_ns=None,
            ttl_ns=None,
        )
        result = scheduler.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        self.assertEqual(result.outcome, "ROUTE_NOT_EXECUTABLE")

    def test_scheduler_state_isolation(self) -> None:
        left = InferenceScheduler()
        right = InferenceScheduler()
        route = sample_route()
        left.submit_route(route, scheduler_time_ns=SCHEDULER_T)
        job_id = derive_inference_job_id(
            routing_decision_id=route.routing_decision_id,
            scheduler_policy_identity=left.policy.identity,
            execution_profile_id="microstructure-cpu-v1",
        )
        self.assertIsNone(right.get_job(job_id))


class LiveReplayParityTests(unittest.TestCase):
    def _run_campaign(self, clock_factory: object) -> list[str]:
        executor = RecordingInferenceExecutor()
        resources = gpu_resources()
        if callable(clock_factory):
            now = clock_factory()
        else:
            now = SCHEDULER_T
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(resources))
        routes = [
            route_with_priority(RoutingPriority.HIGH, "ROUTE-high"),
            route_with_priority(RoutingPriority.NORMAL, "ROUTE-normal"),
        ]
        for route in routes:
            scheduler.submit_route(route, scheduler_time_ns=now)
        scheduler.schedule_once(now)
        return [batch.batch_id for batch in executor.dispatches]

    def test_live_replay_parity(self) -> None:
        live_batches = self._run_campaign(SCHEDULER_T)
        replay_clock = ReplayClock(SCHEDULER_T)
        replay_batches = self._run_campaign(replay_clock.now_ns)
        self.assertEqual(live_batches, replay_batches)

    def test_job_id_parity(self) -> None:
        policy = SchedulerPolicyV1().identity
        route = sample_route()
        job_id = derive_inference_job_id(
            routing_decision_id=route.routing_decision_id,
            scheduler_policy_identity=policy,
            execution_profile_id="microstructure-cpu-v1",
        )
        replay_job_id = derive_inference_job_id(
            routing_decision_id=route.routing_decision_id,
            scheduler_policy_identity=policy,
            execution_profile_id="microstructure-cpu-v1",
        )
        self.assertEqual(job_id, replay_job_id)
