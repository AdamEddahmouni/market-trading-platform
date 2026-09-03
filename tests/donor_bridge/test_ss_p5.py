"""SS P5 active squeeze + remaining fuel tests — fixture-first harness."""

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

from market_platform_foundation.donor_bridge.cross_lane_adapter import (  # noqa: E402
    build_cross_lane_snapshot_from_options,
    build_cross_lane_snapshot_from_squeeze,
)
from market_platform_foundation.donor_bridge.projections import _merge_cross_lane_causal  # noqa: E402
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.options.features.squeeze_context import (  # noqa: E402
    build_squeeze_context_for_options,
)
from market_platform_foundation.providers.projections import build_workspace_options_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402

from squeeze_core.intelligence.evaluator import (  # noqa: E402
    AdamSnapshot,
    CrossLaneSnapshot,
    evaluate_squeeze_intelligence,
)

_SCENARIO_FIXTURE = ROOT / "tests" / "fixtures" / "squeeze" / "active_squeeze_scenario.json"
_NVDA_CUTOFF = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")


class SSP5FuelModuleTests(unittest.TestCase):
    def test_active_squeeze_scenario_fixture_evaluates(self) -> None:
        scenario = json.loads(_SCENARIO_FIXTURE.read_text(encoding="utf-8"))
        donor = scenario["donor_row"]
        hints = scenario["cross_lane_hints"]
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(
                pressure=donor["pressure"],
                ignition=donor["ignition"],
                classification=donor["adam_classification"],
            ),
            cross_lane=CrossLaneSnapshot(
                order_flow_available=True,
                order_flow_aggressive_buy=hints["order_flow_aggressive_buy"],
                order_flow_cvd_slope=5.0,
                options_available=True,
                options_gamma_amplification=hints["options_gamma_amplification"],
                options_hedging_pressure=hints.get("options_hedging_pressure"),
            ),
        )
        expected = scenario["expected_causal"]
        self.assertEqual(result.state.value, expected["state"])
        assert result.reflexivity_strength is not None
        self.assertGreaterEqual(result.reflexivity_strength, expected["min_reflexivity_strength"])
        assert result.remaining_fuel is not None
        self.assertGreaterEqual(result.remaining_fuel, expected["min_remaining_fuel"])


class SSP5CrossLaneHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(
            bootstrap_default_providers(as_of_time_ns=_NVDA_CUTOFF)
        )

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_nvda_options_snapshot_wires_gamma_amplification(self) -> None:
        payload = build_workspace_options_payload(
            "NVDA",
            as_of_context={},
            prediction_cutoff=_NVDA_CUTOFF,
        )
        snapshot, _evidence = build_cross_lane_snapshot_from_options(payload)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot.get("options_gamma_amplification") or snapshot.get("options_dealer_position_available"))

    def test_cross_lane_fusion_posts_gamma_flags(self) -> None:
        detail = {
            "identity": {"symbol": "NVDA"},
            "available": True,
            "freshness": "CURRENT",
            "pressure": 72.0,
            "ignition": 75.0,
            "adam_classification": "WATCH",
            "rules": [],
        }
        causal = {
            "state": "ACTIVE_SQUEEZE",
            "overall_confidence": "HIGH",
            "model_version": "squeeze_causal_baseline.v2",
            "reflexivity_strength": 85.0,
            "remaining_fuel": 52.0,
            "exhaustion_risk": 20.0,
            "transition": {"trigger": "reflexive_feedback_with_structural_fuel"},
        }
        with patch(
            "market_platform_foundation.donor_bridge.projections.evaluate_causal_intelligence",
            return_value=causal,
        ):
            merged, evidence = _merge_cross_lane_causal(
                detail,
                symbol="NVDA",
                base_url="http://127.0.0.1:8787",
                mode_normalized="frozen",
                prediction_cutoff=_NVDA_CUTOFF,
                as_of_context={},
            )
        self.assertEqual(merged["causal_intelligence"]["state"], "ACTIVE_SQUEEZE")
        signals = {item.get("signal") for item in evidence if isinstance(item, dict)}
        self.assertIn("AGGRESSIVE_BUY_PRESSURE", signals)

    def test_squeeze_fuel_evidence_for_options_consumer(self) -> None:
        detail = {
            "causal_intelligence": {
                "state": "ACTIVE_SQUEEZE",
                "remaining_fuel": 55.0,
                "exhaustion_risk": 62.0,
            }
        }
        _snapshot, evidence = build_cross_lane_snapshot_from_squeeze(detail)
        signals = {row["signal"] for row in evidence}
        self.assertIn("REMAINING_SQUEEZE_FUEL", signals)
        self.assertIn("EXHAUSTION_RISK", signals)
        context = build_squeeze_context_for_options(detail["causal_intelligence"])
        self.assertEqual(context["remaining_squeeze_fuel"], 55.0)


if __name__ == "__main__":
    unittest.main()
