"""Full BUILD 01–11 synthetic lifecycle integration test."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ContractKind, ContractReference
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.quality import IntelligenceCapability
from market_platform_foundation.intelligence.routing import DetectionFrame, DetectionPolicyV1, EventDetectorEngine, RoutingPolicyV1, SmartRouter
from market_platform_foundation.intelligence.scheduling import (
    InferenceScheduler,
    ResourceClass,
    ResourceSnapshot,
    SchedulerJobState,
    StaticResourceProvider,
)
from market_platform_foundation.intelligence.specialists import MicrostructureInferenceExecutor
from tests.intelligence.routing_fixtures import T, quality_decision, signal, snapshot


class Build01To11LifecycleTests(unittest.TestCase):
    def test_synthetic_pipeline_through_specialist_and_persistence(self) -> None:
        repo = InMemoryIntelligenceRepository()
        snap1 = snapshot("snap-lifecycle-1", decision_time_ns=T)
        snap2 = snapshot("snap-lifecycle-2", decision_time_ns=T + 1)
        repo.put_snapshot(snap1)
        repo.put_snapshot(snap2)
        sig1 = signal(snap1, "sig-nss-1", "net_signed_share", -0.2, window_ns=300_000_000_000)
        sig2 = signal(snap2, "sig-nss-2", "net_signed_share", 0.2, window_ns=300_000_000_000)
        repo.put_signal(sig1)
        repo.put_signal(sig2)

        detector = EventDetectorEngine(DetectionPolicyV1())
        router = SmartRouter(RoutingPolicyV1())
        detector.detect(
            DetectionFrame(
                snapshot=snap1,
                signals=(sig1,),
                quality_decision=quality_decision(
                    IntelligenceCapability.QUOTES,
                    IntelligenceCapability.TRADES,
                    decision_time_ns=snap1.decision_time_ns,
                ),
            )
        )
        detection_result = detector.detect(
            DetectionFrame(
                snapshot=snap2,
                signals=(sig2,),
                quality_decision=quality_decision(
                    IntelligenceCapability.QUOTES,
                    IntelligenceCapability.TRADES,
                    decision_time_ns=snap2.decision_time_ns,
                ),
            )
        )
        self.assertEqual(len(detection_result.detections), 1)
        detection = detection_result.detections[0]
        repo.put_detection(detection)
        route = router.route(
            detection,
            quality_decision=quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.TRADES,
                decision_time_ns=detection.detected_at_ns,
            ),
        )
        repo.put_routing_decision(route)

        executor = MicrostructureInferenceExecutor(repository=repo)
        resources = ResourceSnapshot(
            captured_at_ns=T,
            cpu_slots_total=8,
            cpu_slots_available=8,
            gpu_slots_total=0,
            gpu_slots_available=0,
            vram_bytes_total=0,
            vram_bytes_available=0,
            current_residency_key="microstructure-cpu",
            supported_resource_classes=frozenset({ResourceClass.CPU}),
        )
        scheduler = InferenceScheduler(
            executor=executor,
            resource_provider=StaticResourceProvider(resources),
        )
        admitted = scheduler.submit_route(
            route,
            scheduler_time_ns=T,
            source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snap2.snapshot_id),
        )
        self.assertEqual(admitted.outcome, "ADMITTED")
        assert admitted.job is not None
        repo.put_inference_job(admitted.job)
        scheduler.schedule_once(T)
        self.assertGreaterEqual(len(executor.dispatches), 1)
        outcome = executor.execute_job(
            admitted.job,
            execution_start_time_ns=T + 1,
            completion_time_ns=T + 2,
            persist_evidence=True,
        )
        scheduler.mark_running(admitted.job.job_id, scheduler_time_ns=T + 1)
        scheduler.complete_job(admitted.job.job_id, scheduler_time_ns=T + 2)
        self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.COMPLETED)
        self.assertEqual(len(outcome.evidence), 1)
        stored = repo.get_evidence(outcome.evidence[0].evidence_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.evidence_id, outcome.evidence[0].evidence_id)


if __name__ == "__main__":
    unittest.main()
