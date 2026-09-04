"""Full BUILD 01–12 production-compatible lifecycle test."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ContractKind, ContractReference, ExpertDomain
from market_platform_foundation.intelligence.council import (
    BlindCouncilOrchestrator,
    CouncilPlan,
    CouncilPolicy,
    DeliberationDecision,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.quality import IntelligenceCapability
from market_platform_foundation.intelligence.routing import DetectionFrame, DetectionPolicyV1, EventDetectorEngine, RoutingPolicyV1, SmartRouter
from market_platform_foundation.intelligence.scheduling import (
    InferenceScheduler,
    ResourceClass,
    ResourceSnapshot,
    StaticResourceProvider,
)
from market_platform_foundation.intelligence.specialists import MicrostructureInferenceExecutor
from tests.intelligence.council_fixtures import T, council_participant
from tests.intelligence.routing_fixtures import quality_decision, signal, snapshot


class Build01To12LifecycleTests(unittest.TestCase):
    def test_production_microstructure_council_lifecycle(self) -> None:
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
        assert admitted.job is not None
        repo.put_inference_job(admitted.job)
        scheduler.schedule_once(T)
        outcome = executor.execute_job(
            admitted.job,
            execution_start_time_ns=T + 1,
            completion_time_ns=T + 2,
            persist_evidence=True,
        )

        plan = CouncilPlan.create(
            source_snapshot_id=snap2.snapshot_id,
            participants=(
                council_participant(
                    expert_domain=ExpertDomain.MICROSTRUCTURE,
                    job_id=admitted.job.job_id,
                ),
            ),
            policy=CouncilPolicy(),
            decision_time_ns=T,
        )
        orchestrator = BlindCouncilOrchestrator(plan=plan, repository=repo)
        orchestrator.start_blind_phase()
        from market_platform_foundation.intelligence.council.models import ParticipantOutcome
        from market_platform_foundation.intelligence.specialists.models import SpecialistExecutionStatus

        orchestrator.record_participant_terminal(
            ParticipantOutcome(
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                job_id=admitted.job.job_id,
                status=SpecialistExecutionStatus.COMPLETED,
                evidence_refs=tuple(row.evidence_id for row in outcome.evidence),
            )
        )
        result = orchestrator.run_to_deliberation_gate()
        self.assertIsNotNone(result.blind_blackboard_id)
        self.assertEqual(result.deliberation_decision, DeliberationDecision.INSUFFICIENT_EVIDENCE)
        self.assertEqual(len(outcome.evidence), 1)


if __name__ == "__main__":
    unittest.main()
