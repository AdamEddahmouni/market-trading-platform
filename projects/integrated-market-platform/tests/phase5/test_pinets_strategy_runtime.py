"""Phase 5 Lane E — PineTS research runtime (isolated, non-authoritative)."""

from __future__ import annotations

import unittest

from market_platform_foundation.strategy.source_runtime.pinets_fixtures import FIXTURE_SMA_CROSSOVER
from market_platform_foundation.strategy.source_runtime.pinets_parity import (
    ParityFailureCode,
    ParitySide,
    compare_parity,
    parity_side_from_reference_payload,
)
from market_platform_foundation.strategy.source_runtime.pinets_reference import run_reference_fixture
from market_platform_foundation.strategy.source_runtime.pinets_registry import PineScriptRegistry
from market_platform_foundation.strategy.source_runtime.types import PineRuntimeCompatibilityStatus
from market_platform_foundation.strategy.source_runtime import (
    PineTSRuntime,
    STRATEGY_RUNTIME_PINETS_LICENSE_BOUNDARY,
    STRATEGY_RUNTIME_PINETS_RESEARCH_READY,
    StrategyDatasetRef,
    StrategyExecutionContext,
    StrategyExecutionMode,
    StrategyParameterRef,
    StrategyRuntimeError,
    StrategySourceRef,
)


def _bars(count: int = 12) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base = 3_000_000_000_000_000_000
    for index in range(count):
        close = 100.0 + index * 0.5
        available = base + index * 60_000_000_000
        events.append(
            {
                "available_time": available,
                "bar_payload": {
                    "close": str(close),
                    "high": str(close + 0.4),
                    "low": str(close - 0.4),
                    "open": str(close - 0.1),
                    "timeframe": "1_MINUTE",
                    "volume": 100 + index,
                },
                "event_time": available - 1,
                "event_type": "BAR_OHLCV_1M",
                "instrument_id": "EQ-1",
                "normalized_event_id": f"evt-{index}",
                "schema_version": "1.0.0",
            }
        )
    return events


class PineTSStrategyRuntimeLaneETests(unittest.TestCase):
    def test_runtime_reference_fixture_research_ready(self) -> None:
        runtime = PineTSRuntime()
        source = StrategySourceRef(
            kind="pinets_fixture",
            body={"script_id": FIXTURE_SMA_CROSSOVER},
        )
        dataset = StrategyDatasetRef(events=tuple(_bars()))
        parameters = StrategyParameterRef(body={})
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.PARITY,
            generated_at="2026-09-14T12:00:00.000000000Z",
        )
        result = runtime.execute(source, dataset, parameters, context)
        self.assertEqual(result.foundation_gate, STRATEGY_RUNTIME_PINETS_RESEARCH_READY)
        self.assertEqual(
            result.pine_compatibility_status,
            PineRuntimeCompatibilityStatus.PARTIAL_PARITY,
        )
        self.assertIn("license_audit", result.metrics)
        self.assertEqual(result.metrics["license_audit"]["npm_license"], "AGPL-3.0-only")

    def test_prefer_pinets_engine_fails_closed_at_license_boundary(self) -> None:
        runtime = PineTSRuntime()
        source = StrategySourceRef(
            kind="pinets_fixture",
            body={"script_id": FIXTURE_SMA_CROSSOVER},
        )
        dataset = StrategyDatasetRef(events=tuple(_bars()))
        parameters = StrategyParameterRef(body={"prefer_pinets_engine": True})
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.RESEARCH,
            generated_at="2026-09-14T12:00:00.000000000Z",
        )
        result = runtime.execute(source, dataset, parameters, context)
        self.assertEqual(result.foundation_gate, STRATEGY_RUNTIME_PINETS_LICENSE_BOUNDARY)
        self.assertTrue(any("PINETS" in err or "NODE" in err for err in result.errors))

    def test_live_hold_label_rejected(self) -> None:
        runtime = PineTSRuntime()
        source = StrategySourceRef(kind="pinets_fixture", body={"script_id": FIXTURE_SMA_CROSSOVER})
        dataset = StrategyDatasetRef(events=tuple(_bars(4)))
        parameters = StrategyParameterRef(body={})
        context = StrategyExecutionContext(
            mode=StrategyExecutionMode.RESEARCH,
            generated_at="2026-09-14T12:00:00.000000000Z",
            hold_labels=("SIMULATOR", "LIVE_ON"),
        )
        with self.assertRaises(StrategyRuntimeError):
            runtime.execute(source, dataset, parameters, context)

    def test_imported_script_defaults_untested(self) -> None:
        registry = PineScriptRegistry()
        record = registry.import_script(
            "imp.pinets.custom.unreviewed",
            pine_source="// @version=5\nindicator(\"X\")\nplot(close)\n",
        )
        self.assertEqual(record.status, PineRuntimeCompatibilityStatus.UNTESTED)

    def test_parity_harness_reference_self_match(self) -> None:
        bars = [
            {"time": 1, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1.0},
            {"time": 2, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 1.0},
            {"time": 3, "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2, "volume": 1.0},
            {"time": 4, "open": 1.2, "high": 1.4, "low": 1.1, "close": 1.3, "volume": 1.0},
            {"time": 5, "open": 1.3, "high": 1.5, "low": 1.2, "close": 1.4, "volume": 1.0},
            {"time": 6, "open": 1.4, "high": 1.6, "low": 1.3, "close": 1.5, "volume": 1.0},
        ]
        for script_id in (
            "imp.pinets.fixture.sma_crossover",
            "imp.pinets.fixture.rsi_threshold",
            "imp.pinets.fixture.simple_breakout",
        ):
            payload = run_reference_fixture(script_id, bars, {})
            side = parity_side_from_reference_payload(payload)
            parity = compare_parity(side, side)
            self.assertTrue(parity.ok, msg=f"{script_id}:{parity.details}")

    def test_parity_detects_numerical_mismatch(self) -> None:
        reference = ParitySide(indicators={"rsi": [None, 50.0, 55.0]}, warmup_bars=1)
        challenger = ParitySide(indicators={"rsi": [None, 50.0, 56.0]}, warmup_bars=1)
        parity = compare_parity(reference, challenger)
        self.assertFalse(parity.ok)
        self.assertIn(str(ParityFailureCode.NUMERICAL_MISMATCH), parity.failure_codes)


if __name__ == "__main__":
    unittest.main()
