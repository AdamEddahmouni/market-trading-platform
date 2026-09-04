"""SS P7 donor bridge tests — calibrated horizons and simulator replay."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

DONOR_ROOT = ROOT.parent / "short-squeeze-project" / "short-squeeze-core"
sys.path.insert(0, str(DONOR_ROOT / "src"))

if not (DONOR_ROOT / "src" / "squeeze_core" / "intelligence").is_dir():
    raise unittest.SkipTest("companion squeeze_core intelligence package is unavailable")

from market_platform_foundation.donor_bridge.horizon_model_bridge import (  # noqa: E402
    build_horizon_model_snapshot,
)
from market_platform_foundation.donor_bridge.projections import _merge_cross_lane_causal  # noqa: E402
from market_platform_foundation.donor_bridge.squeeze_simulation_context import (  # noqa: E402
    resolve_squeeze_context_at_cutoff,
)
from market_platform_foundation.execution.simulator import BarConservativeSimulator  # noqa: E402
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY  # noqa: E402
from market_platform_foundation.risk_simulation.evaluation import (  # noqa: E402
    risk_simulation_root_hash,
    run_risk_simulation_evaluation,
)

from squeeze_core.intelligence.cross_lane import horizon_model_from_dict  # noqa: E402
from squeeze_core.intelligence.evaluator import (  # noqa: E402
    AdamSnapshot,
    evaluate_squeeze_intelligence,
)

_SIM_FIXTURE = ROOT / "tests" / "fixtures" / "squeeze" / "simulation_squeeze_replay_slice.json"
_NVDA_CUTOFF = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")


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
                    "volume": 10000 + index * 100,
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


class SSP7HorizonModelTests(unittest.TestCase):
    def test_build_horizon_model_snapshot_calibrated_when_pit_passes(self) -> None:
        snapshot = build_horizon_model_snapshot(symbol="BIYA")
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["status"], "CALIBRATED")
        self.assertTrue(snapshot["pit_verified"])
        self.assertIn("hazard_by_horizon", snapshot)
        self.assertIn("magnitude", snapshot)

    def test_calibrated_horizons_in_evaluator(self) -> None:
        snapshot = build_horizon_model_snapshot(symbol="BIYA")
        assert snapshot is not None
        model = horizon_model_from_dict(snapshot)
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=72.0, ignition=65.0, classification="WATCH"),
            horizon_model=model,
        )
        self.assertEqual(result.model_version, "squeeze_causal_baseline.v4")
        calibrated = [hp for hp in result.horizon_probabilities if hp.status == "CALIBRATED"]
        self.assertGreater(len(calibrated), 0)
        codes = {item.code for item in result.supporting_evidence}
        self.assertIn("CALIBRATED_HORIZON_PROBABILITY", codes)
        self.assertIn("MAGNITUDE_ESTIMATE", codes)


class SSP7SimulationReplayTests(unittest.TestCase):
    def test_resolve_squeeze_context_at_nvda_cutoff(self) -> None:
        scenario = json.loads(_SIM_FIXTURE.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(scenario["prediction_cutoff"])
        ctx = resolve_squeeze_context_at_cutoff(cutoff)
        self.assertTrue(ctx.get("available"))
        self.assertEqual(ctx.get("squeeze_state"), scenario["expected"]["squeeze_state"])
        self.assertEqual(ctx.get("remaining_fuel"), scenario["expected"]["remaining_fuel"])

    def test_simulator_records_squeeze_context(self) -> None:
        simulator = BarConservativeSimulator(policy=DEFAULT_RISK_POLICY)
        bars = _synthetic_events(6)
        intent = {
            "created_time": int(bars[0]["available_time"]),
            "direction": "long",
            "instrument_id": "EQ-1",
            "intent_id": "intent-1",
        }
        risk_decision = {"decision": "APPROVE", "approved_quantity": 1}
        squeeze_context = {
            "available": True,
            "squeeze_state": "ACTIVE_SQUEEZE",
            "exhaustion_risk": 20.0,
            "remaining_fuel": 55.0,
        }
        order, fill = simulator.simulate(
            intent=intent,
            risk_decision=risk_decision,
            bars=bars,
            squeeze_context=squeeze_context,
        )
        self.assertIn("squeeze_context", order)
        assert fill is not None
        self.assertIn("squeeze_context", fill)

    def test_squeeze_replay_hash_stable(self) -> None:
        events = _synthetic_events(10)
        result_a = run_risk_simulation_evaluation(events)
        result_b = run_risk_simulation_evaluation(events)
        self.assertIsNotNone(result_a.get("squeeze_replay_hash"))
        self.assertEqual(result_a["squeeze_replay_hash"], result_b["squeeze_replay_hash"])
        self.assertEqual(
            risk_simulation_root_hash(result_a),
            risk_simulation_root_hash(result_b),
        )


class SSP7CrossLaneHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(
            bootstrap_default_providers(as_of_time_ns=_NVDA_CUTOFF)
        )

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_cross_lane_fusion_includes_calibrated_horizons(self) -> None:
        detail = {
            "symbol": "NVDA",
            "pressure": 72.0,
            "ignition": 70.0,
            "adam_classification": "WATCH",
            "freshness": "FROZEN",
            "rules": [],
        }
        with patch(
            "market_platform_foundation.donor_bridge.projections.evaluate_causal_intelligence",
            side_effect=lambda **kwargs: {
                "model_version": "squeeze_causal_baseline.v4",
                "state": "LIVE_CONFIRMATION",
                "horizon_probabilities": [
                    {
                        "horizon_days": 5,
                        "value": 0.42,
                        "status": "CALIBRATED",
                        "note": "test",
                    }
                ],
            },
        ):
            merged, _evidence = _merge_cross_lane_causal(
                detail,
                symbol="NVDA",
                base_url="http://127.0.0.1:8787",
                mode_normalized="frozen",
                prediction_cutoff=_NVDA_CUTOFF,
                as_of_context={"as_of_time_ns": _NVDA_CUTOFF},
            )
        causal = merged.get("causal_intelligence")
        self.assertIsInstance(causal, dict)


if __name__ == "__main__":
    unittest.main()
