"""Hypothesis replay parity tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.hypotheses import HypothesisEvaluationStatus
from tests.intelligence.hypothesis_fixtures import evaluate_rows, microstructure_order_flow_evidence, positioning_short_pressure_evidence


class HypothesisReplayTests(unittest.TestCase):
    def test_same_blackboard_same_result(self) -> None:
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
        self.assertEqual(first.status, second.status)
        if first.hypothesis and second.hypothesis:
            self.assertEqual(first.hypothesis.hypothesis_id, second.hypothesis.hypothesis_id)
            self.assertEqual(first.hypothesis.supporting_evidence_ids, second.hypothesis.supporting_evidence_ids)
            self.assertEqual(first.hypothesis.contradicting_evidence_ids, second.hypothesis.contradicting_evidence_ids)

    def test_input_order_independent(self) -> None:
        rows_a = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        rows_b = tuple(reversed(rows_a))
        first = evaluate_rows(rows_a)
        second = evaluate_rows(rows_b)
        self.assertEqual(first.status, second.status)
        assert first.hypothesis and second.hypothesis
        self.assertEqual(first.hypothesis.hypothesis_id, second.hypothesis.hypothesis_id)

    def test_counterfactual_repeatable(self) -> None:
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
        )
        first = evaluate_rows(rows)
        second = evaluate_rows(rows)
        self.assertEqual(first.status, HypothesisEvaluationStatus.INSUFFICIENT_REQUIRED_EVIDENCE)
        self.assertEqual(first.status, second.status)


if __name__ == "__main__":
    unittest.main()
