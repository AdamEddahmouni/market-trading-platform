"""SS P6 advanced exhaustion tests — fixture-first harness."""

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
from market_platform_foundation.donor_bridge.lending_adapter import (  # noqa: E402
    build_lending_cross_lane_fields,
)
from market_platform_foundation.donor_bridge.projections import _merge_cross_lane_causal  # noqa: E402
from market_platform_foundation.donor_bridge.transition_stream import (  # noqa: E402
    DEFAULT_TRANSITION_STREAM_FIXTURE,
    extract_fuel_history,
    replay_transition_stream,
)
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.options.flow import build_flow_snapshot  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_options_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402

from squeeze_core.intelligence.evaluator import (  # noqa: E402
    AdamSnapshot,
    CrossLaneSnapshot,
    FuelHistorySnapshot,
    evaluate_squeeze_intelligence,
)

_SCENARIO_FIXTURE = ROOT / "tests" / "fixtures" / "squeeze" / "exhaustion_scenario.json"
_FLOW_REVERSAL_FIXTURE = (
    ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_flow_reversal_slice.json"
)
_NVDA_CUTOFF = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")


class SSP6ExhaustionModuleTests(unittest.TestCase):
    def test_exhaustion_scenario_fixture_evaluates(self) -> None:
        scenario = json.loads(_SCENARIO_FIXTURE.read_text(encoding="utf-8"))
        donor = scenario["donor_row"]
        hints = scenario["cross_lane_hints"]
        history = scenario["fuel_history"]
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
                order_flow_cvd_slope=hints["order_flow_cvd_slope"],
                options_available=hints.get("options_available", True),
                options_flow_reversal=hints.get("options_flow_reversal"),
                options_gamma_decay=hints.get("options_gamma_decay"),
                borrow_normalization_score=hints.get("borrow_normalization_score"),
            ),
            fuel_history=FuelHistorySnapshot(
                previous_remaining_fuel=history.get("previous_remaining_fuel"),
                previous_cvd_slope=history.get("previous_cvd_slope"),
                previous_reflexivity=history.get("previous_reflexivity"),
            ),
            previous_state=None,
        )
        expected = scenario["expected_causal"]
        self.assertEqual(result.state.value, expected["state"])
        assert result.exhaustion_risk is not None
        self.assertGreaterEqual(result.exhaustion_risk, expected["min_exhaustion_risk"])


class SSP6CrossLaneHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(
            bootstrap_default_providers(as_of_time_ns=_NVDA_CUTOFF)
        )

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_transition_stream_extracts_fuel_history(self) -> None:
        transitions = replay_transition_stream(DEFAULT_TRANSITION_STREAM_FIXTURE)
        history = extract_fuel_history(transitions)
        self.assertEqual(history.get("previous_remaining_fuel"), 65.0)
        self.assertEqual(history.get("previous_cvd_slope"), 5.0)

    def test_flow_reversal_fixture_sets_options_flow_reversal(self) -> None:
        payload = json.loads(_FLOW_REVERSAL_FIXTURE.read_text(encoding="utf-8"))
        activities = payload.get("activities", [])
        flow = build_flow_snapshot(activities, as_of_time=activities[0]["event_time"])
        self.assertEqual(flow.get("dominant_direction"), "sell_initiated")
        options_payload = {
            "available": True,
            "activities": activities,
            "signed_flow_snapshot": flow,
        }
        snapshot, evidence = build_cross_lane_snapshot_from_options(options_payload)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot.get("options_flow_reversal"))
        signals = {row.get("signal") for row in evidence}
        self.assertIn("OPTIONS_FLOW_REVERSAL", signals)

    def test_gamma_decay_with_prior_cross_lane(self) -> None:
        payload = build_workspace_options_payload(
            "NVDA",
            as_of_context={},
            prediction_cutoff=_NVDA_CUTOFF,
        )
        prior = {"options_gamma_amplification": True, "options_hedging_pressure": 2.5}
        snapshot, _evidence = build_cross_lane_snapshot_from_options(
            payload,
            prior_cross_lane=prior,
        )
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        if not snapshot.get("options_gamma_amplification"):
            self.assertTrue(snapshot.get("options_gamma_decay"))

    def test_lending_fixture_posts_borrow_normalization(self) -> None:
        fields = build_lending_cross_lane_fields()
        self.assertIn("borrow_normalization_score", fields)
        self.assertGreaterEqual(fields["borrow_normalization_score"], 50.0)

    def test_squeeze_exhaustion_evidence_still_published(self) -> None:
        detail = {
            "causal_intelligence": {
                "state": "EXHAUSTION",
                "remaining_fuel": 18.0,
                "exhaustion_risk": 82.0,
            }
        }
        _snapshot, evidence = build_cross_lane_snapshot_from_squeeze(detail)
        signals = {row["signal"] for row in evidence}
        self.assertIn("EXHAUSTION_RISK", signals)

    def test_cross_lane_fusion_includes_lending_and_fuel_history(self) -> None:
        detail = {
            "identity": {"symbol": "NVDA"},
            "available": True,
            "freshness": "CURRENT",
            "pressure": 72.0,
            "ignition": 60.0,
            "adam_classification": "WATCH",
            "rules": [],
        }
        causal = {
            "state": "EXHAUSTION",
            "overall_confidence": "HIGH",
            "model_version": "squeeze_causal_baseline.v3",
            "remaining_fuel": 18.0,
            "exhaustion_risk": 82.0,
            "transition": {"trigger": "exhaustion_signals"},
        }

        def _fake_evaluate(*, row, cross_lane, fuel_history=None, base_url, **kwargs):
            self.assertIn("borrow_normalization_score", cross_lane)
            self.assertIsNotNone(fuel_history)
            return causal

        with patch(
            "market_platform_foundation.donor_bridge.projections.evaluate_causal_intelligence",
            side_effect=_fake_evaluate,
        ):
            merged, evidence = _merge_cross_lane_causal(
                detail,
                symbol="NVDA",
                base_url="http://127.0.0.1:8787",
                mode_normalized="frozen",
                prediction_cutoff=_NVDA_CUTOFF,
                as_of_context={},
            )
        self.assertEqual(merged["causal_intelligence"]["state"], "EXHAUSTION")
        signals = {item.get("signal") for item in evidence if isinstance(item, dict)}
        self.assertIn("AGGRESSIVE_BUY_PRESSURE", signals)


if __name__ == "__main__":
    unittest.main()
