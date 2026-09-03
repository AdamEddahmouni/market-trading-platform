"""Baseline control tests (BUILD 08)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.baselines import (  # noqa: E402
    AlwaysDownBaseline,
    AlwaysUpBaseline,
    BaselinePredictionEngine,
    BaselinePredictionRequest,
    DeterministicRandomBaseline,
    MomentumBaseline,
    PredictionStatus,
)
from tests.intelligence.test_baseline_fixtures import (  # noqa: E402
    default_horizon,
    default_target,
    momentum_signal,
    sample_snapshot,
)


class BaselineControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = BaselinePredictionEngine()
        self.snapshot = sample_snapshot()
        self.target = default_target()
        self.horizon = default_horizon()

    def _request(self, signals=()):
        return BaselinePredictionRequest(
            snapshot=self.snapshot,
            signals=signals,
            target=self.target,
            horizon=self.horizon,
        )

    def test_always_up(self) -> None:
        result = self.engine.predict(self._request(), AlwaysUpBaseline().bind_target(self.target))
        self.assertEqual(result.status, PredictionStatus.PREDICTED)
        assert result.forecast is not None
        self.assertEqual(result.forecast.estimate.probability, 1.0)
        self.assertEqual(result.forecast.metadata["predicted_direction"], "UP")
        self.assertEqual(result.forecast.metadata["calibration_status"], "UNCALIBRATED")

    def test_always_down(self) -> None:
        result = self.engine.predict(self._request(), AlwaysDownBaseline().bind_target(self.target))
        self.assertEqual(result.status, PredictionStatus.PREDICTED)
        assert result.forecast is not None
        self.assertEqual(result.forecast.estimate.probability, 0.0)

    def test_deterministic_random(self) -> None:
        model = DeterministicRandomBaseline(seed="seed-a").bind_target(self.target)
        first = self.engine.predict(self._request(), model)
        second = self.engine.predict(self._request(), model)
        assert first.forecast is not None and second.forecast is not None
        self.assertEqual(first.forecast.forecast_id, second.forecast.forecast_id)
        self.assertEqual(first.forecast.estimate.probability, second.forecast.estimate.probability)

    def test_random_seed_changes_model_id(self) -> None:
        a = DeterministicRandomBaseline(seed="seed-a").bind_target(self.target)
        b = DeterministicRandomBaseline(seed="seed-b").bind_target(self.target)
        self.assertNotEqual(a.descriptor.model_id, b.descriptor.model_id)

    def test_momentum_positive(self) -> None:
        signal = momentum_signal(snapshot_id=self.snapshot.snapshot_id, value=0.02)
        result = self.engine.predict(self._request((signal,)), MomentumBaseline().bind_target(self.target))
        self.assertEqual(result.status, PredictionStatus.PREDICTED)
        assert result.forecast is not None
        self.assertEqual(result.forecast.metadata["predicted_direction"], "UP")

    def test_momentum_negative(self) -> None:
        signal = momentum_signal(snapshot_id=self.snapshot.snapshot_id, value=-0.03)
        result = self.engine.predict(self._request((signal,)), MomentumBaseline().bind_target(self.target))
        self.assertEqual(result.status, PredictionStatus.PREDICTED)
        assert result.forecast is not None
        self.assertEqual(result.forecast.metadata["predicted_direction"], "DOWN")

    def test_momentum_zero_abstains(self) -> None:
        signal = momentum_signal(snapshot_id=self.snapshot.snapshot_id, value=0.0)
        result = self.engine.predict(self._request((signal,)), MomentumBaseline().bind_target(self.target))
        self.assertEqual(result.status, PredictionStatus.ABSTAINED)

    def test_momentum_missing_abstains(self) -> None:
        result = self.engine.predict(self._request(), MomentumBaseline().bind_target(self.target))
        self.assertEqual(result.status, PredictionStatus.ABSTAINED)


if __name__ == "__main__":
    unittest.main()
