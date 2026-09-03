"""Tests for intelligence V1 contracts."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    ContractReference,
    Direction,
    EvidenceApplicability,
    EventV1,
    EvidenceV1,
    ForecastEstimate,
    ForecastTarget,
    ForecastV1,
    HypothesisV1,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    OutcomeResolutionStatus,
    OutcomeV1,
    QualityState,
    QualitySummary,
    RunManifestV1,
    SignalV1,
    SnapshotV1,
    SourceReference,
    TimeHorizonNs,
    event_v1_from_dict,
    event_v1_to_dict,
    evidence_v1_from_dict,
    evidence_v1_to_dict,
    forecast_v1_from_dict,
    forecast_v1_to_dict,
    hypothesis_v1_from_dict,
    hypothesis_v1_to_dict,
    opportunity_v1_from_dict,
    opportunity_v1_to_dict,
    outcome_v1_from_dict,
    outcome_v1_to_dict,
    round_trip_contract_dict,
    run_manifest_v1_from_dict,
    run_manifest_v1_to_dict,
    signal_v1_from_dict,
    signal_v1_to_dict,
    snapshot_v1_from_dict,
    snapshot_v1_to_dict,
)

DECISION_NS = 1_700_000_000_000_000_000
HORIZON_NS = 30 * 60 * 1_000_000_000
INSTRUMENT = "NVDA"


def _quality(state: QualityState = QualityState.GOOD) -> QualitySummary:
    return QualitySummary(state=state)


def _scope() -> IntelligenceScope:
    return IntelligenceScope(instrument_ids=(INSTRUMENT,))


class EventV1Tests(unittest.TestCase):
    def test_minimal_instrument_event(self) -> None:
        event = EventV1(
            event_id="evt-nvda-flow",
            schema_version="1",
            event_type="ORDER_FLOW_EVENT",
            event_time_ns=DECISION_NS,
            available_time_ns=DECISION_NS,
            payload={"delta": 71220},
            quality=_quality(),
            source=SourceReference(
                provider_id="MOOMOO",
                source_type="order_flow",
                source_record_id="rec-1",
            ),
            instrument_id=INSTRUMENT,
            received_time_ns=DECISION_NS + 1,
        )
        restored = event_v1_from_dict(round_trip_contract_dict(event_v1_to_dict(event)))
        self.assertEqual(restored.event_id, event.event_id)
        self.assertEqual(restored.payload["delta"], 71220)

    def test_instrumentless_macro_event(self) -> None:
        event = EventV1(
            event_id="evt-fomc",
            schema_version="1",
            event_type="MACRO_RELEASE",
            event_time_ns=DECISION_NS,
            available_time_ns=DECISION_NS,
            payload={"release": "FOMC"},
            quality=_quality(),
            source=SourceReference(
                provider_id="FRED",
                source_type="macro",
                source_record_id="fomc-1",
            ),
        )
        self.assertIsNone(event.instrument_id)

    def test_unknown_fields_rejected(self) -> None:
        payload = event_v1_to_dict(
            EventV1(
                event_id="evt-1",
                schema_version="1",
                event_type="TEST",
                event_time_ns=DECISION_NS,
                available_time_ns=DECISION_NS,
                payload={},
                quality=_quality(),
                source=SourceReference(
                    provider_id="INTERNAL",
                    source_type="test",
                    source_record_id="r1",
                ),
            )
        )
        payload["unexpected"] = True
        with self.assertRaises(ValueError):
            event_v1_from_dict(payload)


class SnapshotV1Tests(unittest.TestCase):
    def test_snapshot_with_event_refs(self) -> None:
        event_ref = ContractReference(kind="event", id="evt-nvda-flow")
        snapshot = SnapshotV1(
            snapshot_id="snap-1",
            schema_version="1",
            decision_time_ns=DECISION_NS,
            scope=_scope(),
            quality=_quality(),
            source_event_refs=(event_ref, event_ref),
        )
        restored = snapshot_v1_from_dict(round_trip_contract_dict(snapshot_v1_to_dict(snapshot)))
        self.assertEqual(len(restored.source_event_refs), 1)


class SignalV1Tests(unittest.TestCase):
    def test_scalar_cvd_signal(self) -> None:
        signal = SignalV1(
            signal_id="sig-cvd-5m",
            schema_version="1",
            signal_type="CVD_5M",
            scope=_scope(),
            as_of_time_ns=DECISION_NS,
            value=71220.0,
            quality=_quality(),
            unit="shares",
            direction=Direction.LONG,
            calculation_window=TimeHorizonNs(duration_ns=5 * 60 * 1_000_000_000),
            normalized_value=0.82,
        )
        restored = signal_v1_from_dict(round_trip_contract_dict(signal_v1_to_dict(signal)))
        self.assertEqual(restored.value, 71220.0)
        self.assertEqual(restored.direction, Direction.LONG)

    def test_non_finite_value_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SignalV1(
                signal_id="sig-bad",
                schema_version="1",
                signal_type="TEST",
                scope=_scope(),
                as_of_time_ns=DECISION_NS,
                value=math.inf,
                quality=_quality(),
            )


class EvidenceV1Tests(unittest.TestCase):
    def test_applicable_evidence(self) -> None:
        evidence = EvidenceV1(
            evidence_id="ev-1",
            schema_version="1",
            snapshot_id="snap-1",
            expert_id="microstructure",
            scope=_scope(),
            applicability=EvidenceApplicability.APPLICABLE,
            quality=_quality(),
            assessment={"pressure": "buy_side_skewed"},
            support_strength=0.74,
            evidence_for=("aggressive_buy_flow",),
            source_signal_refs=(ContractReference(kind="signal", id="sig-cvd-5m"),),
        )
        restored = evidence_v1_from_dict(round_trip_contract_dict(evidence_v1_to_dict(evidence)))
        self.assertEqual(restored.applicability, EvidenceApplicability.APPLICABLE)

    def test_abstaining_evidence(self) -> None:
        evidence = EvidenceV1(
            evidence_id="ev-abstain",
            schema_version="1",
            snapshot_id="snap-1",
            expert_id="gamma",
            scope=_scope(),
            applicability=EvidenceApplicability.INSUFFICIENT_DATA,
            quality=QualitySummary(state=QualityState.DEGRADED),
        )
        self.assertEqual(evidence.abstention_reason, "INSUFFICIENT_DATA")

    def test_support_score_bounds(self) -> None:
        with self.assertRaises(ValueError):
            EvidenceV1(
                evidence_id="ev-bad",
                schema_version="1",
                snapshot_id="snap-1",
                expert_id="x",
                scope=_scope(),
                applicability=EvidenceApplicability.APPLICABLE,
                quality=_quality(),
                support_strength=1.2,
            )


class HypothesisV1Tests(unittest.TestCase):
    def test_hypothesis_without_forecast(self) -> None:
        hypothesis = HypothesisV1(
            hypothesis_id="hyp-1",
            schema_version="1",
            hypothesis_type="SHORT_SQUEEZE_FORMATION",
            scope=_scope(),
            generated_at_ns=DECISION_NS,
            snapshot_id="snap-1",
            quality=_quality(),
            supporting_evidence_ids=("ev-1",),
            contradicting_evidence_ids=("ev-2",),
            support_score=0.61,
            mechanism={"phase": "emerging"},
        )
        restored = hypothesis_v1_from_dict(round_trip_contract_dict(hypothesis_v1_to_dict(hypothesis)))
        self.assertEqual(restored.hypothesis_type, "SHORT_SQUEEZE_FORMATION")


class ForecastV1Tests(unittest.TestCase):
    def test_classification_forecast(self) -> None:
        forecast = ForecastV1(
            forecast_id="fc-1",
            schema_version="1",
            scope=_scope(),
            decision_time_ns=DECISION_NS,
            snapshot_id="snap-1",
            target=ForecastTarget(
                target_kind="midpoint_return_threshold",
                instrument_id=INSTRUMENT,
                parameters={"threshold": 0.0, "metric": "midpoint_return"},
            ),
            horizon=TimeHorizonNs(duration_ns=HORIZON_NS),
            estimate=ForecastEstimate(
                estimate_kind="classification_probability",
                probability=0.68,
                raw_score=0.68,
            ),
            quality=_quality(),
            resolve_time_ns=DECISION_NS + HORIZON_NS,
            source_hypothesis_refs=(ContractReference(kind="hypothesis", id="hyp-1"),),
        )
        restored = forecast_v1_from_dict(round_trip_contract_dict(forecast_v1_to_dict(forecast)))
        self.assertEqual(restored.estimate.probability, 0.68)

    def test_probability_out_of_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ForecastV1(
                forecast_id="fc-bad",
                schema_version="1",
                scope=_scope(),
                decision_time_ns=DECISION_NS,
                snapshot_id="snap-1",
                target=ForecastTarget(
                    target_kind="midpoint_return_threshold",
                    instrument_id=INSTRUMENT,
                    parameters={"threshold": 0.0},
                ),
                horizon=TimeHorizonNs(duration_ns=HORIZON_NS),
                estimate=ForecastEstimate(
                    estimate_kind="classification_probability",
                    probability=1.5,
                ),
                quality=_quality(),
            )


class OpportunityV1Tests(unittest.TestCase):
    def test_opportunity_not_order(self) -> None:
        opportunity = OpportunityV1(
            opportunity_id="opp-1",
            schema_version="1",
            scope=_scope(),
            created_at_ns=DECISION_NS,
            quality=_quality(),
            side=OpportunitySide.LONG,
            source_forecast_refs=(ContractReference(kind="forecast", id="fc-1"),),
            expected_net_edge=0.0031,
            valid_until_ns=DECISION_NS + HORIZON_NS,
            reason_summary="candidate long after costs",
        )
        payload = opportunity_v1_to_dict(opportunity)
        self.assertNotIn("quantity", payload)
        self.assertNotIn("order_id", payload)
        restored = opportunity_v1_from_dict(round_trip_contract_dict(payload))
        self.assertEqual(restored.side, OpportunitySide.LONG)

    def test_execution_metadata_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            OpportunityV1(
                opportunity_id="opp-bad",
                schema_version="1",
                scope=_scope(),
                created_at_ns=DECISION_NS,
                quality=_quality(),
                metadata={"quantity": 100},
            )


class OutcomeV1Tests(unittest.TestCase):
    def test_settled_outcome(self) -> None:
        outcome = OutcomeV1(
            outcome_id="out-1",
            schema_version="1",
            forecast_id="fc-1",
            adjudicated_at_ns=DECISION_NS + HORIZON_NS,
            resolution_status=OutcomeResolutionStatus.SETTLED,
            quality=_quality(),
            realized_return=0.0042,
            realized_direction=Direction.LONG,
            mfe=0.0065,
            mae=-0.0012,
            start_observation={"midpoint": 120.5},
            end_observation={"midpoint": 121.0},
        )
        restored = outcome_v1_from_dict(round_trip_contract_dict(outcome_v1_to_dict(outcome)))
        self.assertEqual(restored.realized_return, 0.0042)

    def test_unlabelable_outcome(self) -> None:
        outcome = OutcomeV1(
            outcome_id="out-unlabelable",
            schema_version="1",
            forecast_id="fc-1",
            adjudicated_at_ns=DECISION_NS + HORIZON_NS,
            resolution_status=OutcomeResolutionStatus.UNLABELABLE,
            quality=QualitySummary(state=QualityState.INVALID),
            unlabelable_reason="MISSING_RESOLUTION_BAR",
        )
        self.assertEqual(outcome.resolution_status, OutcomeResolutionStatus.UNLABELABLE)


class RunManifestV1Tests(unittest.TestCase):
    def test_minimal_manifest(self) -> None:
        manifest = RunManifestV1(
            run_id="run-1",
            schema_version="1",
            created_at_ns=DECISION_NS,
            quality=_quality(),
            data_mode="FIXTURE_REPLAY",
            execution_mode="NONE",
            execution_authority="BLOCKED",
        )
        restored = run_manifest_v1_from_dict(round_trip_contract_dict(run_manifest_v1_to_dict(manifest)))
        self.assertEqual(restored.execution_authority, "BLOCKED")

    def test_invalid_execution_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RunManifestV1(
                run_id="run-bad",
                schema_version="1",
                created_at_ns=DECISION_NS,
                quality=_quality(),
                execution_mode="LIVE_TRADING",
            )


if __name__ == "__main__":
    unittest.main()
