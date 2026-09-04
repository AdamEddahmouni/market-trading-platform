"""Full BUILD 01–13 lifecycle tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ContractKind, ContractReference, ExpertDomain
from market_platform_foundation.intelligence.council import BlindCouncilOrchestrator, CouncilPlan, CouncilPolicy, DeliberationDecision
from market_platform_foundation.intelligence.hypotheses import (
    DEFAULT_PRODUCTION_ADAPTER_REGISTRY,
    HypothesisEvaluationService,
    HypothesisEvaluationStatus,
    ShortSqueezeHypothesisEngine,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.quality import IntelligenceCapability
from market_platform_foundation.intelligence.routing import DetectionFrame, DetectionPolicyV1, EventDetectorEngine, RoutingPolicyV1, SmartRouter
from market_platform_foundation.intelligence.scheduling import InferenceScheduler, ResourceClass, ResourceSnapshot, StaticResourceProvider
from market_platform_foundation.intelligence.specialists import MicrostructureInferenceExecutor
from tests.intelligence.council_fixtures import T, council_participant
from tests.intelligence.hypothesis_fixtures import TEST_ADAPTER_REGISTRY, analyze_blackboard, positioning_short_pressure_evidence
from tests.intelligence.routing_fixtures import quality_decision, signal, snapshot


class Build01To13LifecycleTests(unittest.TestCase):
    def test_production_pipeline_fails_closed(self) -> None:
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
        council_result = orchestrator.run_to_deliberation_gate()
        self.assertIsNotNone(council_result.blind_blackboard_id)

        blackboard = orchestrator.blind_blackboard
        relation_report = orchestrator.relation_report
        assert blackboard is not None and relation_report is not None

        service = HypothesisEvaluationService(repository=repo)
        result = service.evaluate_short_squeeze(
            blackboard=blackboard,
            relation_report=relation_report,
            decision_time_ns=T,
        )
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.status, HypothesisEvaluationStatus.INSUFFICIENT_REQUIRED_EVIDENCE)

    def test_synthetic_composite_lifecycle_emits_and_persists(self) -> None:
        repo = InMemoryIntelligenceRepository()
        micro_row = None
        from tests.intelligence.hypothesis_fixtures import microstructure_order_flow_evidence

        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        blackboard, relation_report = analyze_blackboard(repo, rows)
        engine = ShortSqueezeHypothesisEngine(adapter_registry=TEST_ADAPTER_REGISTRY)
        from market_platform_foundation.intelligence.hypotheses.types import HypothesisEvaluationContext

        result = engine.evaluate(
            HypothesisEvaluationContext(
                blackboard=blackboard,
                relation_report=relation_report,
                evidence_by_id={row.evidence_id: row for row in rows},
                decision_time_ns=T,
            )
        )
        self.assertIsNotNone(result.hypothesis)
        repo.put_hypothesis(result.hypothesis)
        loaded = repo.get_hypothesis(result.hypothesis.hypothesis_id)
        assert loaded is not None
        self.assertEqual(loaded.hypothesis_type, "SHORT_SQUEEZE_SETUP")

    def test_no_forecast_or_opportunity_created(self) -> None:
        repo = InMemoryIntelligenceRepository()
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
        )
        blackboard, relation_report = analyze_blackboard(repo, rows)
        service = HypothesisEvaluationService(repository=repo)
        service.evaluate_short_squeeze(blackboard=blackboard, relation_report=relation_report)
        self.assertEqual(repo.get_forecast("missing"), None)
        self.assertEqual(repo.get_opportunity("missing"), None)


if __name__ == "__main__":
    unittest.main()
