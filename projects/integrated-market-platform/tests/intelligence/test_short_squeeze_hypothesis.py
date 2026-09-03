"""Short squeeze composite hypothesis engine tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ExpertDomain, QualityState, QualitySummary
from market_platform_foundation.intelligence.council import BlackboardPhase, publish_blackboard_snapshot
from market_platform_foundation.intelligence.hypotheses import (
    DEFAULT_PRODUCTION_ADAPTER_REGISTRY,
    HypothesisEvaluationStatus,
    HypothesisEvidencePhasePolicy,
    ShortSqueezeHypothesisEngine,
    ShortSqueezeHypothesisPolicy,
)
from market_platform_foundation.intelligence.hypotheses.adapters import HypothesisEvidenceAdapterRegistry, MicrostructureShortSqueezeEvidenceAdapter
from tests.intelligence.council_fixtures import completed_outcome, synthetic_evidence
from tests.intelligence.hypothesis_fixtures import (
    TEST_ADAPTER_REGISTRY,
    evaluate_rows,
    microstructure_order_flow_evidence,
    positioning_short_pressure_evidence,
)


class ShortSqueezeHypothesisTests(unittest.TestCase):
    def test_production_microstructure_only_no_emit(self) -> None:
        row = microstructure_order_flow_evidence(
            evidence_id="EVID-M1",
            transition="NEGATIVE_TO_POSITIVE",
        )
        result = evaluate_rows((row,), adapter_registry=DEFAULT_PRODUCTION_ADAPTER_REGISTRY)
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.status, HypothesisEvaluationStatus.INSUFFICIENT_REQUIRED_EVIDENCE)
        self.assertIn("SHORT_PRESSURE", str(result.coverage.get("missing_required_factors", ())))

    def test_missing_activation(self) -> None:
        row = positioning_short_pressure_evidence(evidence_id="EVID-P1")
        result = evaluate_rows((row,))
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.status, HypothesisEvaluationStatus.INSUFFICIENT_REQUIRED_EVIDENCE)

    def test_synthetic_core_support_emits(self) -> None:
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        result = evaluate_rows(rows)
        self.assertIsNotNone(result.hypothesis)
        self.assertEqual(result.status, HypothesisEvaluationStatus.EMITTED)
        self.assertIn("EVID-P1", result.hypothesis.supporting_evidence_ids)
        self.assertIn("EVID-M1", result.hypothesis.supporting_evidence_ids)
        self.assertIsNone(result.hypothesis.support_score)
        self.assertTrue(result.hypothesis.invalidation_conditions)

    def test_same_source_independence_rejection(self) -> None:
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-SHARED"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-SHARED",
            ),
        )
        result = evaluate_rows(rows)
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.status, HypothesisEvaluationStatus.INSUFFICIENT_INDEPENDENCE)

    def test_same_domain_only_rejection(self) -> None:
        rows = (
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M2",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M2",
            ),
        )
        result = evaluate_rows(rows)
        self.assertIsNone(result.hypothesis)
        self.assertIn(
            result.status,
            {
                HypothesisEvaluationStatus.INSUFFICIENT_REQUIRED_EVIDENCE,
                HypothesisEvaluationStatus.INSUFFICIENT_DOMAIN_COVERAGE,
            },
        )

    def test_negative_activation_contradicted(self) -> None:
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="POSITIVE_TO_NEGATIVE",
                signal_id="SIG-M1",
            ),
        )
        result = evaluate_rows(rows)
        self.assertIsNone(result.hypothesis)
        self.assertEqual(result.status, HypothesisEvaluationStatus.CONTRADICTED)

    def test_contested_activation_emits_contested(self) -> None:
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M2",
                transition="POSITIVE_TO_NEGATIVE",
                signal_id="SIG-M2",
            ),
        )
        result = evaluate_rows(rows)
        self.assertIsNotNone(result.hypothesis)
        self.assertEqual(result.status, HypothesisEvaluationStatus.EMITTED_CONTESTED)
        self.assertTrue(result.hypothesis.contradicting_evidence_ids)

    def test_optional_amplifiers_do_not_block(self) -> None:
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        result = evaluate_rows(rows)
        self.assertEqual(result.status, HypothesisEvaluationStatus.EMITTED)
        receipt = result.coverage["factor_receipt"]
        self.assertEqual(receipt["LIQUIDITY_CONSTRAINT"], "ABSENT")

    def test_false_consensus_does_not_emit(self) -> None:
        rows = tuple(
            synthetic_evidence(
                evidence_id=f"EVID-{index}",
                expert_domain=ExpertDomain.POSITIONING_BORROW if index == 0 else ExpertDomain.MICROSTRUCTURE,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="POSITIVE",
                signal_refs=(),
            )
            for index in range(5)
        )
        result = evaluate_rows(rows)
        self.assertIsNone(result.hypothesis)

    def test_production_registry_only_microstructure_adapter(self) -> None:
        registry = DEFAULT_PRODUCTION_ADAPTER_REGISTRY
        self.assertEqual(len(registry.adapters), 1)
        self.assertIsInstance(registry.adapters[0], MicrostructureShortSqueezeEvidenceAdapter)

    def test_blind_only_rejects_deliberation_blackboard(self) -> None:
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        engine = ShortSqueezeHypothesisEngine(
            policy=ShortSqueezeHypothesisPolicy(
                evidence_phase_policy=HypothesisEvidencePhasePolicy.BLIND_ONLY,
            )
        )
        from tests.intelligence.hypothesis_fixtures import analyze_blackboard
        from market_platform_foundation.intelligence.hypotheses.types import HypothesisEvaluationContext
        from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository

        repo = InMemoryIntelligenceRepository()
        blackboard, relation_report = analyze_blackboard(repo, rows)
        deliberation_bb = publish_blackboard_snapshot(
            council_id="COUNCIL-HYP",
            source_snapshot_id=rows[0].snapshot_id,
            evidence_refs=blackboard.evidence_refs,
            participant_outcomes=blackboard.participant_outcomes,
            phase=BlackboardPhase.DELIBERATION_PASS,
            revision=2,
            resolved_evidence={row.evidence_id: row for row in rows},
        )
        result = engine.evaluate(
            HypothesisEvaluationContext(
                blackboard=deliberation_bb,
                relation_report=relation_report,
                evidence_by_id={row.evidence_id: row for row in rows},
            )
        )
        self.assertEqual(result.status, HypothesisEvaluationStatus.INVALID_INPUT)

    def test_degraded_required_evidence_policy(self) -> None:
        from dataclasses import replace

        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        degraded_rows = tuple(
            replace(row, quality=QualitySummary(state=QualityState.DEGRADED))
            for row in rows
        )
        engine = ShortSqueezeHypothesisEngine(
            adapter_registry=TEST_ADAPTER_REGISTRY,
            policy=ShortSqueezeHypothesisPolicy(allow_degraded_evidence=False),
        )
        from tests.intelligence.hypothesis_fixtures import analyze_blackboard
        from market_platform_foundation.intelligence.hypotheses.types import HypothesisEvaluationContext
        from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository

        repo = InMemoryIntelligenceRepository()
        blackboard, relation_report = analyze_blackboard(repo, degraded_rows)
        result = engine.evaluate(
            HypothesisEvaluationContext(
                blackboard=blackboard,
                relation_report=relation_report,
                evidence_by_id={row.evidence_id: row for row in degraded_rows},
            )
        )
        self.assertIsNone(result.hypothesis)


if __name__ == "__main__":
    unittest.main()
