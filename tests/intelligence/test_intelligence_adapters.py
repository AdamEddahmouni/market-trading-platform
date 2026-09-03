"""Tests for shadow P6 ↔ intelligence contract adapters."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.adapters import (  # noqa: E402
    forecast_v1_to_shadow_prediction_fields,
    shadow_label_to_outcome_v1,
    shadow_manifest_to_run_manifest_v1,
    shadow_prediction_to_forecast_v1,
)
from market_platform_foundation.intelligence.contracts.forecast import forecast_v1_from_dict  # noqa: E402
from market_platform_foundation.intelligence.contracts.forecast import forecast_v1_to_dict  # noqa: E402
from market_platform_foundation.shadow.records import (  # noqa: E402
    build_label_from_parts,
    build_prediction,
    build_run_manifest,
)

DECISION_NS = 1_000_000_000_000_000_000
HORIZON_NS = 500_000_000


class IntelligenceAdapterTests(unittest.TestCase):
    def test_shadow_prediction_maps_to_forecast(self) -> None:
        manifest = build_run_manifest(
            strategy_version="fixture-strategy/1",
            prediction_version="shadow/fixture/1",
            universe=("NVDA",),
            data_window_refs=({"kind": "replay", "ref": "fixtures/nvda"},),
            train_window_end_ns=DECISION_NS,
            eval_window_start_ns=DECISION_NS,
            eval_window_end_ns=DECISION_NS + HORIZON_NS * 10,
            created_at_ns=DECISION_NS - 1,
        )
        prediction = build_prediction(
            run_id=manifest.run_id,
            instrument_id="NVDA",
            decision_time_ns=DECISION_NS,
            horizon_ns=HORIZON_NS,
            predicted_probability=0.68,
            pit_snapshot_ref="snap-1",
            created_at_ns=DECISION_NS - 1,
        )
        forecast = shadow_prediction_to_forecast_v1(prediction)
        self.assertEqual(forecast.forecast_id, prediction.prediction_id)
        self.assertEqual(forecast.estimate.probability, 0.68)
        shadow_fields = forecast_v1_to_shadow_prediction_fields(forecast)
        self.assertEqual(shadow_fields["instrument_id"], "NVDA")
        round_trip = forecast_v1_from_dict(forecast_v1_to_dict(forecast))
        self.assertEqual(round_trip.horizon.duration_ns, HORIZON_NS)

    def test_shadow_label_maps_to_outcome(self) -> None:
        label = build_label_from_parts(
            run_id="run-1",
            prediction_id="pred-1",
            observed_positive=True,
            label_time_ns=DECISION_NS + HORIZON_NS,
            available_time_ns=DECISION_NS + HORIZON_NS + 1,
            observed_return_bps=42.0,
        )
        outcome = shadow_label_to_outcome_v1(label)
        self.assertEqual(outcome.forecast_id, label.prediction_id)
        self.assertAlmostEqual(outcome.realized_return, 0.0042)

    def test_shadow_manifest_maps_to_run_manifest(self) -> None:
        manifest = build_run_manifest(
            strategy_version="fixture-strategy/1",
            prediction_version="shadow/fixture/1",
            universe=("NVDA",),
            data_window_refs=({"kind": "replay", "ref": "fixtures/nvda"},),
            train_window_end_ns=DECISION_NS,
            eval_window_start_ns=DECISION_NS,
            eval_window_end_ns=DECISION_NS + HORIZON_NS,
            created_at_ns=DECISION_NS - 1,
        )
        run_manifest = shadow_manifest_to_run_manifest_v1(manifest)
        self.assertEqual(run_manifest.run_id, manifest.run_id)
        self.assertEqual(run_manifest.execution_authority, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
