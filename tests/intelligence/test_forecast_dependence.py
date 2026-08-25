"""Forecast dependence and pooling tests (BUILD 14)."""

from __future__ import annotations

import math
import unittest

from market_platform_foundation.intelligence.fusion import (
    ForecastFusionManifest,
    FusionEngine,
    FusionPolicy,
    ForecastProvenanceResolver,
    within_group_probability,
    across_group_probability,
    ForecastDependenceGroup,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.fusion_fixtures import (
    production_contributor,
    sample_snapshot,
    synthetic_production_forecast,
)
from tests.intelligence.test_baseline_fixtures import default_horizon, default_target


class ForecastDependenceTests(unittest.TestCase):
    def test_false_consensus_clone_case(self) -> None:
        snapshot = sample_snapshot()
        repo = InMemoryIntelligenceRepository()
        clones = [
            synthetic_production_forecast(
                forecast_id=f"FCST-CLONE-{index}",
                snapshot=snapshot,
                probability=0.9,
                signal_ids=("SIG-SHARED",),
                forecast_family_key="family-shared",
            )
            for index in range(3)
        ]
        independent = synthetic_production_forecast(
            forecast_id="FCST-IND-1",
            snapshot=snapshot,
            probability=0.2,
            signal_ids=("SIG-IND",),
            forecast_family_key="family-independent",
        )
        manifest = ForecastFusionManifest.create(
            snapshot_id=snapshot.snapshot_id,
            target=default_target(),
            horizon=default_horizon(),
            decision_time_ns=snapshot.decision_time_ns,
            scope=snapshot.scope,
            contributors=[production_contributor(row) for row in (*clones, independent)],
            fusion_policy=FusionPolicy(),
        )
        engine = FusionEngine(ForecastProvenanceResolver(repo))
        result = engine.fuse(manifest)
        assert result.raw_probability is not None
        self.assertAlmostEqual(result.raw_probability, 0.55)
        self.assertEqual(len(result.dependence_groups), 2)

    def test_clone_addition_invariance(self) -> None:
        snapshot = sample_snapshot()
        base = [
            synthetic_production_forecast(
                forecast_id=f"FCST-CLONE-{index}",
                snapshot=snapshot,
                probability=0.9,
                signal_ids=("SIG-SHARED",),
                forecast_family_key="family-shared",
            )
            for index in range(3)
        ]
        independent = synthetic_production_forecast(
            forecast_id="FCST-IND-1",
            snapshot=snapshot,
            probability=0.2,
            signal_ids=("SIG-IND",),
            forecast_family_key="family-independent",
        )
        repo = InMemoryIntelligenceRepository()
        engine = FusionEngine(ForecastProvenanceResolver(repo))
        manifest_a = ForecastFusionManifest.create(
            snapshot_id=snapshot.snapshot_id,
            target=default_target(),
            horizon=default_horizon(),
            decision_time_ns=snapshot.decision_time_ns,
            scope=snapshot.scope,
            contributors=[production_contributor(row) for row in (*base, independent)],
            fusion_policy=FusionPolicy(),
        )
        clone = synthetic_production_forecast(
            forecast_id="FCST-CLONE-CLONE",
            snapshot=snapshot,
            probability=0.9,
            signal_ids=("SIG-SHARED",),
            forecast_family_key="family-shared",
        )
        manifest_b = ForecastFusionManifest.create(
            snapshot_id=snapshot.snapshot_id,
            target=default_target(),
            horizon=default_horizon(),
            decision_time_ns=snapshot.decision_time_ns,
            scope=snapshot.scope,
            contributors=[production_contributor(row) for row in (*base, clone, independent)],
            fusion_policy=FusionPolicy(),
        )
        result_a = engine.fuse(manifest_a)
        result_b = engine.fuse(manifest_b)
        self.assertEqual(result_a.raw_probability, result_b.raw_probability)

    def test_within_and_across_group_pool(self) -> None:
        contributors = []
        snapshot = sample_snapshot()
        for probability, signal_id, family in ((0.8, "SIG-1", "f1"), (0.6, "SIG-2", "f1")):
            contributors.append(
                production_contributor(
                    synthetic_production_forecast(
                        forecast_id=f"FCST-{signal_id}",
                        snapshot=snapshot,
                        probability=probability,
                        signal_ids=(signal_id,),
                        forecast_family_key=family,
                    )
                )
            )
        group_probability = within_group_probability(tuple(contributors))
        self.assertAlmostEqual(group_probability, 0.7)
        groups = (
            ForecastDependenceGroup(group_id="g1", forecast_ids=("a",), group_probability=0.8),
            ForecastDependenceGroup(group_id="g2", forecast_ids=("b",), group_probability=0.6),
        )
        self.assertAlmostEqual(across_group_probability(groups, {"g1": 0.8, "g2": 0.6}), 0.7)


if __name__ == "__main__":
    unittest.main()
