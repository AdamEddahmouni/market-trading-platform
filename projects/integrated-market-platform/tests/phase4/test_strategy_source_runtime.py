"""Phase 4 Lane H — StrategyRuntime foundation (Python adapter + stubs)."""

from __future__ import annotations

import unittest

from market_platform_foundation.strategy.evaluation import (
    default_forecast_momentum_spec,
    strategy_evaluation_root_hash,
    run_strategy_evaluation,
)
from market_platform_foundation.strategy.source_runtime import (
    MATLABRuntime,
    PineTSRuntime,
    PythonRuntime,
    STRATEGY_RUNTIME_FOUNDATION_READY,
    STRATEGY_RUNTIME_STUB_UNAVAILABLE,
    StrategyDatasetRef,
    StrategyExecutionContext,
    StrategyExecutionMode,
    StrategyParameterRef,
    StrategyRuntimeError,
    StrategySourceRef,
    TypeScriptRuntime,
    WasmStrategyRuntime,
)


def _synthetic_events(count: int = 8) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base = 2_000_000_000_000_000_000
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


class StrategySourceRuntimeFoundationTests(unittest.TestCase):
    def test_python_runtime_executes_walk_forward_evaluation(self) -> None:
        events = _synthetic_events()
        runtime = PythonRuntime()
        source = StrategySourceRef(kind="strategy_spec", body=default_forecast_momentum_spec())
        dataset = StrategyDatasetRef(events=tuple(events))
        parameters = StrategyParameterRef(body={})
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.RESEARCH,
            generated_at="2026-09-14T00:00:00.000000000Z",
        )
        result = runtime.execute(source, dataset, parameters, context)
        self.assertEqual(result.foundation_gate, STRATEGY_RUNTIME_FOUNDATION_READY)
        self.assertGreater(result.metrics["signal_count"], 0)
        self.assertEqual(len(result.signals), result.metrics["signal_count"])
        direct = run_strategy_evaluation(events, strategy_spec=default_forecast_momentum_spec())
        self.assertEqual(
            result.metrics["evaluation_root_hash"],
            strategy_evaluation_root_hash(direct),
        )

    def test_result_identity_is_deterministic(self) -> None:
        events = _synthetic_events()
        runtime = PythonRuntime()
        source = StrategySourceRef(kind="strategy_spec", body=default_forecast_momentum_spec())
        dataset = StrategyDatasetRef(events=tuple(events))
        parameters = StrategyParameterRef(body={})
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.REPLAY,
            generated_at="2026-09-14T00:00:00.000000000Z",
        )
        first = runtime.execute(source, dataset, parameters, context)
        second = runtime.execute(source, dataset, parameters, context)
        self.assertEqual(first.result_identity, second.result_identity)
        self.assertEqual(first.source_hash, second.source_hash)
        self.assertEqual(first.dataset_hash, second.dataset_hash)

    def test_stub_runtimes_fail_closed_with_errors(self) -> None:
        source = StrategySourceRef(kind="strategy_spec", body=default_forecast_momentum_spec())
        dataset = StrategyDatasetRef(events=tuple(_synthetic_events(2)))
        parameters = StrategyParameterRef(body={})
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.PARITY,
            generated_at="2026-09-14T00:00:00.000000000Z",
        )
        for stub in (MATLABRuntime(), PineTSRuntime(), TypeScriptRuntime(), WasmStrategyRuntime()):
            result = stub.execute(source, dataset, parameters, context)
            self.assertTrue(result.errors)
            self.assertEqual(result.metrics, {})
            self.assertEqual(result.foundation_gate, STRATEGY_RUNTIME_STUB_UNAVAILABLE)
            self.assertNotEqual(result.foundation_gate, STRATEGY_RUNTIME_FOUNDATION_READY)

    def test_live_hold_label_rejected(self) -> None:
        runtime = PythonRuntime()
        source = StrategySourceRef(kind="strategy_spec", body=default_forecast_momentum_spec())
        dataset = StrategyDatasetRef(events=tuple(_synthetic_events(2)))
        parameters = StrategyParameterRef(body={})
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.RESEARCH,
            generated_at="2026-09-14T00:00:00.000000000Z",
            hold_labels=("SIMULATOR", "LIVE_ON"),
        )
        with self.assertRaises(StrategyRuntimeError):
            runtime.execute(source, dataset, parameters, context)


if __name__ == "__main__":
    unittest.main()
