"""Hypothesis persistence tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence.errors import RepositoryConflictError
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult
from market_platform_foundation.intelligence.hypotheses import HypothesisEvaluationService
from market_platform_foundation.intelligence.hypotheses.registry import HypothesisEngineRegistry
from market_platform_foundation.intelligence.hypotheses.short_squeeze import ShortSqueezeHypothesisEngine
from tests.intelligence.hypothesis_fixtures import TEST_ADAPTER_REGISTRY, analyze_blackboard, microstructure_order_flow_evidence, positioning_short_pressure_evidence


def _test_service(repo) -> HypothesisEvaluationService:
    engine = ShortSqueezeHypothesisEngine(adapter_registry=TEST_ADAPTER_REGISTRY)
    registry = HypothesisEngineRegistry(engines={"SHORT_SQUEEZE_SETUP": engine})
    return HypothesisEvaluationService(repository=repo, engine_registry=registry)


class HypothesisPersistenceTests(unittest.TestCase):
    def test_idempotent_put(self) -> None:
        repo = InMemoryIntelligenceRepository()
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        blackboard, relation_report = analyze_blackboard(repo, rows)
        service = _test_service(repo)
        result = service.evaluate_short_squeeze(
            blackboard=blackboard,
            relation_report=relation_report,
            persist=True,
        )
        assert result.hypothesis is not None
        second = repo.put_hypothesis(result.hypothesis)
        self.assertEqual(second, RepositoryPutResult.ALREADY_PRESENT)
        loaded = repo.get_hypothesis(result.hypothesis.hypothesis_id)
        assert loaded is not None
        self.assertEqual(loaded.supporting_evidence_ids, result.hypothesis.supporting_evidence_ids)
        self.assertEqual(loaded.invalidation_conditions, result.hypothesis.invalidation_conditions)

    def test_conflict_on_same_id_different_content(self) -> None:
        repo = InMemoryIntelligenceRepository()
        rows = (
            positioning_short_pressure_evidence(evidence_id="EVID-P1", signal_id="SIG-P1"),
            microstructure_order_flow_evidence(
                evidence_id="EVID-M1",
                transition="NEGATIVE_TO_POSITIVE",
                signal_id="SIG-M1",
            ),
        )
        blackboard, relation_report = analyze_blackboard(repo, rows)
        service = _test_service(repo)
        result = service.evaluate_short_squeeze(
            blackboard=blackboard,
            relation_report=relation_report,
            persist=True,
        )
        assert result.hypothesis is not None
        from dataclasses import replace

        mutated = replace(result.hypothesis, explanation="mutated claim")
        with self.assertRaises(RepositoryConflictError):
            repo.put_hypothesis(mutated)


if __name__ == "__main__":
    unittest.main()
