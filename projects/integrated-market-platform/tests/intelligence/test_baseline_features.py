"""Baseline feature extraction tests (BUILD 08)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.baselines.features import (  # noqa: E402
    BaselineFeatureSchema,
    FeatureSelector,
    FeatureVectorBuilder,
    MOMENTUM_5M_SELECTOR,
)
from market_platform_foundation.intelligence.contracts import QualityState, QualitySummary, SignalV1  # noqa: E402
from tests.intelligence.test_baseline_fixtures import (  # noqa: E402
    WINDOW,
    momentum_signal,
    sample_snapshot,
)


class BaselineFeatureTests(unittest.TestCase):
    def test_momentum_window_disambiguation(self) -> None:
        snapshot = sample_snapshot()
        schema = BaselineFeatureSchema(
            selectors=(
                MOMENTUM_5M_SELECTOR,
            )
        )
        one_min = momentum_signal(
            snapshot_id=snapshot.snapshot_id,
            value=0.01,
            signal_id="sig-1m",
            window_ns=60 * 1_000_000_000,
        )
        five_min = momentum_signal(
            snapshot_id=snapshot.snapshot_id,
            value=0.05,
            signal_id="sig-5m",
            window_ns=WINDOW,
        )
        vector, diagnostics = FeatureVectorBuilder(schema).extract(snapshot, (one_min, five_min))
        self.assertEqual(diagnostics, ())
        assert vector is not None
        self.assertEqual(vector.values[0], 0.05)
        self.assertEqual(vector.source_signals[0].signal_id, "sig-5m")

    def test_duplicate_feature_rejected(self) -> None:
        snapshot = sample_snapshot()
        schema = BaselineFeatureSchema(selectors=(MOMENTUM_5M_SELECTOR,))
        first = momentum_signal(snapshot_id=snapshot.snapshot_id, value=0.01, signal_id="sig-a")
        second = momentum_signal(snapshot_id=snapshot.snapshot_id, value=0.02, signal_id="sig-b")
        vector, diagnostics = FeatureVectorBuilder(schema).extract(snapshot, (first, second))
        self.assertIsNone(vector)
        self.assertTrue(diagnostics)

    def test_nonfinite_value_rejected_at_contract(self) -> None:
        with self.assertRaises(ValueError):
            momentum_signal(snapshot_id=sample_snapshot().snapshot_id, value=math.nan)

    def test_degraded_policy(self) -> None:
        snapshot = sample_snapshot()
        schema = BaselineFeatureSchema(selectors=(MOMENTUM_5M_SELECTOR,))
        degraded = SignalV1(
            signal_id="sig-degraded",
            schema_version="1",
            signal_type="momentum_simple",
            scope=snapshot.scope,
            as_of_time_ns=snapshot.decision_time_ns,
            value=0.01,
            quality=QualitySummary(state=QualityState.DEGRADED),
            source_snapshot_ref=momentum_signal(snapshot_id=snapshot.snapshot_id, value=0.01).source_snapshot_ref,
            calculation_window=momentum_signal(snapshot_id=snapshot.snapshot_id, value=0.01).calculation_window,
            calculation_lineage={
                "calculator_id": "momentum-calculator",
                "calculator_version": "1",
            },
        )
        vector, diagnostics = FeatureVectorBuilder(schema).extract(snapshot, (degraded,), allow_degraded=False)
        self.assertIsNone(vector)
        vector_allowed, diagnostics_allowed = FeatureVectorBuilder(schema).extract(
            snapshot, (degraded,), allow_degraded=True
        )
        self.assertEqual(diagnostics_allowed, ())
        self.assertIsNotNone(vector_allowed)


if __name__ == "__main__":
    unittest.main()
