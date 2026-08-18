"""Tests for cross-lane evidence contract extensions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.evidence import (  # noqa: E402
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    validate_evidence_dag,
)


class CrossLaneEvidenceTests(unittest.TestCase):
    def test_futures_signals_exist(self) -> None:
        self.assertEqual(
            EvidenceSignal.FUTURES_CURVE_BACKWARDATION.value,
            "FUTURES_CURVE_BACKWARDATION",
        )
        self.assertEqual(
            EvidenceSignal.FUTURES_LONG_LIQUIDATION_RISK.value,
            "FUTURES_LONG_LIQUIDATION_RISK",
        )
        self.assertEqual(
            EvidenceSignal.CALL_DEMAND_ANOMALY.value, "CALL_DEMAND_ANOMALY"
        )
        self.assertEqual(
            EvidenceSignal.ESTIMATED_HEDGING_PRESSURE.value,
            "ESTIMATED_HEDGING_PRESSURE",
        )

    def test_provenance_class_serialized(self) -> None:
        from market_platform_foundation.cross_lane.evidence import lane_evidence_to_dict

        item = NormalizedLaneEvidence(
            lane=LaneId.OPTIONS,
            signal=EvidenceSignal.CALL_DEMAND_ANOMALY,
            strength="LOW",
            available=True,
            source_ref="test",
            detail="test detail",
            provenance_class=EvidenceProvenanceClass.DERIVED,
        )
        payload = lane_evidence_to_dict(item)
        self.assertEqual(payload["provenance_class"], "DERIVED")

    def test_validate_evidence_dag_empty_when_clean(self) -> None:
        items = [
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=EvidenceSignal.CALL_DEMAND_ANOMALY,
                strength="LOW",
                available=True,
                source_ref="test",
                detail="detail",
                provenance_class=EvidenceProvenanceClass.DERIVED,
            )
        ]
        self.assertEqual(validate_evidence_dag(items), [])

    def test_validate_evidence_dag_detects_cycle(self) -> None:
        signal = EvidenceSignal.CALL_DEMAND_ANOMALY
        items = [
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=signal,
                strength="LOW",
                available=True,
                source_ref="model",
                detail="model output",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=signal,
                strength="LOW",
                available=True,
                source_ref="cross",
                detail="cross lane",
                provenance_class=EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT,
            ),
        ]
        violations = validate_evidence_dag(items)
        self.assertTrue(violations)

    def test_physical_distribution_signals_exist(self) -> None:
        self.assertEqual(
            EvidenceSignal.FORECAST_RV_ELEVATED.value,
            "FORECAST_RV_ELEVATED",
        )
        self.assertEqual(
            EvidenceSignal.UPSIDE_TAIL_PROBABILITY_PHYSICAL.value,
            "UPSIDE_TAIL_PROBABILITY_PHYSICAL",
        )


if __name__ == "__main__":
    unittest.main()
