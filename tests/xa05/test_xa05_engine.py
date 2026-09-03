"""XA-05 deterministic state construction tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.enums import AnalyticalDomain
from market_platform_foundation.xa05.engine import CrossAssetStateEngine, StateConstructionConfig
from market_platform_foundation.xa05.enums import EvidenceAvailabilityStatus, StateDimensionId
from market_platform_foundation.xa05.errors import Xa05Error
from market_platform_foundation.xa05.queries import get_dimension

from tests.xa05.test_xa05_fixtures import build_engine, populate_repository


class Xa05EngineTests(unittest.TestCase):
    def test_deterministic_state_construction(self) -> None:
        engine = build_engine()
        decision_time = "2026-08-20T00:00:00Z"
        first = engine.construct_state(decision_time=decision_time, construction_time=decision_time)
        second = engine.construct_state(decision_time=decision_time, construction_time=decision_time)
        self.assertEqual(first.state_id, second.state_id)
        self.assertEqual(first.provenance.semantic_fingerprint, second.provenance.semantic_fingerprint)
        self.assertEqual(first.dimensions, second.dimensions)

    def test_missing_scalar_is_not_zero(self) -> None:
        engine = build_engine()
        state = engine.construct_state(
            decision_time="2020-01-01T00:00:00Z",
            construction_time="2020-01-01T00:00:00Z",
        )
        policy = get_dimension(state, StateDimensionId.POLICY_RATE_LEVEL)
        assert policy is not None
        self.assertEqual(policy.evidence_status, EvidenceAvailabilityStatus.MISSING)
        self.assertIsNone(policy.numeric_features.get("policy_rate_percent"))

    def test_unknown_classifier_version_rejected(self) -> None:
        engine = build_engine()
        with self.assertRaises(Xa05Error):
            engine.construct_state(
                decision_time="2026-08-20T00:00:00Z",
                construction_time="2026-08-20T00:00:00Z",
                config=StateConstructionConfig(yield_curve_classifier_version="imp-xa05-unknown"),
            )

    def test_analytical_domains_preserved(self) -> None:
        engine = build_engine()
        state = engine.construct_state(
            decision_time="2026-08-20T00:00:00Z",
            construction_time="2026-08-20T00:00:00Z",
        )
        self.assertIn(AnalyticalDomain.RATES, state.analytical_domains)
        self.assertIn(AnalyticalDomain.MONETARY_RESERVE, state.analytical_domains)

    def test_provenance_traceability(self) -> None:
        repo, _state = populate_repository()
        engine = CrossAssetStateEngine(repo)
        constructed = engine.construct_state(
            decision_time="2026-08-20T00:00:00Z",
            construction_time="2026-08-20T00:00:00Z",
        )
        for ref in constructed.evidence_references:
            scalar = repo.get_scalar_observation(ref.observation_id)
            envelope = repo.get_admission_envelope(ref.observation_id)
            self.assertTrue(scalar is not None or envelope is not None)
        self.assertEqual(
            set(constructed.provenance.evidence_observation_ids),
            {ref.observation_id for ref in constructed.evidence_references},
        )

    def test_classification_version_in_reproducibility(self) -> None:
        engine = build_engine()
        state = engine.construct_state(
            decision_time="2026-08-20T00:00:00Z",
            construction_time="2026-08-20T00:00:00Z",
        )
        self.assertIn("yield_curve", state.provenance.classifier_versions)
        curve = get_dimension(state, StateDimensionId.RATES_CURVE_CONFIGURATION)
        assert curve is not None
        self.assertEqual(curve.definition_version, "imp-xa05-yield-curve-v1")


if __name__ == "__main__":
    unittest.main()
