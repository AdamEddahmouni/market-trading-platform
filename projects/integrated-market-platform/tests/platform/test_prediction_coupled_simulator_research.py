"""Prediction-conditioned historical simulator research (Lane R1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol.contamination import (  # noqa: E402
    BenchmarkContaminationError,
    assert_historical_manifest_admissible,
)
from market_platform_foundation.intelligence.historical_research_harness import (  # noqa: E402
    SIMULATOR_RESEARCH_RESULT_KIND,
    PredictionCoupledSimulatorError,
    build_signal_interpretations_from_predictions,
    run_historical_development_simulator_research,
)
from market_platform_foundation.intelligence.historical_research_harness.simulator import (  # noqa: E402
    ITEM9_CALIBRATION_RESULT_KIND,
)
from market_platform_foundation.risk.kill_switch import KillSwitchState  # noqa: E402


def _bar_event(time_ns: int, *, close: float = 100.0) -> dict:
    return {
        "available_time": time_ns,
        "event_time": time_ns,
        "event_type": "BAR_OHLCV_1M",
        "instrument_id": "canonical:EQUITY:XNAS:AAPL",
        "normalized_event_id": f"evt-{time_ns}",
        "bar_payload": {
            "open": str(close - 0.1),
            "high": str(close + 0.2),
            "low": str(close - 0.2),
            "close": str(close),
            "volume": 5000,
        },
    }


class PredictionCoupledSimulatorResearchTests(unittest.TestCase):
    def _run(self, predictions: list[dict], events: list[dict] | None = None, **kwargs):
        event_list = events or [_bar_event(1_000_000)]
        return run_historical_development_simulator_research(
            event_list,
            predictions=predictions,
            simulator_version="paper_bar_conservative_v1",
            cost_slippage_bps=5.0,
            **kwargs,
        )

    def test_no_trade_zero_intents_zero_fills(self) -> None:
        result = self._run([{"decision_time_ns": 1_000_000, "predicted_direction": 0}])
        self.assertEqual(result["trade_intents"], 0)
        self.assertEqual(result["fills"], 0)
        self.assertEqual(result["turnover"], 0)
        self.assertEqual(result["result_kind"], SIMULATOR_RESEARCH_RESULT_KIND)

    def test_one_long_signal_single_long_intent(self) -> None:
        result = self._run([{"decision_time_ns": 1_000_000, "predicted_direction": 1}])
        self.assertEqual(result["trade_intents"], 1)
        self.assertEqual(result["signals"][0]["signal_direction"], "long")
        intents = result["trade_intents"]
        self.assertEqual(intents, 1)
        self.assertFalse(result["independent_bar_replay_trading"])

    def test_one_short_signal_single_short_intent(self) -> None:
        interpretations, signals = build_signal_interpretations_from_predictions(
            [{"decision_time_ns": 2_000_000, "predicted_direction": -1}],
            instrument_id="canonical:EQUITY:XNAS:AAPL",
        )
        self.assertEqual(len(interpretations), 1)
        self.assertEqual(interpretations[0]["direction"], "short")
        self.assertEqual(signals[0]["signal_direction"], "short")

    def test_abstain_produces_no_intent(self) -> None:
        interpretations, _ = build_signal_interpretations_from_predictions(
            [{"decision_time_ns": 3_000_000, "predicted_direction": 0}],
            instrument_id="canonical:EQUITY:XNAS:AAPL",
        )
        self.assertEqual(interpretations, [])
        result = self._run([{"decision_time_ns": 3_000_000, "predicted_direction": 0}])
        self.assertEqual(result["trade_intents"], 0)

    def test_rejected_intent_produces_no_fill(self) -> None:
        result = self._run(
            [{"decision_time_ns": 1_000_000, "predicted_direction": 1}],
            kill_switch=KillSwitchState(active=True, reason_code="TEST_HALT"),
        )
        self.assertEqual(result["trade_intents"], 1)
        self.assertEqual(result["rejected_intents"], 1)
        self.assertEqual(result["accepted_intents"], 0)
        self.assertEqual(result["fills"], 0)

    def test_result_kind_missing_refused_by_benchmark(self) -> None:
        manifest = {
            "artifact_kind": "historical_research_run_manifest_v1",
            "corpus_evidence_authority": "HISTORICAL_DEVELOPMENT",
            "simulator": {},
        }
        with self.assertRaises(BenchmarkContaminationError) as ctx:
            assert_historical_manifest_admissible(manifest)
        self.assertEqual(str(ctx.exception), "SIMULATOR_RESULT_KIND_REQUIRED")

    def test_historical_simulation_not_item9_authority(self) -> None:
        result = self._run([{"decision_time_ns": 1_000_000, "predicted_direction": 0}])
        self.assertEqual(result["result_kind"], SIMULATOR_RESEARCH_RESULT_KIND)
        self.assertEqual(result["not_result_kind"], ITEM9_CALIBRATION_RESULT_KIND)
        self.assertFalse(result["item9_calibration"])
        self.assertFalse(result["item9_calibration_authority"])

    def test_no_trade_invariant_fails_closed_on_phantom_fills(self) -> None:
        with self.assertRaises(PredictionCoupledSimulatorError):
            from market_platform_foundation.intelligence.historical_research_harness.prediction_coupling import (
                assert_no_trade_baseline_invariant,
            )

            assert_no_trade_baseline_invariant(trade_intent_count=0, fill_count=1, turnover=1)


if __name__ == "__main__":
    unittest.main()
