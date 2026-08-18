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


class CrossLaneIntegrationTests(unittest.TestCase):
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
            "identity": {"symbol": "BIYA"},
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
                symbol="BIYA",
                base_url="http://127.0.0.1:8787",
                mode_normalized="frozen",
                prediction_cutoff=1784114400000000000,
                as_of_context={},
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


if __name__ == "__main__":
    unittest.main()
