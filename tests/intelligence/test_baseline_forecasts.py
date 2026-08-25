"""Baseline forecast identity and persistence tests (BUILD 08)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.baselines import (  # noqa: E402
    AlwaysUpBaseline,
    BaselinePredictionEngine,
    BaselinePredictionRequest,
    persist_forecast,
)
from market_platform_foundation.intelligence.baselines.identity import derive_forecast_id  # noqa: E402
from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from market_platform_foundation.intelligence.contracts import ForecastEstimate, ForecastV1, forecast_v1_from_dict, forecast_v1_to_dict  # noqa: E402
from tests.intelligence.test_baseline_fixtures import (  # noqa: E402
    default_horizon,
    default_target,
    sample_snapshot,
)


class BaselineForecastTests(unittest.TestCase):
    def test_forecast_id_determinism(self) -> None:
        engine = BaselinePredictionEngine()
        snapshot = sample_snapshot()
        target = default_target()
        horizon = default_horizon()
        model = AlwaysUpBaseline().bind_target(target)
        request = BaselinePredictionRequest(snapshot=snapshot, signals=(), target=target, horizon=horizon)
        first = engine.predict(request, model)
        second = engine.predict(request, model)
        assert first.forecast is not None and second.forecast is not None
        self.assertEqual(first.forecast.forecast_id, second.forecast.forecast_id)

    def test_forecast_id_excludes_output(self) -> None:
        snapshot = sample_snapshot()
        target = default_target()
        horizon = default_horizon()
        model = AlwaysUpBaseline().bind_target(target)
        forecast_id = derive_forecast_id(
            snapshot_id=snapshot.snapshot_id,
            source_signal_ids=(),
            model_id=model.descriptor.model_id,
            target=target,
            horizon=horizon,
        )
        self.assertTrue(forecast_id.startswith("BLFC-"))

    def test_persistence_idempotency(self) -> None:
        repo = InMemoryIntelligenceRepository()
        engine = BaselinePredictionEngine()
        snapshot = sample_snapshot()
        target = default_target()
        horizon = default_horizon()
        result = engine.predict(
            BaselinePredictionRequest(snapshot=snapshot, signals=(), target=target, horizon=horizon),
            AlwaysUpBaseline().bind_target(target),
        )
        assert result.forecast is not None
        self.assertEqual(persist_forecast(repo, result.forecast), RepositoryPutResult.INSERTED)
        self.assertEqual(persist_forecast(repo, result.forecast), RepositoryPutResult.ALREADY_PRESENT)

    def test_nondeterminism_conflict(self) -> None:
        repo = InMemoryIntelligenceRepository()
        engine = BaselinePredictionEngine()
        snapshot = sample_snapshot()
        target = default_target()
        horizon = default_horizon()
        result = engine.predict(
            BaselinePredictionRequest(snapshot=snapshot, signals=(), target=target, horizon=horizon),
            AlwaysUpBaseline().bind_target(target),
        )
        assert result.forecast is not None
        repo.put_forecast(result.forecast)
        from market_platform_foundation.intelligence.contracts import ForecastEstimate

        conflict = ForecastV1(
            forecast_id=result.forecast.forecast_id,
            schema_version=result.forecast.schema_version,
            scope=result.forecast.scope,
            decision_time_ns=result.forecast.decision_time_ns,
            snapshot_id=result.forecast.snapshot_id,
            target=result.forecast.target,
            horizon=result.forecast.horizon,
            estimate=ForecastEstimate(
                estimate_kind="classification_probability",
                probability=0.99,
            ),
            quality=result.forecast.quality,
        )
        with self.assertRaises(RepositoryConflictError):
            repo.put_forecast(conflict)

    def test_forecast_round_trip(self) -> None:
        engine = BaselinePredictionEngine()
        snapshot = sample_snapshot()
        target = default_target()
        horizon = default_horizon()
        result = engine.predict(
            BaselinePredictionRequest(snapshot=snapshot, signals=(), target=target, horizon=horizon),
            AlwaysUpBaseline().bind_target(target),
        )
        assert result.forecast is not None
        restored = forecast_v1_from_dict(forecast_v1_to_dict(result.forecast))
        self.assertEqual(restored.forecast_id, result.forecast.forecast_id)
        self.assertIsNone(restored.estimate.calibrated_probability)


if __name__ == "__main__":
    unittest.main()
