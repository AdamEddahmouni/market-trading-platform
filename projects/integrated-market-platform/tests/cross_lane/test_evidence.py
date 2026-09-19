"""Tests for cross-lane evidence contract extensions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.evidence import (  # noqa: E402
    OBSERVED_AT_EMPTY,
    OBSERVED_AT_UNKNOWN,
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    apply_evidence_lag_rules,
    lane_evidence_from_dict,
    lane_evidence_to_dict,
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
        self.assertEqual(payload["inference_kind"], "DERIVED")
        self.assertEqual(payload["observed_at_presence"], OBSERVED_AT_UNKNOWN)

    def test_model_output_labels_inference_kind(self) -> None:
        item = NormalizedLaneEvidence(
            lane=LaneId.MARKET_CONTEXT,
            signal=EvidenceSignal.EVENT_SURPRISE_POSITIVE,
            strength="MODERATE",
            available=True,
            source_ref="mc6",
            detail="surprise",
            provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
        )
        payload = lane_evidence_to_dict(item)
        self.assertEqual(payload["inference_kind"], "MODEL_INFERENCE")

    def test_empty_observed_at_is_not_unknown_timestamp(self) -> None:
        item = NormalizedLaneEvidence(
            lane=LaneId.OPTIONS,
            signal=EvidenceSignal.CALL_DEMAND_ANOMALY,
            strength="LOW",
            available=True,
            source_ref="test",
            detail="detail",
            observed_at="",
            provenance_class=EvidenceProvenanceClass.DERIVED,
        )
        payload = lane_evidence_to_dict(item)
        self.assertEqual(payload["observed_at_presence"], OBSERVED_AT_EMPTY)
        round_trip = lane_evidence_from_dict(payload)
        self.assertIsNone(round_trip.observed_at)

    def test_lane_evidence_from_dict_round_trip(self) -> None:
        original = NormalizedLaneEvidence(
            lane=LaneId.FUTURES,
            signal=EvidenceSignal.FUTURES_DATA_CONFIDENCE,
            strength="HIGH",
            available=True,
            source_ref="futures:fixture",
            detail="fixture confidence",
            observed_at="2026-07-15T14:45:00.000000000Z",
            quality_flags=("DELAYED",),
            provenance_class=EvidenceProvenanceClass.RAW,
        )
        restored = lane_evidence_from_dict(lane_evidence_to_dict(original))
        self.assertEqual(restored.lane, original.lane)
        self.assertEqual(restored.signal, original.signal)
        self.assertEqual(restored.provenance_class, original.provenance_class)
        self.assertEqual(restored.observed_at, original.observed_at)

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

    def test_validate_evidence_dag_detects_context_options_coupling(self) -> None:
        observed_at = "2026-07-15T14:45:00.000000000Z"
        items = [
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=EvidenceSignal.EVENT_SURPRISE_POSITIVE,
                strength="MODERATE",
                available=True,
                source_ref="mc6",
                detail="surprise",
                observed_at=observed_at,
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=EvidenceSignal.EVENT_VOL_PREMIUM,
                strength="MODERATE",
                available=True,
                source_ref="o7",
                detail="event vol",
                observed_at=observed_at,
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
        ]
        violations = validate_evidence_dag(items)
        self.assertTrue(any("MC-D20" in item for item in violations))

    def test_apply_evidence_lag_rules_filters_options_coupling(self) -> None:
        observed_at = "2026-07-15T14:45:00.000000000Z"
        items = [
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=EvidenceSignal.EVENT_SURPRISE_POSITIVE,
                strength="MODERATE",
                available=True,
                source_ref="mc6",
                detail="surprise",
                observed_at=observed_at,
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=EvidenceSignal.EVENT_VOL_PREMIUM,
                strength="MODERATE",
                available=True,
                source_ref="o7",
                detail="event vol",
                observed_at=observed_at,
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
        ]
        filtered, violations = apply_evidence_lag_rules(items)
        self.assertTrue(violations)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].lane, LaneId.MARKET_CONTEXT)

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
