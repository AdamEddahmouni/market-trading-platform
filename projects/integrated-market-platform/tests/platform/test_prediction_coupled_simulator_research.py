"""Prediction-conditioned historical simulator research (Lane R1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

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


def _fillable_events(*, decision_time_ns: int = 1_000_000, bar_count: int = 3) -> list[dict]:
    """Bars with decision on the first timestamp and post-signal bars for conservative fills."""

    return [
        _bar_event(decision_time_ns + index * 60_000_000_000, close=100.0 + index * 0.1)
        for index in range(bar_count)
    ]


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
        decision_time_ns = 1_000_000
        result = self._run(
            [{"decision_time_ns": decision_time_ns, "predicted_direction": 1}],
            events=_fillable_events(decision_time_ns=decision_time_ns),
        )
        self.assertEqual(result["trade_intents"], 1)
        self.assertEqual(result["signals"][0]["signal_direction"], "long")
        self.assertGreaterEqual(result["accepted_intents"], 1)
        self.assertGreaterEqual(result["fills"], 1)

    def test_one_short_signal_e2e_when_risk_accepts(self) -> None:
        decision_time_ns = 2_000_000
        result = self._run(
            [{"decision_time_ns": decision_time_ns, "predicted_direction": -1}],
            events=_fillable_events(decision_time_ns=decision_time_ns),
        )
        self.assertEqual(result["trade_intents"], 1)
        self.assertEqual(result["signals"][0]["signal_direction"], "short")
        self.assertGreaterEqual(result["accepted_intents"], 1)
        self.assertGreaterEqual(result["fills"], 1)

    def test_research_path_does_not_invoke_walk_forward_strategy(self) -> None:
        decision_time_ns = 1_000_000
        with mock.patch(
            "market_platform_foundation.risk_simulation.evaluation.run_strategy_evaluation"
        ) as strategy_eval:
            result = self._run(
                [{"decision_time_ns": decision_time_ns, "predicted_direction": 1}],
                events=_fillable_events(decision_time_ns=decision_time_ns),
            )
            strategy_eval.assert_not_called()
        self.assertTrue(result["prediction_coupled"])

    def test_abstain_produces_no_intent(self) -> None:
        interpretations, _ = build_signal_interpretations_from_predictions(
            [{"decision_time_ns": 3_000_000, "predicted_direction": 0}],
            instrument_id="canonical:EQUITY:XNAS:AAPL",
        )
        self.assertEqual(interpretations, [])
        result = self._run([{"decision_time_ns": 3_000_000, "predicted_direction": 0}])
        self.assertEqual(result["trade_intents"], 0)

    def test_invalid_predicted_direction_abstains(self) -> None:
        result = self._run([{"decision_time_ns": 1_000_000, "predicted_direction": 99}])
        self.assertEqual(result["trade_intents"], 0)
        self.assertEqual(result["fills"], 0)
        self.assertTrue(result["signals"][0]["abstained"])

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

    @mock.patch(
        "market_platform_foundation.intelligence.historical_research_harness.simulator.summarize_risk_execution"
    )
    def test_no_trade_invariant_fails_closed_on_phantom_fills(
        self,
        mock_summarize: mock.MagicMock,
    ) -> None:
        mock_summarize.return_value = {
            "trade_intents": 0,
            "accepted_intents": 0,
            "rejected_intents": 0,
            "fills": 1,
            "partial_fills": 0,
            "gross_pnl": 10.0,
            "turnover": 1,
            "exposure": 1,
        }
        with self.assertRaises(PredictionCoupledSimulatorError):
            self._run([{"decision_time_ns": 1_000_000, "predicted_direction": 0}])


if __name__ == "__main__":
    unittest.main()
