"""Integration tests for cross-lane fusion DAG and squeeze publisher."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.evidence import EvidenceProvenanceClass, validate_evidence_dag  # noqa: E402
from market_platform_foundation.donor_bridge.cross_lane_adapter import (  # noqa: E402
    build_cross_lane_snapshot_from_squeeze,
    merge_cross_lane_evidence,
)
from market_platform_foundation.donor_bridge.projections import _merge_cross_lane_causal  # noqa: E402
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger  # noqa: E402


_NVDA_ORDER_FLOW_CUTOFF = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")


class CrossLaneIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        configure_institutional_ledger(
            build_combined_fixture_ledger(as_of_time_ns=_NVDA_ORDER_FLOW_CUTOFF)
        )

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)
    def test_squeeze_publisher_emits_model_output(self) -> None:
        detail = {
            "causal_intelligence": {
                "state": "VULNERABLE",
                "overall_confidence": "MEDIUM",
                "model_version": "squeeze_causal_baseline.v1",
            }
        }
        snapshot, evidence = build_cross_lane_snapshot_from_squeeze(detail)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot.get("squeeze_available"))
        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0].get("provenance_class"), EvidenceProvenanceClass.MODEL_OUTPUT.value)

    def test_merge_path_has_no_same_timestamp_model_feedback_loop(self) -> None:
        detail = {
            "identity": {"symbol": "NVDA"},
            "available": True,
            "rules": [],
            "causal_intelligence": {
                "state": "VULNERABLE",
                "overall_confidence": "MEDIUM",
                "model_version": "squeeze_causal_baseline.v1",
            },
        }
        with patch(
            "market_platform_foundation.donor_bridge.projections.evaluate_causal_intelligence",
            return_value=detail["causal_intelligence"],
        ):
            merged, evidence = _merge_cross_lane_causal(
                detail,
                symbol="NVDA",
                base_url="http://127.0.0.1:8787",
                mode_normalized="frozen",
                prediction_cutoff=_NVDA_ORDER_FLOW_CUTOFF,
                as_of_context={"as_of_time_ns": _NVDA_ORDER_FLOW_CUTOFF},
            )
        squeeze_signals = [item for item in evidence if item.get("signal") == "SQUEEZE_STATE"]
        self.assertTrue(squeeze_signals)
        from market_platform_foundation.cross_lane.evidence import EvidenceSignal, LaneId, NormalizedLaneEvidence

        parsed = [
            NormalizedLaneEvidence(
                lane=LaneId(str(item.get("lane"))),
                signal=EvidenceSignal(str(item.get("signal"))),
                strength=str(item.get("strength", "LOW")),
                available=True,
                source_ref=str(item.get("source_ref", "")),
                detail=str(item.get("detail", "")),
                provenance_class=EvidenceProvenanceClass(
                    str(item.get("provenance_class", EvidenceProvenanceClass.DERIVED.value))
                ),
            )
            for item in evidence
            if isinstance(item, dict)
        ]
        violations = validate_evidence_dag(parsed)
        self.assertEqual(violations, [])
        self.assertIsNotNone(merged.get("causal_intelligence"))

    def test_current_mode_fuses_cross_lane_without_prediction_cutoff(self) -> None:
        detail = {
            "identity": {"symbol": "NVDA"},
            "available": True,
            "freshness": "CURRENT",
            "rules": [],
            "causal_intelligence": {
                "state": "IGNITION_WATCH",
                "overall_confidence": "MEDIUM",
                "model_version": "squeeze_causal_baseline.v1",
            },
        }
        refreshed = {
            **detail,
            "causal_state_transitions": [
                {
                    "from_state": "IGNITION_WATCH",
                    "to_state": "LIVE_CONFIRMATION",
                    "changed_at": "2026-08-18T18:10:00Z",
                    "trigger": "live_order_flow_confirmation",
                    "kind": "causal_state",
                }
            ],
        }
        with patch(
            "market_platform_foundation.donor_bridge.projections.post_cross_lane_snapshot",
            return_value={"ok": True},
        ) as post_mock, patch(
            "market_platform_foundation.donor_bridge.projections.fetch_current_candidate_detail",
            return_value=refreshed,
        ):
            merged, evidence = _merge_cross_lane_causal(
                detail,
                symbol="NVDA",
                base_url="http://127.0.0.1:8787",
                mode_normalized="current",
                prediction_cutoff=None,
                as_of_context={"as_of_time_ns": _NVDA_ORDER_FLOW_CUTOFF},
            )
        post_mock.assert_called_once()
        snapshot = post_mock.call_args[0][1]
        self.assertTrue(snapshot.get("order_flow_available"))
        self.assertTrue(evidence)
        self.assertEqual(merged.get("causal_state_transitions", [{}])[0].get("to_state"), "LIVE_CONFIRMATION")

    def test_nvda_opportunity_fusion_end_to_end(self) -> None:
        import json

        from market_platform_foundation.cross_lane.evidence import EvidenceSignal
        from market_platform_foundation.donor_bridge.opportunity_adapter import build_opportunity_fusion_bundle
        from market_platform_foundation.options.strategy import build_strategy_snapshot

        strategy_fixture_path = ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_strategy_optimizer_slice.json"
        opportunity_fixture_path = ROOT / "tests" / "fixtures" / "providers" / "opportunity" / "nvda_opportunity_fusion_expected.json"
        strategy_fixture = json.loads(strategy_fixture_path.read_text(encoding="utf-8"))
        opportunity_fixture = json.loads(opportunity_fixture_path.read_text(encoding="utf-8"))
        scenario = strategy_fixture["scenarios"]["bullish_directional"]
        strategy_snapshot = build_strategy_snapshot(
            strategy_fixture["symbol"],
            strategy_fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=strategy_fixture["physical_forecast"],
            chain_rows=strategy_fixture["chain_rows"],
            friction=scenario["friction"],
        )
        squeeze_detail = {
            "causal_intelligence": {
                "state": "ACTIVE_SQUEEZE",
                "remaining_fuel": 72.0,
            }
        }
        bundle, evidence = build_opportunity_fusion_bundle(
            "NVDA",
            strategy_fixture["as_of_time"],
            strategy_snapshot=strategy_snapshot,
            physical_forecast=strategy_fixture["physical_forecast"],
            squeeze_detail=squeeze_detail,
            order_flow_payload={
                "available": True,
                "bars": [{"delta": 120.0, "cumulative_delta": 620.0}],
            },
            execution_friction=scenario["friction"],
        )
        expected = opportunity_fixture["expected"]
        snapshot = bundle["opportunity_snapshot"]
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["fused_net_ev"], expected["fused_net_ev"])
        signals = {row["signal"] for row in evidence}
        self.assertIn(EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED.value, signals)


if __name__ == "__main__":
    unittest.main()
