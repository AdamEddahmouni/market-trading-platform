"""BUILD 11 microstructure specialist analysis tests."""

from __future__ import annotations

import dataclasses
import unittest

from market_platform_foundation.intelligence.contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    ExpertDomain,
    ForecastV1,
    HypothesisV1,
    InferenceJobV1,
    QualityState,
    QualitySummary,
    RoutingPriority,
    RouteAction,
    RoutingDecisionV1,
    SemanticEventType,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence.errors import RepositoryConflictError
from market_platform_foundation.intelligence.specialists import (
    MicrostructureSpecialist,
    MicrostructureSpecialistPolicyV1,
    SpecialistDiagnosticCode,
    SpecialistExecutionStatus,
    derive_microstructure_evidence_id,
    resolve_specialist_context,
)
from tests.intelligence.routing_fixtures import T, signal, snapshot
from tests.intelligence.specialists_fixtures import (
    liquidity_detection,
    manual_detection,
    order_flow_detection,
    replace_detection_signals,
    routed_microstructure_job,
)
from tests.intelligence.test_persistence_fixtures import sample_forecast


class MicrostructureSpecialistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.specialist = MicrostructureSpecialist()

    def _context(self, *, bearish: bool = False, liquidity: bool = False):
        if liquidity:
            _, snap2, sig_prev, sig_curr, detection = liquidity_detection()
        else:
            _, snap2, sig_prev, sig_curr, detection = order_flow_detection(
                previous_nss=0.35 if bearish else -0.35,
                current_nss=-0.42 if bearish else 0.42,
            )
        repo, route, job = routed_microstructure_job(
            detection,
            snap2,
            signals=(sig_prev, sig_curr),
        )
        context, failure = resolve_specialist_context(job=job, repository=repo)
        assert failure is None and context is not None
        return context, repo, job, route, detection

    def test_bullish_order_flow_evidence(self) -> None:
        context, _, _, _, detection = self._context()
        result = self.specialist.analyze(context)
        self.assertEqual(result.status, SpecialistExecutionStatus.COMPLETED)
        self.assertEqual(len(result.evidence), 1)
        evidence = result.evidence[0]
        self.assertEqual(evidence.assessment["transition"], "NEGATIVE_TO_POSITIVE")
        self.assertEqual(evidence.assessment["previous_nss"], -0.35)
        self.assertEqual(evidence.assessment["current_nss"], 0.42)
        self.assertAlmostEqual(evidence.assessment["delta_nss"], 0.77)
        self.assertEqual(len(evidence.source_signal_refs), 2)
        self.assertNotIsInstance(evidence, ForecastV1)
        self.assertNotIsInstance(evidence, HypothesisV1)
        self.assertIn("ORDER_FLOW_TRANSITION", evidence.assessment["evidence_kind"])
        self.assertEqual(detection.semantic_event_type, SemanticEventType.ORDER_FLOW_REVERSAL)

    def test_bearish_order_flow_evidence(self) -> None:
        context, _, _, _, _ = self._context(bearish=True)
        result = self.specialist.analyze(context)
        self.assertEqual(result.status, SpecialistExecutionStatus.COMPLETED)
        self.assertEqual(result.evidence[0].assessment["transition"], "POSITIVE_TO_NEGATIVE")

    def test_liquidity_evidence(self) -> None:
        context, _, _, _, _ = self._context(liquidity=True)
        result = self.specialist.analyze(context)
        self.assertEqual(result.status, SpecialistExecutionStatus.COMPLETED)
        evidence = result.evidence[0]
        self.assertEqual(evidence.assessment["evidence_kind"], "LIQUIDITY_STRESS")
        self.assertEqual(evidence.assessment["previous_spread_bps"], 40.0)
        self.assertEqual(evidence.assessment["current_spread_bps"], 60.0)
        self.assertEqual(evidence.assessment["spread_delta_bps"], 20.0)

    def test_wrong_domain(self) -> None:
        context, _, _, _, _ = self._context()
        wrong_job = dataclasses.replace(context.job, expert_domain=ExpertDomain.DERIVATIVES)
        wrong_context = dataclasses.replace(context, job=wrong_job)
        result = self.specialist.analyze(wrong_context)
        self.assertEqual(result.status, SpecialistExecutionStatus.FAILED)
        self.assertEqual(result.diagnostics[0].code, SpecialistDiagnosticCode.UNSUPPORTED_DOMAIN)

    def test_unsupported_semantic_event(self) -> None:
        context, _, _, _, _ = self._context()
        borrow_detection = manual_detection(
            event_type=SemanticEventType.BORROW_CHANGE,
            signal_refs=(),
            snapshot_id=context.snapshot.snapshot_id,
        )
        wrong_context = dataclasses.replace(context, detection=borrow_detection)
        result = self.specialist.analyze(wrong_context)
        self.assertEqual(result.status, SpecialistExecutionStatus.FAILED)
        self.assertEqual(result.diagnostics[0].code, SpecialistDiagnosticCode.UNSUPPORTED_SEMANTIC_EVENT)

    def test_missing_source_signal(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        repo, route, job = routed_microstructure_job(detection, snap2, signals=(sig_prev,))
        context, failure = resolve_specialist_context(job=job, repository=repo)
        self.assertIsNone(context)
        assert failure is not None
        self.assertEqual(failure.status, SpecialistExecutionStatus.FAILED)
        self.assertEqual(failure.diagnostics[0].code, SpecialistDiagnosticCode.MISSING_REQUIRED_SOURCE)

    def test_wrong_signal_type(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        spread = signal(snap2, "sig-spread-wrong", "spread_bps", 10.0)
        bad_detection = replace_detection_signals(detection, (sig_prev, spread))
        repo, _, job = routed_microstructure_job(bad_detection, snap2, signals=(sig_prev, spread))
        context, failure = resolve_specialist_context(job=job, repository=repo)
        assert context is not None
        result = self.specialist.analyze(context)
        self.assertEqual(result.status, SpecialistExecutionStatus.FAILED)
        self.assertEqual(result.diagnostics[0].code, SpecialistDiagnosticCode.WRONG_SIGNAL_TYPE)

    def test_source_snapshot_mismatch(self) -> None:
        context, repo, job, _, _ = self._context()
        bad_job = dataclasses.replace(
            job,
            source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id="snap-wrong"),
        )
        _, failure = resolve_specialist_context(job=bad_job, repository=repo)
        assert failure is not None
        self.assertEqual(failure.diagnostics[0].code, SpecialistDiagnosticCode.SOURCE_SNAPSHOT_MISMATCH)

    def test_route_detection_mismatch(self) -> None:
        context, repo, job, route, _ = self._context()
        bad_job = dataclasses.replace(
            job,
            detection_ref=ContractReference(kind=ContractKind.DETECTION.value, id="DET-other"),
        )
        _, failure = resolve_specialist_context(job=bad_job, repository=repo)
        assert failure is not None
        self.assertEqual(failure.diagnostics[0].code, SpecialistDiagnosticCode.REFERENCE_RESOLUTION_FAILED)

    def test_quality_good(self) -> None:
        context, _, _, _, _ = self._context()
        result = self.specialist.analyze(context)
        self.assertEqual(result.evidence[0].quality.state, QualityState.GOOD)

    def test_quality_degraded(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection(quality=QualityState.DEGRADED)
        repo, _, job = routed_microstructure_job(detection, snap2, signals=(sig_prev, sig_curr))
        context, _ = resolve_specialist_context(job=job, repository=repo)
        assert context is not None
        result = self.specialist.analyze(context)
        self.assertEqual(result.evidence[0].quality.state, QualityState.DEGRADED)

    def test_quality_invalid(self) -> None:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        invalid_detection = dataclasses.replace(
            detection,
            quality=QualitySummary(state=QualityState.INVALID),
        )
        repo = InMemoryIntelligenceRepository()
        repo.put_snapshot(snap2)
        for row in (sig_prev, sig_curr):
            if repo.get_snapshot(row.source_snapshot_ref.id) is None:
                repo.put_snapshot(snapshot(row.source_snapshot_ref.id, decision_time_ns=row.as_of_time_ns))
            repo.put_signal(row)
        repo.put_detection(invalid_detection)
        route = RoutingDecisionV1(
            routing_decision_id="ROUTE-invalid",
            schema_version="1",
            detection_ref=ContractReference(kind=ContractKind.DETECTION.value, id=invalid_detection.detection_id),
            decision_time_ns=T,
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            route_action=RouteAction.ROUTE,
            priority=RoutingPriority.HIGH,
            reason_codes=("FIXTURE",),
            required_capabilities=("QUOTES", "TRADES"),
            optional_capabilities=(),
            deadline_time_ns=T + 5_000_000_000,
            expires_at_ns=T + 30_000_000_000,
            ttl_ns=30_000_000_000,
            quality=QualitySummary(state=QualityState.INVALID),
            router_lineage=ComponentLineage(component_id="smart-router", component_version="1"),
        )
        repo.put_routing_decision(route)
        job = InferenceJobV1(
            job_id="IJOB-invalid-quality",
            schema_version="1",
            routing_decision_ref=ContractReference(kind=ContractKind.ROUTING_DECISION.value, id="ROUTE-invalid"),
            detection_ref=ContractReference(kind=ContractKind.DETECTION.value, id=invalid_detection.detection_id),
            source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snap2.snapshot_id),
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            priority=RoutingPriority.HIGH,
            decision_time_ns=T,
            submitted_at_ns=T,
            deadline_time_ns=T + 5_000_000_000,
            expires_at_ns=T + 30_000_000_000,
            required_capabilities=("QUOTES", "TRADES"),
            execution_profile_id="microstructure-cpu-v1",
            batch_key="microstructure-specialist-v1",
            residency_key="microstructure-cpu",
            adapter_key=None,
            scheduler_policy_identity="SCHPOL-test",
            scheduler_lineage=ComponentLineage(component_id="inference-scheduler", component_version="1"),
        )
        _, failure = resolve_specialist_context(job=job, repository=repo)
        assert failure is not None
        self.assertEqual(failure.diagnostics[0].code, SpecialistDiagnosticCode.QUALITY_REJECTED)

    def test_evidence_identity_stable(self) -> None:
        first_context, _, _, _, _ = self._context()
        second_context, _, _, _, _ = self._context()
        first = self.specialist.analyze(first_context).evidence[0]
        second = self.specialist.analyze(second_context).evidence[0]
        self.assertEqual(first.evidence_id, second.evidence_id)

    def test_input_order_irrelevant(self) -> None:
        context, _, _, _, _ = self._context()
        shuffled = dataclasses.replace(context, signals=tuple(reversed(context.signals)))
        first = self.specialist.analyze(context).evidence[0]
        second = self.specialist.analyze(shuffled).evidence[0]
        self.assertEqual(first, second)

    def test_late_same_snapshot_signal_does_not_change_output(self) -> None:
        context, repo, _, _, _ = self._context()
        baseline = self.specialist.analyze(context).evidence[0]
        late = signal(context.snapshot, "sig-late-leak", "net_signed_share", 0.99, window_ns=300_000_000_000)
        repo.put_signal(late)
        again = self.specialist.analyze(context).evidence[0]
        self.assertEqual(baseline, again)

    def test_no_baseline_forecast_anchoring(self) -> None:
        context, repo, _, _, _ = self._context()
        repo.put_forecast(sample_forecast("fc-anchor", probability=0.99))
        result = self.specialist.analyze(context)
        self.assertEqual(len(result.evidence), 1)

    def test_evidence_identity_excludes_computed_output(self) -> None:
        context, _, job, route, detection = self._context()
        evidence = self.specialist.analyze(context).evidence[0]
        identity = derive_microstructure_evidence_id(
            job=job,
            route=route,
            detection=detection,
            evidence_kind=evidence.assessment["evidence_kind"],
            source_signal_refs=evidence.source_signal_refs,
            specialist_component_id=self.specialist.component_id,
            specialist_component_version=self.specialist.component_version,
            specialist_policy_identity=self.specialist.policy.identity,
            evidence_identity_version=self.specialist.policy.evidence_identity_version,
        )
        self.assertEqual(evidence.evidence_id, identity)

    def test_evidence_conflict_detects_nondeterminism(self) -> None:
        context, repo, _, _, _ = self._context()
        evidence = self.specialist.analyze(context).evidence[0]
        repo.put_evidence(evidence)
        tampered = dataclasses.replace(
            evidence,
            assessment={**evidence.assessment, "delta_nss": 999.0},
        )
        with self.assertRaises(RepositoryConflictError):
            repo.put_evidence(tampered)


if __name__ == "__main__":
    unittest.main()
