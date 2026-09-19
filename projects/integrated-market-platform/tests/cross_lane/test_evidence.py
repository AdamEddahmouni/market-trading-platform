"""Tests for cross-lane evidence contract extensions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.evidence import (  # noqa: E402
    OBSERVED_AT_EMPTY,
    OBSERVED_AT_PRESENT,
    OBSERVED_AT_UNKNOWN,
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    apply_evidence_lag_rules,
    inference_kind_for_provenance,
    lane_evidence_from_dict,
    lane_evidence_to_dict,
    observation_clock_key,
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

    def test_hidden_inference_is_never_serialized_as_observed(self) -> None:
        raw = NormalizedLaneEvidence(
            lane=LaneId.ORDER_FLOW,
            signal=EvidenceSignal.AGGRESSIVE_BUY_PRESSURE,
            strength="HIGH",
            available=True,
            source_ref="tape",
            detail="aggressive buy",
            observed_at="2026-07-15T14:45:00.000000000Z",
            provenance_class=EvidenceProvenanceClass.RAW,
        )
        model = NormalizedLaneEvidence(
            lane=LaneId.MARKET_CONTEXT,
            signal=EvidenceSignal.SYNTHESIS_CONTRADICTION_DETECTED,
            strength="HIGH",
            available=True,
            source_ref="mc-synth",
            detail="contradiction",
            provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
        )
        cross = NormalizedLaneEvidence(
            lane=LaneId.OPTIONS,
            signal=EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED,
            strength="MODERATE",
            available=True,
            source_ref="fusion",
            detail="fused",
            provenance_class=EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT,
        )
        raw_payload = lane_evidence_to_dict(raw)
        model_payload = lane_evidence_to_dict(model)
        cross_payload = lane_evidence_to_dict(cross)
        self.assertEqual(raw_payload["inference_kind"], "OBSERVED")
        self.assertEqual(model_payload["inference_kind"], "MODEL_INFERENCE")
        self.assertEqual(cross_payload["inference_kind"], "CROSS_LANE_MODEL_INFERENCE")
        self.assertNotEqual(model_payload["inference_kind"], "OBSERVED")
        self.assertNotEqual(cross_payload["inference_kind"], "OBSERVED")
        self.assertEqual(
            inference_kind_for_provenance(EvidenceProvenanceClass.RAW),
            "OBSERVED",
        )
        restored = lane_evidence_from_dict(
            {**model_payload, "inference_kind": "OBSERVED"}
        )
        self.assertEqual(restored.provenance_class, EvidenceProvenanceClass.MODEL_OUTPUT)
        self.assertEqual(
            lane_evidence_to_dict(restored)["inference_kind"],
            "MODEL_INFERENCE",
        )

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

    def test_whitespace_observed_at_is_empty_not_present(self) -> None:
        item = NormalizedLaneEvidence(
            lane=LaneId.OPTIONS,
            signal=EvidenceSignal.CALL_DEMAND_ANOMALY,
            strength="LOW",
            available=True,
            source_ref="test",
            detail="detail",
            observed_at="   ",
            provenance_class=EvidenceProvenanceClass.DERIVED,
        )
        payload = lane_evidence_to_dict(item)
        self.assertEqual(payload["observed_at_presence"], OBSERVED_AT_EMPTY)
        self.assertIsNone(observation_clock_key(item.observed_at))
        self.assertIsNone(lane_evidence_from_dict({"lane": "options", "signal": "CALL_DEMAND_ANOMALY", "observed_at": "  "}).observed_at)

    def test_present_observed_at_keeps_clock_key(self) -> None:
        observed_at = "2026-07-15T14:45:00.000000000Z"
        self.assertEqual(observation_clock_key(observed_at), observed_at)
        item = NormalizedLaneEvidence(
            lane=LaneId.FUTURES,
            signal=EvidenceSignal.FUTURES_DATA_CONFIDENCE,
            strength="HIGH",
            available=True,
            source_ref="futures:fixture",
            detail="fixture confidence",
            observed_at=observed_at,
            provenance_class=EvidenceProvenanceClass.RAW,
        )
        self.assertEqual(lane_evidence_to_dict(item)["observed_at_presence"], OBSERVED_AT_PRESENT)

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

    def test_blank_observed_at_does_not_couple_context_options(self) -> None:
        items = [
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=EvidenceSignal.EVENT_SURPRISE_POSITIVE,
                strength="MODERATE",
                available=True,
                source_ref="mc6",
                detail="surprise",
                observed_at="  ",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=EvidenceSignal.EVENT_VOL_PREMIUM,
                strength="MODERATE",
                available=True,
                source_ref="o7",
                detail="event vol",
                observed_at="\t",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
        ]
        violations = validate_evidence_dag(items)
        self.assertFalse(any("MC-D20" in item for item in violations))
        filtered, _ = apply_evidence_lag_rules(items)
        self.assertEqual(len(filtered), 2)

    def test_distinct_timestamps_do_not_couple_context_options(self) -> None:
        items = [
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=EvidenceSignal.EVENT_SURPRISE_POSITIVE,
                strength="MODERATE",
                available=True,
                source_ref="mc6",
                detail="surprise",
                observed_at="2026-07-15T14:45:00.000000000Z",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=EvidenceSignal.EVENT_VOL_PREMIUM,
                strength="MODERATE",
                available=True,
                source_ref="o7",
                detail="event vol",
                observed_at="2026-07-15T14:46:00.000000000Z",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            ),
        ]
        self.assertEqual(validate_evidence_dag(items), [])

    def test_reaction_contradicted_stays_inference_not_observation(self) -> None:
        item = NormalizedLaneEvidence(
            lane=LaneId.MARKET_CONTEXT,
            signal=EvidenceSignal.REACTION_CONTRADICTED,
            strength="HIGH",
            available=True,
            source_ref="mc-reaction",
            detail="price reaction contradicted thesis",
            observed_at="2026-07-15T14:45:00.000000000Z",
            provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
        )
        payload = lane_evidence_to_dict(item)
        self.assertEqual(payload["signal"], "REACTION_CONTRADICTED")
        self.assertEqual(payload["inference_kind"], "MODEL_INFERENCE")
        self.assertEqual(payload["observed_at_presence"], OBSERVED_AT_PRESENT)

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
