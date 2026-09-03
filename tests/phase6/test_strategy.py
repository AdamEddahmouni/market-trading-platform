"""Phase 6 preregistered strategy tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.research.forecast import build_forecast, verify_forecast_interface
from market_platform_foundation.strategy.evaluation import (
    default_forecast_momentum_spec,
    default_whale_aligned_spec,
    run_strategy_evaluation,
    strategy_evaluation_root_hash,
)
from market_platform_foundation.strategy.interpretation import interpret_strategy
from market_platform_foundation.strategy.preregistration import build_preregistration, verify_preregistration
from market_platform_foundation.strategy.strategy_spec import build_strategy_spec


def _synthetic_events(count: int = 6) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base = 2000000000000000000
    for index in range(count):
        available = base + index * 60_000_000_000
        events.append(
            {
                "available_time": available,
                "bar_payload": {
                    "close": str(100 + index),
                    "high": str(101 + index),
                    "low": str(99 + index),
                    "open": str(100 + index),
                    "timeframe": "1_MINUTE",
                    "volume": 100 + index,
                },
                "channel_id": "EQ-1",
                "event_time": available - 1,
                "event_type": "BAR_OHLCV_1M",
                "historical_ingested_time": available,
                "ingest_run_id": "RUN-SYNTH",
                "instrument_id": "EQ-1",
                "normalization_version": "test/1.0.0",
                "normalized_event_id": f"evt-{index}",
                "operation": "UPSERT",
                "publisher_id": "PUB-1",
                "quality_observation_refs": [],
                "raw_reference": f"test://{index}",
                "schema_version": "1.0.0",
                "source_instance_id": "SRC-1",
                "source_record_id": f"REC-{index}",
                "source_revision_id": "1",
                "venue_id": "VEN-1",
            }
        )
    return events


class StrategyTests(unittest.TestCase):
    def test_strategy_identity_stable(self) -> None:
        spec_a = build_strategy_spec(
            alignment_type="FORECAST_MOMENTUM",
            hypothesis="test",
            evidence_requirements=["bar_derived_features"],
        )
        spec_b = build_strategy_spec(
            alignment_type="FORECAST_MOMENTUM",
            hypothesis="test",
            evidence_requirements=["bar_derived_features"],
        )
        self.assertEqual(spec_a["strategy_identity_hash"], spec_b["strategy_identity_hash"])

    def test_preregistration_required(self) -> None:
        spec = default_whale_aligned_spec()
        forecast = build_forecast(score="1.0", prediction_cutoff=100, horizon_ns=60_000_000_000)
        fcast_status, _ = verify_forecast_interface(forecast)
        without = interpret_strategy(
            strategy_spec=spec,
            preregistration=None,
            forecast=forecast,
            forecast_status=fcast_status,
            prediction_cutoff=100,
            observation_time=100,
        )
        self.assertEqual(without["outcome"], "abstention")

    def test_whale_aligned_abstains_without_institutional(self) -> None:
        spec = default_whale_aligned_spec()
        prereg = build_preregistration(spec, registered_at="2026-08-16T00:00:00.000000000Z")
        status, reasons = verify_preregistration(prereg, spec)
        self.assertEqual(status, "PASS")
        forecast = build_forecast(score="1.0", prediction_cutoff=100, horizon_ns=60_000_000_000)
        fcast_status, _ = verify_forecast_interface(forecast)
        result = interpret_strategy(
            strategy_spec=spec,
            preregistration=prereg,
            forecast=forecast,
            forecast_status=fcast_status,
            prediction_cutoff=100,
            observation_time=100,
        )
        self.assertEqual(result["outcome"], "abstention")

    def test_strategy_evaluation_deterministic(self) -> None:
        events = _synthetic_events(8)
        result_a = run_strategy_evaluation(events)
        result_b = run_strategy_evaluation(events)
        self.assertEqual(strategy_evaluation_root_hash(result_a), strategy_evaluation_root_hash(result_b))
        self.assertGreater(result_a["signal_count"], 0)


if __name__ == "__main__":
    unittest.main()
