"""Hypothesis identity determinism tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.hypotheses import derive_hypothesis_id
from market_platform_foundation.intelligence.hypotheses.policy import ShortSqueezeHypothesisPolicy
from tests.intelligence.hypothesis_fixtures import evaluate_rows, microstructure_order_flow_evidence, positioning_short_pressure_evidence


class HypothesisIdentityTests(unittest.TestCase):
    def test_same_inputs_same_id(self) -> None:
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        first = evaluate_rows(rows)
        second = evaluate_rows(rows)
        assert first.hypothesis and second.hypothesis
        self.assertEqual(first.hypothesis.hypothesis_id, second.hypothesis.hypothesis_id)

    def test_policy_change_changes_identity(self) -> None:
        from market_platform_foundation.intelligence.hypotheses.short_squeeze import ShortSqueezeHypothesisEngine
        from market_platform_foundation.intelligence.hypotheses.types import HypothesisEvaluationContext
        from tests.intelligence.hypothesis_fixtures import TEST_ADAPTER_REGISTRY, analyze_blackboard

        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository

        repo = InMemoryIntelligenceRepository()
        blackboard, relation_report = analyze_blackboard(repo, rows)
        context = HypothesisEvaluationContext(
            blackboard=blackboard,
            relation_report=relation_report,
            evidence_by_id={row.evidence_id: row for row in rows},
        )
        policy_a = ShortSqueezeHypothesisPolicy(minimum_expert_domains=2)
        policy_b = ShortSqueezeHypothesisPolicy(minimum_expert_domains=1)
        self.assertNotEqual(policy_a.policy_identity, policy_b.policy_identity)
        result_a = ShortSqueezeHypothesisEngine(policy=policy_a, adapter_registry=TEST_ADAPTER_REGISTRY).evaluate(context)
        result_b = ShortSqueezeHypothesisEngine(policy=policy_b, adapter_registry=TEST_ADAPTER_REGISTRY).evaluate(context)
        assert result_a.hypothesis and result_b.hypothesis
        self.assertNotEqual(result_a.hypothesis.hypothesis_id, result_b.hypothesis.hypothesis_id)

    def test_derive_hypothesis_id_stable(self) -> None:
        first = derive_hypothesis_id(
            hypothesis_type="SHORT_SQUEEZE_SETUP",
            blackboard_id="BB-1",
            snapshot_id="snap-1",
            engine_id="short-squeeze-hypothesis-engine",
            engine_version="1",
            policy_identity="SSPOL-ABC",
            scope_key="INST-1",
        )
        second = derive_hypothesis_id(
            hypothesis_type="SHORT_SQUEEZE_SETUP",
            blackboard_id="BB-1",
            snapshot_id="snap-1",
            engine_id="short-squeeze-hypothesis-engine",
            engine_version="1",
            policy_identity="SSPOL-ABC",
            scope_key="INST-1",
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("HYP-"))


if __name__ == "__main__":
    unittest.main()
