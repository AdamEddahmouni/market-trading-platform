"""Full BUILD 01–10 synthetic lifecycle integration test."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    SemanticEventType,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.replay import ReplayPipelineConfig
from market_platform_foundation.intelligence.routing import (
    DetectionFrame,
    DetectionPolicyV1,
    EventDetectorEngine,
    RoutingPolicyV1,
    SmartRouter,
)
from market_platform_foundation.intelligence.scheduling import (
    InferenceScheduler,
    RecordingInferenceExecutor,
    ResourceClass,
    ResourceSnapshot,
    SchedulerJobState,
    StaticResourceProvider,
)
from tests.intelligence.routing_fixtures import T, quality_decision, signal, snapshot
from market_platform_foundation.intelligence.quality import IntelligenceCapability


class Build01To10LifecycleTests(unittest.TestCase):
    def test_synthetic_pipeline_through_scheduler(self) -> None:
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

        executor = RecordingInferenceExecutor()
        resources = ResourceSnapshot(
            captured_at_ns=T,
            cpu_slots_total=8,
            cpu_slots_available=8,
            gpu_slots_total=1,
            gpu_slots_available=1,
            vram_bytes_total=16 * 1024**3,
            vram_bytes_available=16 * 1024**3,
            supported_resource_classes=frozenset({ResourceClass.CPU, ResourceClass.GPU}),
        )
        scheduler = InferenceScheduler(executor=executor, resource_provider=StaticResourceProvider(resources))
        if route.route_action.value == "ROUTE":
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
            scheduler.mark_running(admitted.job.job_id, scheduler_time_ns=T + 1)
            scheduler.complete_job(admitted.job.job_id, scheduler_time_ns=T + 2)
            self.assertEqual(scheduler.get_job_state(admitted.job.job_id), SchedulerJobState.COMPLETED)
            stored_job = repo.get_inference_job(admitted.job.job_id)
            self.assertIsNotNone(stored_job)

    def test_replay_pipeline_build_09_enabled(self) -> None:
        config = ReplayPipelineConfig(enable_build_09=True)
        self.assertTrue(config.enable_build_09)


class Build09RegressionGuard(unittest.TestCase):
    def test_detection_semantic_types_unchanged(self) -> None:
        self.assertIn(SemanticEventType.ORDER_FLOW_REVERSAL, SemanticEventType)
