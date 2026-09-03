"""SS P4 live confirmation tests — fixture-first transition stream and causal fusion."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge.projections import (  # noqa: E402
    _build_state_machine,
    _merge_cross_lane_causal,
)
from market_platform_foundation.donor_bridge.transition_stream import (  # noqa: E402
    DEFAULT_TRANSITION_STREAM_FIXTURE,
    replay_transition_stream,
)
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger  # noqa: E402


_NVDA_ORDER_FLOW_CUTOFF = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")


class SSP4TransitionStreamTests(unittest.TestCase):
    def test_replay_transition_stream_returns_all_when_no_cutoff(self) -> None:
        transitions = replay_transition_stream(DEFAULT_TRANSITION_STREAM_FIXTURE)
        self.assertEqual(len(transitions), 3)
        self.assertEqual(transitions[0]["to_state"], "LIVE_CONFIRMATION")

    def test_replay_transition_stream_pit_filters(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:00:00.000000000Z")
        transitions = replay_transition_stream(DEFAULT_TRANSITION_STREAM_FIXTURE, as_of_time_ns=cutoff)
        self.assertEqual(len(transitions), 2)
        self.assertEqual(transitions[0]["to_state"], "IGNITION_WATCH")

    def test_build_state_machine_surfaces_transition_metadata(self) -> None:
        detail = {
            "freshness": "CURRENT",
            "causal_intelligence": {"state": "LIVE_CONFIRMATION", "transition": {"trigger": "live_order_flow_confirmation"}},
            "causal_state_transitions": replay_transition_stream(DEFAULT_TRANSITION_STREAM_FIXTURE),
        }
        machine = _build_state_machine(detail, rules=[])
        self.assertEqual(machine["transition_count"], 3)
        self.assertEqual(machine["latest_transition_at"], "2026-07-21T20:05:00.000000000Z")
        self.assertEqual(machine["last_transition_label"], "2026-07-21T20:05:00.000000000Z")
        self.assertEqual(machine["state_transitions"][0]["to_state"], "LIVE_CONFIRMATION")


class SSP4LiveConfirmationHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(
            build_combined_fixture_ledger(as_of_time_ns=_NVDA_ORDER_FLOW_CUTOFF)
        )

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_cross_lane_replay_reaches_live_confirmation(self) -> None:
        detail = {
            "identity": {"symbol": "NVDA"},
            "available": True,
            "freshness": "CURRENT",
            "pressure": 55.0,
            "ignition": 62.0,
            "adam_classification": "WATCH",
            "rules": [],
        }
        causal = {
            "state": "LIVE_CONFIRMATION",
            "overall_confidence": "HIGH",
            "model_version": "squeeze_causal_baseline.v1",
            "transition": {"trigger": "live_order_flow_confirmation", "from_state": "IGNITION_WATCH"},
            "supporting_evidence": [{"code": "CVD_AGGRESSIVE_BUY"}],
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
                prediction_cutoff=_NVDA_ORDER_FLOW_CUTOFF,
                as_of_context={},
            )
        self.assertEqual(merged["causal_intelligence"]["state"], "LIVE_CONFIRMATION")
        self.assertTrue(any(item.get("signal") == "AGGRESSIVE_BUY_PRESSURE" for item in evidence))
        codes = {item.get("signal") for item in evidence if isinstance(item, dict)}
        self.assertIn("AGGRESSIVE_BUY_PRESSURE", codes)


if __name__ == "__main__":
    unittest.main()
